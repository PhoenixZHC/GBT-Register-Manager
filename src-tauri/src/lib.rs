use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::fs::OpenOptions;
use std::io::Write;
use std::path::PathBuf;
use std::process::{Command, Stdio};
use std::sync::{Mutex, OnceLock};
use tauri::{Manager, State};
use tauri_plugin_dialog::{DialogExt, FilePath};

#[cfg(windows)]
use std::os::windows::process::CommandExt;

// ---------- 原生错误对话框（WebView2 未就绪时兜底） ------------------------

#[cfg(windows)]
fn show_native_error(title: &str, msg: &str) {
    use std::ffi::OsStr;
    use std::iter::once;
    use std::os::windows::ffi::OsStrExt;
    extern "system" {
        fn MessageBoxW(hwnd: *mut (), text: *const u16, caption: *const u16, utype: u32) -> i32;
    }
    let encode = |s: &str| -> Vec<u16> {
        OsStr::new(s).encode_wide().chain(once(0)).collect()
    };
    let text = encode(msg);
    let caption = encode(title);
    unsafe {
        MessageBoxW(std::ptr::null_mut(), text.as_ptr(), caption.as_ptr(), 0x10 /*MB_ICONERROR*/);
    }
}

#[cfg(not(windows))]
fn show_native_error(_title: &str, msg: &str) {
    eprintln!("[GBT-RS] FATAL: {msg}");
}

/// 与前端一致：该地址为调试入口，不连接真实机器人
const DEBUG_BYPASS_IP: &str = "255.255.255.255";

#[cfg(windows)]
const CREATE_NO_WINDOW: u32 = 0x0800_0000;

const FRAME_BEGIN: &str = "<<<GBT-BEGIN>>>";
const FRAME_END: &str = "<<<GBT-END>>>";

// ---------- 日志 -----------------------------------------------------------

static LOG_FILE: OnceLock<PathBuf> = OnceLock::new();
static LOG_DIR: OnceLock<PathBuf> = OnceLock::new();
const LOG_MAX_BYTES: u64 = 2 * 1024 * 1024;

fn rotate_if_needed(path: &PathBuf) {
    if let Ok(meta) = std::fs::metadata(path) {
        if meta.len() > LOG_MAX_BYTES {
            let backup = path.with_extension("log.1");
            let _ = std::fs::remove_file(&backup);
            let _ = std::fs::rename(path, &backup);
        }
    }
}

fn gbt_log(msg: &str) {
    eprintln!("[GBT-RS] {msg}");
    let _ = std::io::stderr().flush();
    if let Some(path) = LOG_FILE.get() {
        rotate_if_needed(path);
        if let Ok(mut f) = OpenOptions::new().create(true).append(true).open(path) {
            let ts = chrono_like_now();
            let _ = writeln!(f, "{ts} [GBT-RS] {msg}");
        }
    }
}

fn chrono_like_now() -> String {
    use std::time::{SystemTime, UNIX_EPOCH};
    let secs = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0);
    format!("{secs}")
}

// ---------- State ----------------------------------------------------------

