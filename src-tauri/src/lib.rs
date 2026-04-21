use serde::{Deserialize, Serialize};
use serde_json::Value;
use std::io::Write;
use std::path::PathBuf;
use std::process::Command;
use std::sync::Mutex;
use tauri::State;
use tauri_plugin_dialog::{DialogExt, FilePath};

/// 与前端一致：该地址为调试入口，不连接真实机器人
const DEBUG_BYPASS_IP: &str = "255.255.255.255";

/// 控制台排查日志（写入 stderr，便于与 Python 侧 `[GBT-PY]` 区分）
fn gbt_log(msg: &str) {
    eprintln!("[GBT-RS] {msg}");
    let _ = std::io::stderr().flush();
}

#[derive(Default)]
struct AppState {
    connection: Mutex<ConnectionState>,
}

#[derive(Debug, Clone, Serialize, Deserialize, Default)]
#[serde(rename_all = "camelCase")]
struct ConnectionState {
    connected: bool,
    ip: String,
    message: String,
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

#[tauri::command]
fn get_app_version() -> String {
    env!("CARGO_PKG_VERSION").to_string()
}

#[tauri::command]
fn fetch_robot_meta(state: State<AppState>) -> Result<RobotMeta, String> {
    gbt_log("fetch_robot_meta begin");
    let conn = state.connection.lock().expect("lock connection").clone();
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
    let payload = serde_json::json!({
      "action": "fetch_robot_meta",
      "ip": conn.ip
    });
    let v = run_python_action(payload).map_err(|e| {
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
fn connect_robot(ip: String, state: State<AppState>) -> ConnectionState {
    gbt_log("connect_robot begin");
    let mut conn = state.connection.lock().expect("lock connection");
    let trimmed = ip.trim().to_string();
    if trimmed.is_empty() {
        conn.connected = false;
        conn.message = "IP 不能为空".to_string();
        gbt_log("connect_robot end empty_ip");
        return conn.clone();
    }
    if trimmed == DEBUG_BYPASS_IP {
        conn.connected = true;
        conn.ip = trimmed.clone();
        conn.message = "调试模式（未连接真实机器人）".to_string();
        gbt_log("connect_robot end debug_bypass");
        return conn.clone();
    }
    gbt_log(&format!("connect_robot verify_connect ip={trimmed}"));
    let payload = serde_json::json!({
        "action": "verify_connect",
        "ip": trimmed
    });
    match run_python_action(payload) {
        Ok(v) => {
            let ok = v.get("ok").and_then(Value::as_bool).unwrap_or(false);
            let msg = v
                .get("message")
                .and_then(Value::as_str)
                .unwrap_or("")
                .to_string();
            if ok {
                conn.connected = true;
                conn.ip = trimmed.clone();
                conn.message = if msg.is_empty() {
                    "连接已建立".to_string()
                } else {
                    msg
                };
                gbt_log(&format!("connect_robot ok ip={trimmed}"));
            } else {
                conn.connected = false;
                conn.ip.clear();
                conn.message = if msg.is_empty() {
                    "连接失败".to_string()
                } else {
                    msg.clone()
                };
                gbt_log(&format!("connect_robot failed ip={trimmed} msg={msg}"));
            }
        }
        Err(e) => {
            conn.connected = false;
            conn.ip.clear();
            conn.message = e.clone();
            gbt_log(&format!("connect_robot python_err ip={trimmed} err={e}"));
        }
    }
    conn.clone()
}

#[tauri::command]
fn get_connection_status(state: State<AppState>) -> ConnectionState {
    state.connection.lock().expect("lock connection").clone()
}

#[tauri::command]
fn disconnect_robot(state: State<AppState>) -> CommonResponse {
    gbt_log("disconnect_robot");
    let mut conn = state.connection.lock().expect("lock connection");
    conn.connected = false;
    conn.ip.clear();
    conn.message = "已断开连接".to_string();
    CommonResponse {
        ok: true,
        message: "已断开连接".to_string(),
        details: None,
    }
}

/// `python-sidecar` 在仓库根目录，与 `src-tauri` 同级；不能依赖进程 cwd（`tauri dev` 时常为 `src-tauri`）。
fn bridge_script_path() -> Result<PathBuf, String> {
    let from_manifest = PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .join("..")
        .join("python-sidecar")
        .join("bridge.py");
    if from_manifest.is_file() {
        return from_manifest.canonicalize().map_err(|e| format!("解析 bridge.py 路径失败: {e}"));
    }
    Err(format!(
        "找不到 python-sidecar/bridge.py（已检查: {}）。请确认工程目录完整。",
        from_manifest.display()
    ))
}

fn run_python_action(payload: Value) -> Result<Value, String> {
    let action = payload
        .get("action")
        .and_then(|a| a.as_str())
        .unwrap_or("?");
    gbt_log(&format!("python spawn action={action}"));
    let script = bridge_script_path()?;
    let output = Command::new("python")
        .env("PYTHONUTF8", "1")
        .current_dir(
            script
                .parent()
                .ok_or_else(|| "bridge.py 路径无效".to_string())?,
        )
        .arg(&script)
        .arg(payload.to_string())
        .output()
        .map_err(|e| {
            gbt_log(&format!("python spawn failed action={action} err={e}"));
            format!("执行 Python sidecar 失败: {e}")
        })?;

    if !output.status.success() {
        let stderr = String::from_utf8_lossy(&output.stderr).to_string();
        let tail: String = stderr.chars().take(800).collect();
        gbt_log(&format!(
            "python exit_fail action={action} code={:?} stderr_tail={tail}",
            output.status.code()
        ));
        return Err(format!("Python 执行失败: {stderr}"));
    }
    let parsed = parse_python_json_stdout(&output.stdout)?;
    gbt_log(&format!(
        "python done action={action} stdout_bytes={}",
        output.stdout.len()
    ));
    Ok(parsed)
}

/// 解析 bridge 写入 stdout 的**第一个** JSON 对象。
/// SDK 或第三方库偶发会在同一 stdout 流里追加调试字符，导致 `from_str` 报 trailing characters；
/// 这里从首个 `{` 起用流式反序列化只取一个 `Value`，其余忽略。
fn parse_python_json_stdout(raw: &[u8]) -> Result<Value, String> {
    let mut s = raw;
    if s.starts_with(&[0xEF, 0xBB, 0xBF]) {
        s = &s[3..];
    }
    let text = std::str::from_utf8(s).map_err(|e| format!("Python 输出不是有效 UTF-8: {e}"))?;
    let text = text.trim();
    let from_obj = text
        .find('{')
        .map(|i| &text[i..])
        .ok_or_else(|| {
            format!(
                "Python stdout 中未找到 JSON 对象（应以 {{ 开头），原始长度={} 字节",
                text.len()
            )
        })?;
    let mut de = serde_json::Deserializer::from_str(from_obj);
    let v = Value::deserialize(&mut de)
        .map_err(|e| format!("解析 Python 输出失败: {e}"))?;
    if let Some(i) = text.find('{') {
        if i > 0 {
            gbt_log(&format!(
                "parse_python_json_stdout: skipped {i} non-JSON prefix bytes before `{{`"
            ));
        }
    }
    Ok(v)
}

#[tauri::command]
fn read_registers(req: ReadRequest, state: State<AppState>) -> Result<Vec<Value>, String> {
    gbt_log(&format!(
        "read_registers begin type={} program={:?} mode={} start={:?} end={:?}",
        req.register_type,
        req.program_name,
        req.selector.mode,
        req.selector.start_id,
        req.selector.end_id
    ));
    let conn = state.connection.lock().expect("lock connection").clone();
    if !conn.connected {
        gbt_log("read_registers abort not_connected");
        return Err("请先连接机器人".to_string());
    }
    if conn.ip == DEBUG_BYPASS_IP {
        gbt_log("read_registers debug_bypass empty");
        return Ok(vec![]);
    }
    let payload = serde_json::json!({
      "action": "read_preview",
      "ip": conn.ip,
      "request": req
    });
    let result = run_python_action(payload).map_err(|e| {
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
fn apply_registers(req: ApplyRequest, state: State<AppState>) -> Result<CommonResponse, String> {
    gbt_log(&format!(
        "apply_registers begin type={} policy={} rows={}",
        req.register_type,
        req.conflict_policy,
        req.rows.len()
    ));
    let conn = state.connection.lock().expect("lock connection").clone();
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
    let payload = serde_json::json!({
      "action": "apply_rows",
      "ip": conn.ip,
      "request": req
    });
    let result = run_python_action(payload).map_err(|e| {
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
fn export_preview_to_excel(
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
    let file_path = app
        .dialog()
        .file()
        .add_filter("Excel", &["xlsx"])
        .set_file_name(&default_name)
        .blocking_save_file();
    let Some(fp) = file_path else {
        gbt_log("export_preview_to_excel user_cancelled_dialog");
        return Ok(CommonResponse {
            ok: false,
            message: "已取消保存".to_string(),
            details: None,
        });
    };
    let output_path = file_path_to_string(fp)?;
    gbt_log(&format!("export_preview_to_excel path_ok len={}", output_path.len()));
    let payload = serde_json::json!({
      "action": "export_excel",
      "registerType": register_type,
      "rows": rows,
      "outputPath": output_path
    });
    let result = run_python_action(payload)?;
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
fn export_template_excel(app: tauri::AppHandle, register_type: String) -> Result<CommonResponse, String> {
    gbt_log(&format!("export_template_excel begin type={register_type}"));
    let default_name = format!("{register_type}_template.xlsx");
    let file_path = app
        .dialog()
        .file()
        .add_filter("Excel", &["xlsx"])
        .set_file_name(&default_name)
        .blocking_save_file();
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
    let result = run_python_action(payload)?;
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

pub fn run() {
    let app_state = AppState {
        connection: Mutex::new(ConnectionState {
            connected: false,
            ip: String::new(),
            message: "未连接".to_string(),
        }),
    };

    tauri::Builder::default()
        .plugin(tauri_plugin_dialog::init())
        .manage(app_state)
        .invoke_handler(tauri::generate_handler![
            connect_robot,
            get_connection_status,
            disconnect_robot,
            get_app_version,
            fetch_robot_meta,
            read_registers,
            apply_registers,
            export_preview_to_excel
            ,
            export_template_excel
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
