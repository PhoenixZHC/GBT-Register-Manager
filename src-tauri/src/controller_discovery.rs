//! 按需运行发现 Sidecar；与机器人连接和读写进程隔离。
use serde_json::{json, Value};
use std::io::{BufRead, BufReader, Read, Write};
use std::process::{Command, Stdio};
use std::sync::{atomic::{AtomicBool, Ordering}, mpsc, Arc, Mutex};
use std::time::{Duration, Instant};
use tauri::{Emitter, Manager, State};

struct Task {
    id: String,
    cancel: Arc<AtomicBool>,
    done: Arc<AtomicBool>,
}

#[derive(Default)]
pub struct DiscoveryState(Mutex<Option<Task>>);

struct Frames {
    limit: usize,
    active: bool,
    body: String,
}

impl Default for Frames {
    fn default() -> Self { Self { active: false, body: String::new(), limit: 65536 } }
}

impl Frames {
    fn feed(&mut self, line: &str) -> Result<Option<Value>, String> {
        match line.trim() {
            "<<<GBT-BEGIN>>>" => {
                if self.active { return Err("protocol".into()); }
                self.active = true;
                self.body.clear();
            }
            "<<<GBT-END>>>" => {
                if !self.active { return Err("protocol".into()); }
                self.active = false;
                return serde_json::from_str(&self.body).map(Some).map_err(|_| "protocol".into());
            }
            _ if self.active => {
                if self.body.len() + line.len() > self.limit { return Err("protocol".into()); }
                self.body.push_str(line);
            }
            _ => {} // SDK 日志不属于协议帧。
        }
        Ok(None)
    }
}

pub(crate) fn execute_robot(command: Command, payload: Value, cancel: Arc<AtomicBool>, timeout: Duration, event: impl FnMut(Value)) -> Result<Value, String> {
    execute_bounded(command, payload, cancel, timeout, event, 64 * 1024 * 1024)
}

fn execute(command: Command, payload: Value, cancel: Arc<AtomicBool>, timeout: Duration, event: impl FnMut(Value)) -> Result<Value, String> {
    execute_bounded(command, payload, cancel, timeout, event, 65536)
}

fn execute_bounded(
    mut command: Command,
    payload: Value,
    cancel: Arc<AtomicBool>,
    timeout: Duration,
    mut event: impl FnMut(Value),
    frame_limit: usize,
) -> Result<Value, String> {
    if cancel.load(Ordering::SeqCst) { return Err("cancelled".into()); }
    #[cfg(windows)] {
        use std::os::windows::process::CommandExt;
        use windows_sys::Win32::System::Threading::CREATE_SUSPENDED;
        command.creation_flags(crate::CREATE_NO_WINDOW | CREATE_SUSPENDED);
    }
    let mut child = command.stdin(Stdio::piped()).stdout(Stdio::piped()).stderr(Stdio::piped())
        .spawn().map_err(|e| { crate::gbt_log(&format!("discovery spawn: {e}")); "component_missing".to_string() })?;
    #[cfg(windows)]
    let job = match crate::discovery_job::Job::attach_and_resume(&child) {
        Ok(job) => job,
        Err(error) => { let _ = child.kill(); let _ = child.wait(); return Err(error); }
    };
    let mut input = child.stdin.take().expect("piped stdin");
    // 后台写入，避免大请求或卡住的 Sidecar 在写管道时绕过超时／取消。
    let writer = std::thread::spawn(move || input.write_all(payload.to_string().as_bytes()));
    let stdout = child.stdout.take().expect("piped stdout");
    let stderr = child.stderr.take().expect("piped stderr");
    let log_reader = std::thread::spawn(move || {
        let mut reader = BufReader::new(stderr);
        loop {
            let mut line = Vec::new();
            match (&mut reader).take(8192).read_until(b'\n', &mut line) {
                Ok(0) | Err(_) => break,
                Ok(_) => crate::gbt_log(&format!("discovery: {}", String::from_utf8_lossy(&line).trim())),
            }
        }
    });
    let (tx, rx) = mpsc::sync_channel(256);
    let reader = std::thread::spawn(move || {
        let mut reader = BufReader::new(stdout);
        loop {
            let mut line = Vec::new();
            match (&mut reader).take(frame_limit as u64 + 1).read_until(b'\n', &mut line) {
                Ok(0) => break,
                Ok(_) if line.len() <= frame_limit => {
                    if tx.send(String::from_utf8(line).map_err(|_| "protocol".to_string())).is_err() { break; }
                }
                _ => { let _ = tx.send(Err("protocol".into())); break; }
            }
        }
    });
    let started = Instant::now();
    let mut frames = Frames { limit: frame_limit, ..Frames::default() };
    let mut last = None;
    let mut terminal = None;
    let mut exited: Option<bool> = None;
    let result = 'run: loop {
        if cancel.load(Ordering::SeqCst) { break Err("cancelled".into()); }
        if started.elapsed() > timeout { break Err("timeout".into()); }
        // 有界消费，避免异常输出阻塞取消检查。
        for _ in 0..128 {
            match rx.try_recv() {
                Ok(Ok(line)) => match frames.feed(&line) {
                    Ok(Some(value)) => {
                        match value["kind"].as_str() {
                            Some("device" | "warning" | "progress" | "interfaces") => event(value.clone()),
                            Some("finished" | "error") => terminal = Some(value.clone()),
                            _ => last = Some(value),
                        }
                    }
                    Ok(None) => {}
                    Err(e) => break 'run Err(e),
                },
                Ok(Err(e)) => break 'run Err(e),
                Err(mpsc::TryRecvError::Empty) => break,
                Err(mpsc::TryRecvError::Disconnected) => {
                    if let Some(status) = exited {
                        if !status { break 'run Err("process_failed".into()); }
                        if frames.active { break 'run Err("protocol".into()); }
                        break 'run terminal.or(last).ok_or_else(|| "protocol".into());
                    }
                    break;
                }
            }
        }
        match child.try_wait() {
            Ok(Some(status)) => exited = Some(status.success()),
            Ok(None) => {}
            Err(_) => break Err("process_failed".into()),
        }
        std::thread::sleep(Duration::from_millis(20));
    };
    // 关闭通道唤醒可能等待发送的读取线程，再回收唯一的扫描子进程。
    drop(rx);
    #[cfg(windows)]
    drop(job);
    if exited.is_none() { let _ = child.kill(); }
    let _ = child.wait();
    let _ = reader.join();
    let _ = log_reader.join();
    if !matches!(writer.join(), Ok(Ok(()))) && result.is_ok() { return Err("protocol".into()); }
    result
}