#[derive(Default)]
struct AppState {
    connection: Mutex<ConnectionState>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
#[serde(rename_all = "camelCase")]
struct ConnectionState {
    connected: bool,
    /// 控制柜 IP（显示用）。保留字段名 `ip` 以兼容历史持久化/前端旧逻辑。
    ip: String,
    /// 示教器 IP（可选）。四轴无 TP 时为空。
    #[serde(default)]
    teach_panel_ip: String,
    /// 是否让 SDK 在本机启动代理服务（无 TP 或旧软件时需 true）。
    #[serde(default)]
    local_proxy: bool,
    message: String,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct ConnectRequest {
    /// 控制柜 IP（必填）。
    controller_ip: String,
    /// 示教器 IP（可选）。
    #[serde(default)]
    teach_panel_ip: Option<String>,
    /// 是否开启本机代理（四轴无 TP 时应为 true）。
    #[serde(default)]
    local_proxy: bool,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct Selector {
    mode: String,
    start_id: Option<i64>,
    end_id: Option<i64>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct ReadRequest {
    register_type: String,
    program_name: Option<String>,
    selector: Selector,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct ApplyRequest {
    register_type: String,
    program_name: Option<String>,
    conflict_policy: String,
    rows: Vec<Value>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
struct CommonResponse {
    ok: bool,
    message: String,
    #[serde(skip_serializing_if = "Option::is_none")]
    details: Option<Vec<String>>,
}

#[derive(Debug, Clone, Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]
struct RobotMeta {
    model: String,
    controller_version: String,
}

// ---------- 锁辅助 ---------------------------------------------------------

fn lock_connection<'a>(
    state: &'a State<'_, AppState>,
) -> Result<std::sync::MutexGuard<'a, ConnectionState>, String> {
    state
        .connection
        .lock()
        .map_err(|e| format!("连接状态锁异常，请重启应用：{e}"))
}

/// 把已连接状态序列化成 sidecar payload 所需的连接字段（camelCase）。
fn connection_payload_fields(conn: &ConnectionState) -> serde_json::Map<String, Value> {
    let mut m = serde_json::Map::new();
    m.insert("controllerIp".into(), Value::String(conn.ip.clone()));
    // 兼容旧 payload 字段名
    m.insert("ip".into(), Value::String(conn.ip.clone()));
    m.insert(
        "teachPanelIp".into(),
        if conn.teach_panel_ip.is_empty() {
            Value::Null
        } else {
            Value::String(conn.teach_panel_ip.clone())
        },
    );
    m.insert("localProxy".into(), Value::Bool(conn.local_proxy));
    m
}

fn friendly_python_error(raw: &str) -> String {
    let raw = raw.trim();
    if raw.is_empty() {
        return "Python sidecar 崩溃且无输出，请查看日志。".into();
    }
    // 精简：取最后一行非空，避免整段 traceback 暴给用户
    let last = raw
        .lines()
        .rev()
        .find(|l| !l.trim().is_empty())
        .unwrap_or(raw)
        .trim();
    if last.len() > 280 {
        format!("{}…（详情见日志）", &last[..280])
    } else {
        last.to_string()
    }
}

// ---------- sidecar 调用 ---------------------------------------------------

enum Sidecar {
    /// 开发期：系统 Python + bridge.py
    #[cfg(debug_assertions)]
    DevScript { python: String, script: PathBuf, cwd: PathBuf },
    /// 发布期：PyInstaller 冻结的 gbt-bridge.exe
    FrozenExe { exe: PathBuf },
}

fn resolve_sidecar() -> Result<Sidecar, String> {
    #[cfg(debug_assertions)]
    {
        let script = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
            .join("..")
            .join("python-sidecar")
            .join("bridge.py");
        if script.is_file() {
            let cwd = script
                .parent()
                .ok_or_else(|| "bridge.py 路径无效".to_string())?
                .to_path_buf();
            return Ok(Sidecar::DevScript {
                python: "python".into(),
                script,
                cwd,
            });
        }
    }

    // 发布期：可执行文件与主程序同目录（Tauri externalBin 规则）
    let exe = std::env::current_exe().map_err(|e| format!("定位主程序失败: {e}"))?;
    let dir = exe
        .parent()
        .ok_or_else(|| "无法解析主程序目录".to_string())?;
    let name = if cfg!(windows) {
        "gbt-bridge.exe"
    } else {
        "gbt-bridge"
    };
    let candidate = dir.join(name);
    if candidate.is_file() {
        return Ok(Sidecar::FrozenExe { exe: candidate });
    }

    // 兜底：部分 Tauri 版本/安装布局会把 externalBin 放进 resources/ 子目录。
    let alt = dir.join("resources").join(name);
    if alt.is_file() {
        return Ok(Sidecar::FrozenExe { exe: alt });
    }

    Err(format!(
        "找不到 sidecar 可执行文件（{}）。请确认安装包完整，或开发期确认 python-sidecar/bridge.py 存在。",
        candidate.display()
    ))
}

fn build_sidecar_command(sidecar: &Sidecar) -> Command {
    let mut cmd = match sidecar {
        #[cfg(debug_assertions)]
        Sidecar::DevScript { python, script, cwd } => {
            let mut c = Command::new(python);
            c.arg(script).current_dir(cwd);
            c
        }
        Sidecar::FrozenExe { exe } => {
            let mut c = Command::new(exe);
            if let Some(parent) = exe.parent() {
                c.current_dir(parent);
            }
            c
        }
    };
    cmd.env("PYTHONUTF8", "1");
    cmd.env("PYTHONIOENCODING", "utf-8");
    if let Some(dir) = LOG_DIR.get() {
        cmd.env("GBT_LOG_DIR", dir);
    }

    #[cfg(windows)]
    cmd.creation_flags(CREATE_NO_WINDOW);

    cmd
}

fn extract_frame(stdout: &[u8]) -> Result<Value, String> {
    let mut s = stdout;
    if s.starts_with(&[0xEF, 0xBB, 0xBF]) {
        s = &s[3..];
    }
    let text = std::str::from_utf8(s).map_err(|e| format!("Python 输出不是有效 UTF-8: {e}"))?;
    let begin = text
        .find(FRAME_BEGIN)
        .ok_or_else(|| "Python 输出缺少 <<<GBT-BEGIN>>> 标记，可能已崩溃。".to_string())?;
    let rest = &text[begin + FRAME_BEGIN.len()..];
    let end = rest
        .find(FRAME_END)
        .ok_or_else(|| "Python 输出缺少 <<<GBT-END>>> 标记，可能已被截断。".to_string())?;
    let body = rest[..end].trim();
    serde_json::from_str::<Value>(body)
        .map_err(|e| format!("解析 Python 输出 JSON 失败: {e}"))
}

fn run_python_action(payload: Value) -> Result<Value, String> {
    let action = payload
        .get("action")
        .and_then(|a| a.as_str())
        .unwrap_or("?");
    gbt_log(&format!("python spawn action={action}"));

    let sidecar = resolve_sidecar()?;
    let mut cmd = build_sidecar_command(&sidecar);
    cmd.stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped());

    let mut child = cmd.spawn().map_err(|e| {
        gbt_log(&format!("python spawn failed action={action} err={e}"));
        format!("启动 Python sidecar 失败: {e}")
    })?;

    // 通过 stdin 传入 JSON，避免 Windows 命令行 32K 长度限制
    {
        let stdin = child
            .stdin
            .as_mut()
            .ok_or_else(|| "无法打开 sidecar stdin".to_string())?;
        let payload_bytes = serde_json::to_vec(&payload)
            .map_err(|e| format!("序列化 payload 失败: {e}"))?;
        stdin
            .write_all(&payload_bytes)
            .map_err(|e| format!("写入 sidecar stdin 失败: {e}"))?;
    }

    let output = child
        .wait_with_output()
        .map_err(|e| format!("等待 sidecar 退出失败: {e}"))?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr).to_string();
        gbt_log(&format!(
            "python exit_fail action={action} code={:?}",
            output.status.code()
        ));
        return Err(friendly_python_error(&stderr));
    }