fn command() -> Result<Command, String> {
    Ok(crate::build_sidecar_command(&crate::resolve_sidecar().map_err(|_| "component_missing".to_string())?))
}

fn reserve(state: &DiscoveryState, id: &str) -> Result<(Arc<AtomicBool>, Arc<AtomicBool>), String> {
    let mut slot = state.0.lock().map_err(|_| "internal")?;
    if slot.as_ref().is_some_and(|task| !task.done.load(Ordering::SeqCst)) { return Err("busy".into()); }
    let cancel = Arc::new(AtomicBool::new(false));
    let done = Arc::new(AtomicBool::new(false));
    *slot = Some(Task { id: id.into(), cancel: cancel.clone(), done: done.clone() });
    Ok((cancel, done))
}

#[tauri::command]
pub async fn check_controller_discovery(app: crate::AppHandle, state: State<'_, DiscoveryState>) -> Result<Value, String> {
    let (cancel, done) = reserve(&state, "check")?;
    tauri::async_runtime::spawn_blocking(move || {
        let result = command().and_then(|cmd| execute(cmd, json!({"action":"check_discovery"}), cancel, Duration::from_secs(20), |_| {}));
        done.store(true, Ordering::SeqCst);
        drop(app);
        result.and_then(|value| {
            if value["status"].is_string() && value["interfaces"].is_array() && value["warnings"].is_array() {
                Ok(value)
            } else { Err("protocol".into()) }
        })
    }).await.map_err(|_| "internal".to_string())?
}

#[tauri::command(rename_all = "camelCase")]
pub fn start_controller_discovery(app: crate::AppHandle, state: State<'_, DiscoveryState>, scan_id: String) -> Result<(), String> {
    if scan_id.is_empty() || scan_id == "check" || scan_id.len() > 80 {
        return Err("invalid_request".into());
    }
    let command = command()?;
    let (cancel, done) = reserve(&state, &scan_id)?;
    std::thread::spawn(move || {
        let send = |mut value: Value| {
            value["scanId"] = json!(scan_id);
            let _ = app.emit("controller-discovery-event", value);
        };
        let result = execute(command, json!({"action":"discover_controllers"}), cancel,
            Duration::from_secs(150), &send);
        // 必须先完成进程回收，再允许新任务开始。
        done.store(true, Ordering::SeqCst);
        match result {
            Ok(value) if matches!(value["kind"].as_str(), Some("finished" | "error")) => send(value),
            Ok(_) => send(json!({"kind":"error", "code":"protocol"})),
            Err(code) if code == "cancelled" => send(json!({"kind":"finished", "reason":"cancelled"})),
            Err(code) => send(json!({"kind":"error", "code":code})),
        }
    });
    Ok(())
}

#[tauri::command(rename_all = "camelCase")]
pub async fn cancel_controller_discovery(state: State<'_, DiscoveryState>, scan_id: String) -> Result<(), String> {
    let done = {
        let slot = state.0.lock().map_err(|_| "internal")?;
        match slot.as_ref().filter(|task| task.id == scan_id) {
            Some(task) => { task.cancel.store(true, Ordering::SeqCst); Some(task.done.clone()) }
            None => None,
        }
    };
    if let Some(done) = done {
        tauri::async_runtime::spawn_blocking(move || {
            let started = Instant::now();
            while !done.load(Ordering::SeqCst) {
                if started.elapsed() > Duration::from_secs(5) { return Err("timeout".to_string()); }
                std::thread::sleep(Duration::from_millis(20));
            }
            Ok(())
        }).await.map_err(|_| "internal".to_string())??;
    }
    Ok(())
}

pub fn shutdown(app: &crate::AppHandle) {
    let state = app.state::<DiscoveryState>();
    if let Ok(slot) = state.0.lock() {
        if let Some(task) = slot.as_ref() {
            task.cancel.store(true, Ordering::SeqCst);
            let started = Instant::now();
            while !task.done.load(Ordering::SeqCst) && started.elapsed() < Duration::from_secs(5) {
                std::thread::sleep(Duration::from_millis(20));
            }
        }
    };
}

#[tauri::command]
pub fn open_npcap_download() -> Result<(), String> {
    #[cfg(windows)] {
        // 固定地址，不接受来自网络回复或界面的任意命令参数。
        use std::os::windows::process::CommandExt;
        Command::new("rundll32.exe").args(["url.dll,FileProtocolHandler", "https://npcap.com/#download"])
            .creation_flags(crate::CREATE_NO_WINDOW).spawn().map_err(|_| "unavailable".to_string())?;
        Ok(())
    }
    #[cfg(not(windows))] { Err("unsupported".into()) }
}

#[cfg(test)]
mod tests {
    use super::*;
    #[test]
    fn frame_noise_and_bad_json() {
        let mut frames = Frames::default();
        assert!(frames.feed("SDK noise").unwrap().is_none());
        frames.feed("<<<GBT-BEGIN>>>").unwrap();
        frames.feed("{\"kind\":\"device\"}").unwrap();
        assert_eq!(frames.feed("<<<GBT-END>>>").unwrap().unwrap()["kind"], "device");
        assert!(frames.feed("<<<GBT-END>>>").is_err());
        frames.feed("<<<GBT-BEGIN>>>").unwrap();
        frames.feed("broken").unwrap();
        assert!(frames.feed("<<<GBT-END>>>").is_err());
    }
    #[test]
    fn bounded_frames() {
        let mut frames = Frames::default();
        frames.feed("<<<GBT-BEGIN>>>").unwrap();
        assert!(frames.feed(&"x".repeat(65537)).is_err());
    }
    #[test]
    fn reserve_serializes_check_and_scan() {
        let state = DiscoveryState::default();
        let (_, done) = reserve(&state, "one").unwrap();
        assert!(reserve(&state, "two").is_err());
        done.store(true, Ordering::SeqCst);
        assert!(reserve(&state, "two").is_ok());
    }