    let parsed = extract_frame(&output.stdout).map_err(|e| {
        let stderr_tail: String = String::from_utf8_lossy(&output.stderr)
            .chars()
            .take(400)
            .collect();
        gbt_log(&format!(
            "python frame_err action={action} msg={e} stderr_tail={stderr_tail}"
        ));
        e
    })?;

    gbt_log(&format!(
        "python done action={action} stdout_bytes={}",
        output.stdout.len()
    ));
    Ok(parsed)
}

/// 在 Tauri 的 blocking 线程池中运行阻塞调用，避免冻住 IPC 线程。
async fn run_python_action_async(payload: Value) -> Result<Value, String> {
    tauri::async_runtime::spawn_blocking(move || run_python_action(payload))
        .await
        .map_err(|e| format!("任务调度失败: {e}"))?
}

// ---------- IPC Commands --------------------------------------------------

#[tauri::command]
fn get_app_version() -> String {
    env!("CARGO_PKG_VERSION").to_string()
}

#[tauri::command]
fn open_devtools(window: tauri::WebviewWindow) {
    window.open_devtools();
}

#[tauri::command]
fn get_log_dir() -> Option<String> {
    LOG_DIR.get().map(|p| p.to_string_lossy().to_string())
}

#[tauri::command]
async fn fetch_robot_meta(state: State<'_, AppState>) -> Result<RobotMeta, String> {
    gbt_log("fetch_robot_meta begin");
    let conn = lock_connection(&state)?.clone();
    if !conn.connected {
        gbt_log("fetch_robot_meta abort: not connected");
        return Err("请先连接机器人".to_string());
    }
    if conn.ip == DEBUG_BYPASS_IP {
        gbt_log("fetch_robot_meta debug_bypass empty meta");
        return Ok(RobotMeta {
            model: String::new(),
            controller_version: String::new(),
        });
    }
    let mut payload_map = connection_payload_fields(&conn);
    payload_map.insert("action".into(), Value::String("fetch_robot_meta".into()));
    let payload = Value::Object(payload_map);
    let v = run_python_action_async(payload).await.map_err(|e| {
        gbt_log(&format!("fetch_robot_meta python_err {e}"));
        e
    })?;
    let meta = RobotMeta {
        model: v
            .get("model")
            .and_then(|x| x.as_str())
            .unwrap_or("")
            .to_string(),
        controller_version: v
            .get("controllerVersion")
            .and_then(|x| x.as_str())
            .unwrap_or("")
            .to_string(),
    };
    gbt_log(&format!(
        "fetch_robot_meta ok model_len={} ver_len={}",
        meta.model.len(),
        meta.controller_version.len()
    ));
    Ok(meta)
}

#[tauri::command]
async fn connect_robot(
    req: ConnectRequest,
    state: State<'_, AppState>,
) -> Result<ConnectionState, String> {
    gbt_log("connect_robot begin");
    let controller_ip = req.controller_ip.trim().to_string();
    let teach_panel_ip = req
        .teach_panel_ip
        .as_ref()
        .map(|s| s.trim().to_string())
        .filter(|s| !s.is_empty())
        .unwrap_or_default();
    let local_proxy = req.local_proxy;

    if controller_ip.is_empty() {
        let mut conn = lock_connection(&state)?;
        conn.connected = false;
        conn.message = "控制柜 IP 不能为空".to_string();
        gbt_log("connect_robot end empty_controller_ip");
        return Ok(conn.clone());
    }
    if controller_ip == DEBUG_BYPASS_IP {
        let mut conn = lock_connection(&state)?;
        conn.connected = true;
        conn.ip = controller_ip.clone();
        conn.teach_panel_ip = teach_panel_ip.clone();
        conn.local_proxy = local_proxy;
        conn.message = "调试模式（未连接真实机器人）".to_string();
        gbt_log("connect_robot end debug_bypass");
        return Ok(conn.clone());
    }

    gbt_log(&format!(
        "connect_robot verify_connect controller_ip={controller_ip} \
         teach_panel_ip={teach_panel_ip} local_proxy={local_proxy}"
    ));

    let payload = serde_json::json!({
        "action": "verify_connect",
        "controllerIp": controller_ip,
        "ip": controller_ip,
        "teachPanelIp": if teach_panel_ip.is_empty() { Value::Null } else { Value::String(teach_panel_ip.clone()) },
        "localProxy": local_proxy,
    });

    let result = run_python_action_async(payload).await;

    let mut conn = lock_connection(&state)?;
    match result {
        Ok(v) => {
            let ok = v.get("ok").and_then(Value::as_bool).unwrap_or(false);
            let msg = v
                .get("message")
                .and_then(Value::as_str)
                .unwrap_or("")
                .to_string();
            if ok {
                conn.connected = true;
                conn.ip = controller_ip.clone();
                conn.teach_panel_ip = teach_panel_ip.clone();
                conn.local_proxy = local_proxy;
                conn.message = if msg.is_empty() {
                    "连接已建立".to_string()
                } else {
                    msg
                };
                gbt_log(&format!("connect_robot ok controller_ip={controller_ip}"));
            } else {
                conn.connected = false;
                conn.ip.clear();
                conn.teach_panel_ip.clear();
                conn.local_proxy = false;
                conn.message = if msg.is_empty() {
                    "连接失败".to_string()
                } else {
                    msg.clone()
                };
                gbt_log(&format!(
                    "connect_robot failed controller_ip={controller_ip} msg={msg}"
                ));
            }
        }
        Err(e) => {
            conn.connected = false;
            conn.ip.clear();
            conn.teach_panel_ip.clear();
            conn.local_proxy = false;
            conn.message = e.clone();
            gbt_log(&format!(
                "connect_robot python_err controller_ip={controller_ip} err={e}"
            ));
        }
    }
    Ok(conn.clone())
}

#[tauri::command]
fn get_connection_status(state: State<AppState>) -> Result<ConnectionState, String> {
    Ok(lock_connection(&state)?.clone())
}

#[tauri::command]
fn disconnect_robot(state: State<AppState>) -> Result<CommonResponse, String> {
    gbt_log("disconnect_robot");
    let mut conn = lock_connection(&state)?;
    conn.connected = false;
    conn.ip.clear();
    conn.teach_panel_ip.clear();
    conn.local_proxy = false;
    conn.message = "已断开连接".to_string();
    Ok(CommonResponse {
        ok: true,
        message: "已断开连接".to_string(),
        details: None,
    })
}

#[tauri::command]
async fn read_registers(
    req: ReadRequest,
    state: State<'_, AppState>,
) -> Result<Vec<Value>, String> {
    gbt_log(&format!(
        "read_registers begin type={} program={:?} mode={} start={:?} end={:?}",
        req.register_type,
        req.program_name,
        req.selector.mode,
        req.selector.start_id,
        req.selector.end_id
    ));
    let conn = lock_connection(&state)?.clone();
    if !conn.connected {
        gbt_log("read_registers abort not_connected");
        return Err("请先连接机器人".to_string());
    }
    if conn.ip == DEBUG_BYPASS_IP {
        gbt_log("read_registers debug_bypass empty");
        return Ok(vec![]);
    }
    let mut payload_map = connection_payload_fields(&conn);
    payload_map.insert("action".into(), Value::String("read_preview".into()));
    payload_map.insert(
        "request".into(),
        serde_json::to_value(&req).map_err(|e| format!("序列化 ReadRequest 失败: {e}"))?,
    );
    let payload = Value::Object(payload_map);
    let result = run_python_action_async(payload).await.map_err(|e| {
        gbt_log(&format!("read_registers python_err {e}"));
        e
    })?;
    let rows = result
        .get("rows")
        .and_then(Value::as_array)
        .cloned()
        .unwrap_or_default();
    gbt_log(&format!("read_registers ok row_count={}", rows.len()));
    Ok(rows)
}

#[tauri::command]
async fn apply_registers(
    req: ApplyRequest,
    state: State<'_, AppState>,
) -> Result<CommonResponse, String> {
    gbt_log(&format!(
        "apply_registers begin type={} policy={} rows={}",
        req.register_type,
        req.conflict_policy,
        req.rows.len()
    ));
    let conn = lock_connection(&state)?.clone();
    if !conn.connected {
        gbt_log("apply_registers abort not_connected");
        return Err("请先连接机器人".to_string());
    }
    if conn.ip == DEBUG_BYPASS_IP {
        gbt_log("apply_registers debug_bypass skip_write");
        return Ok(CommonResponse {
            ok: true,
            message: "调试模式：已跳过写入（未连接真实机器人）".to_string(),
            details: None,
        });
    }
    let mut payload_map = connection_payload_fields(&conn);
    payload_map.insert("action".into(), Value::String("apply_rows".into()));
    payload_map.insert(
        "request".into(),
        serde_json::to_value(&req).map_err(|e| format!("序列化 ApplyRequest 失败: {e}"))?,
    );
    let payload = Value::Object(payload_map);
    let result = run_python_action_async(payload).await.map_err(|e| {
        gbt_log(&format!("apply_registers python_err {e}"));
        e
    })?;
    let resp = CommonResponse {
        ok: result.get("ok").and_then(Value::as_bool).unwrap_or(false),
        message: result
            .get("message")
            .and_then(Value::as_str)
            .unwrap_or("执行完成")
            .to_string(),
        details: result
            .get("details")
            .and_then(Value::as_array)
            .map(|arr| {
                arr.iter()
                    .filter_map(|v| v.as_str().map(|s| s.to_string()))
                    .collect::<Vec<String>>()
            }),
    };
    gbt_log(&format!(
        "apply_registers end ok={} detail_count={}",
        resp.ok,
        resp.details.as_ref().map(|d| d.len()).unwrap_or(0)
    ));
    Ok(resp)
}

fn file_path_to_string(path: FilePath) -> Result<String, String> {
    path.into_path()
        .map(|p| p.to_string_lossy().to_string())
        .map_err(|e| format!("无法解析保存路径: {e}"))
}

#[tauri::command]
async fn export_preview_to_excel(
    app: tauri::AppHandle,
    register_type: String,
    rows: Vec<Value>,
) -> Result<CommonResponse, String> {
    gbt_log(&format!(
        "export_preview_to_excel begin type={} rows={}",
        register_type,
        rows.len()
    ));
    let default_name = format!("{register_type}_export.xlsx");
    let file_path = tauri::async_runtime::spawn_blocking({
        let app = app.clone();
        move || {
            app.dialog()
                .file()
                .add_filter("Excel", &["xlsx"])
                .set_file_name(&default_name)
                .blocking_save_file()
        }
    })
    .await
    .map_err(|e| format!("打开保存对话框失败: {e}"))?;

    let Some(fp) = file_path else {
        gbt_log("export_preview_to_excel user_cancelled_dialog");
        return Ok(CommonResponse {
            ok: false,
            message: "已取消保存".to_string(),
            details: None,
        });
    };
    let output_path = file_path_to_string(fp)?;
    gbt_log(&format!(
        "export_preview_to_excel path_ok len={}",
        output_path.len()
    ));
    let payload = serde_json::json!({
      "action": "export_excel",
      "registerType": register_type,
      "rows": rows,
      "outputPath": output_path
    });
    let result = run_python_action_async(payload).await?;
    let ok = result.get("ok").and_then(Value::as_bool).unwrap_or(false);
    gbt_log(&format!("export_preview_to_excel end ok={ok}"));
    Ok(CommonResponse {
        ok,
        message: result
            .get("message")
            .and_then(Value::as_str)
            .unwrap_or("导出完成")
            .to_string(),
        details: None,
    })
}

#[tauri::command]
async fn export_template_excel(
    app: tauri::AppHandle,
    register_type: String,
) -> Result<CommonResponse, String> {
    gbt_log(&format!("export_template_excel begin type={register_type}"));
    let default_name = format!("{register_type}_template.xlsx");
    let file_path = tauri::async_runtime::spawn_blocking({
        let app = app.clone();
        move || {
            app.dialog()
                .file()
                .add_filter("Excel", &["xlsx"])
                .set_file_name(&default_name)
                .blocking_save_file()
        }
    })
    .await
    .map_err(|e| format!("打开保存对话框失败: {e}"))?;

    let Some(fp) = file_path else {
        gbt_log("export_template_excel user_cancelled_dialog");
        return Ok(CommonResponse {
            ok: false,
            message: "已取消保存".to_string(),
            details: None,
        });
    };
    let output_path = file_path_to_string(fp)?;
    let payload = serde_json::json!({
      "action": "export_template",
      "registerType": register_type,
      "outputPath": output_path
    });
    let result = run_python_action_async(payload).await?;
    let ok = result.get("ok").and_then(Value::as_bool).unwrap_or(false);
    gbt_log(&format!("export_template_excel end ok={ok}"));
    Ok(CommonResponse {
        ok,
        message: result
            .get("message")
            .and_then(Value::as_str)
            .unwrap_or("模板导出完成")
            .to_string(),
        details: None,
    })
}

// ---------- 入口 -----------------------------------------------------------

pub fn run() {
    let app_state = AppState {
        connection: Mutex::new(ConnectionState {
            connected: false,
            ip: String::new(),
            teach_panel_ip: String::new(),
            local_proxy: false,
            message: "未连接".to_string(),
        }),
    };

    let result = tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .manage(app_state)
        .setup(|app| {
            let handle = app.handle();
            if let Ok(dir) = handle.path().app_log_dir() {
                let _ = std::fs::create_dir_all(&dir);
                let file = dir.join("gbt-rs.log");
                let _ = LOG_DIR.set(dir.clone());
                let _ = LOG_FILE.set(file);
            }
            gbt_log(&format!(
                "=== app starting === version={} os={}",
                env!("CARGO_PKG_VERSION"),
                std::env::consts::OS
            ));
            // 打印日志路径，方便客户反馈时定位
            if let Some(dir) = LOG_DIR.get() {
                gbt_log(&format!("log_dir={}", dir.display()));
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![
            connect_robot,
            get_connection_status,
            disconnect_robot,
            get_app_version,
            fetch_robot_meta,
            read_registers,
            apply_registers,
            export_preview_to_excel,
            export_template_excel,
            open_devtools,
            get_log_dir
        ])
        .run(tauri::generate_context!());

    if let Err(e) = result {
        let msg = format!(
            "应用启动失败，错误信息：\n\n{e}\n\n\
            可能原因：\n\
            1. WebView2 运行时未安装或损坏，请重新安装本软件\n\
            2. 显卡驱动异常，尝试更新显卡驱动\n\n\
            日志位置：%APPDATA%\\com.gbt.register.manager\\logs\\gbt-rs.log"
        );
        eprintln!("[GBT-RS] FATAL: {e}");
        show_native_error("GBT Register Manager - 启动失败", &msg);
        std::process::exit(1);
    }
}