    fn python(script: &str) -> Command {
        let mut command = Command::new(std::path::Path::new(env!("CARGO_MANIFEST_DIR")).join("../.venv/Scripts/python.exe"));
        command.args(["-c", script]);
        command
    }
    #[test]
    fn process_stream_and_terminal_after_exit() {
        let cmd = python("import sys; sys.stdin.read(); print('<<<GBT-BEGIN>>>\\n{\"kind\":\"interfaces\",\"interfaces\":[{\"id\":\"new-usb\"}]}\\n<<<GBT-END>>>'); print('<<<GBT-BEGIN>>>\\n{\"kind\":\"device\"}\\n<<<GBT-END>>>'); print('<<<GBT-BEGIN>>>\\n{\"kind\":\"finished\",\"reason\":\"timeout\"}\\n<<<GBT-END>>>')");
        let mut events = Vec::new();
        let result = execute(cmd, json!({}), Arc::new(AtomicBool::new(false)), Duration::from_secs(5), |v| events.push(v)).unwrap();
        assert_eq!(events.len(), 2);
        assert_eq!(events[0]["interfaces"][0]["id"], "new-usb");
        assert_eq!(result["kind"], "finished");
    }
    #[test]
    fn robot_progress_and_large_result_are_preserved() {
        let cmd = python("import sys,json; sys.stdin.read(); print('<<<GBT-BEGIN>>>\\n{\"kind\":\"progress\",\"current\":1}\\n<<<GBT-END>>>'); print('<<<GBT-BEGIN>>>\\n'+json.dumps({'rows':['x'*70000]})+'\\n<<<GBT-END>>>')");
        let mut events = Vec::new();
        let result = execute_robot(cmd, json!({}), Arc::new(AtomicBool::new(false)), Duration::from_secs(5), |v| events.push(v)).unwrap();
        assert_eq!(events.len(), 1);
        assert_eq!(result["rows"][0].as_str().unwrap().len(), 70000);
    }
    #[test]
    fn robot_timeout_releases_runner_for_next_operation() {
        let result = execute_robot(python("import sys,time; sys.stdin.read(); time.sleep(30)"), json!({}), Arc::new(AtomicBool::new(false)), Duration::from_millis(150), |_| {});
        assert_eq!(result.unwrap_err(), "timeout");
        let result = execute_robot(python("import sys; sys.stdin.read(); print('<<<GBT-BEGIN>>>\\n{\"ok\":true}\\n<<<GBT-END>>>')"), json!({}), Arc::new(AtomicBool::new(false)), Duration::from_secs(5), |_| {}).unwrap();
        assert_eq!(result["ok"], true);
    }
    #[test]
    fn abnormal_exit_is_error() {
        let result = execute(python("import sys; sys.stdin.read(); sys.exit(7)"), json!({}), Arc::new(AtomicBool::new(false)), Duration::from_secs(5), |_| {});
        assert_eq!(result.unwrap_err(), "process_failed");
    }
    #[test]
    fn timeout_kills_and_reaps_process() {
        let start = Instant::now();
        let result = execute(python("import sys,time; sys.stdin.read(); time.sleep(30)"), json!({}), Arc::new(AtomicBool::new(false)), Duration::from_millis(150), |_| {});
        assert_eq!(result.unwrap_err(), "timeout");
        assert!(start.elapsed() < Duration::from_secs(3));
    }
    #[test]
    fn cancellation_kills_and_reaps_process() {
        let cancel = Arc::new(AtomicBool::new(false));
        let flag = cancel.clone();
        let signal = std::thread::spawn(move || { std::thread::sleep(Duration::from_millis(200)); flag.store(true, Ordering::SeqCst); });
        let result = execute(python("import sys,time; sys.stdin.read(); time.sleep(30)"), json!({}), cancel, Duration::from_secs(5), |_| {});
        signal.join().unwrap();
        assert_eq!(result.unwrap_err(), "cancelled");
    }
    #[cfg(windows)]
    #[test]
    fn cancellation_reaps_descendant_with_inherited_pipes() {
        let cancel = Arc::new(AtomicBool::new(false));
        let flag = cancel.clone();
        let mut pid = 0;
        let script = "import sys,subprocess,json,time; sys.stdin.read(); p=subprocess.Popen([sys.executable,'-c','import time; time.sleep(30)'],creationflags=0x08000000); print('<<<GBT-BEGIN>>>\\n'+json.dumps({'kind':'device','pid':p.pid})+'\\n<<<GBT-END>>>',flush=True); time.sleep(30)";
        let started = Instant::now();
        let result = execute(python(script), json!({}), cancel, Duration::from_secs(5), |v| {
            pid = v["pid"].as_u64().unwrap_or(0) as u32;
            flag.store(true, Ordering::SeqCst);
        });
        assert_eq!(result.unwrap_err(), "cancelled");
        assert!(pid > 0);
        assert!(started.elapsed() < Duration::from_secs(3));
        unsafe {
            use windows_sys::Win32::System::Threading::{OpenProcess, GetExitCodeProcess, PROCESS_QUERY_LIMITED_INFORMATION};
            let handle = OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, 0, pid);
            if !handle.is_null() {
                let mut code = 259;
                assert_ne!(GetExitCodeProcess(handle, &mut code), 0);
                windows_sys::Win32::Foundation::CloseHandle(handle);
                assert_ne!(code, 259, "child process still active");
            }
        }
    }
    #[test]
    fn real_sidecar_dependency_check_returns_structured_status() {
        let result = execute(command().unwrap(), json!({"action":"check_discovery"}), Arc::new(AtomicBool::new(false)), Duration::from_secs(20), |_| {}).unwrap();
        assert!(result["status"].is_string());
        assert!(result["interfaces"].is_array());
        assert!(result["warnings"].is_array());
    }
}
