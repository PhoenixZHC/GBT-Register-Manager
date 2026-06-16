//! 控制柜 / 示教器 SFTP 日志与程序数据导出。
//! 发布前请将 `SFTP_USER`、`SFTP_PASSWORD_*` 替换为实机账号（用户名两设备相同，密码分别配置）。

use chrono::NaiveDate;
use ssh2::{Session, Sftp};
use std::fs::File;
use std::io::Read;
use std::net::{SocketAddr, TcpStream};
use std::path::{Path, PathBuf};
use std::time::Duration;
use walkdir::WalkDir;
use zip::write::FileOptions;
use zip::CompressionMethod;
use zip::ZipWriter;

use crate::gbt_log;

const GBT_INTERNAL_ERROR: &str = "GBT_INTERNAL_ERROR";
const GBT_INVALID_EXPORT_DATE: &str = "GBT_INVALID_EXPORT_DATE";

fn sftp_ipc_err(ctx: &str) -> String {
    gbt_log(ctx);
    GBT_INTERNAL_ERROR.to_string()
}

/// SFTP 导出进度：`phase` 为 `scan` | `download` | `zip`；
/// `current`/`total` 为正在处理的文件序号与总数，`done` 为已完成（已下载）数量。
pub type ExportProgressCallback<'a> = Option<&'a mut dyn FnMut(&'static str, usize, usize, usize)>;

fn report_progress(
    cb: &mut ExportProgressCallback<'_>,
    phase: &'static str,
    current: usize,
    total: usize,
    done: usize,
) {
    if let Some(f) = cb {
        f(phase, current, total, done);
    }
}

/// SSH/SFTP 端口（与 WinSCP 默认一致）。
const SFTP_PORT: u16 = 22;

/// 两设备共用的 SSH 用户名。
pub const SFTP_USER: &str = "root";

/// 控制柜 SSH 密码（请替换为实机密码）。
pub const SFTP_PASSWORD_CONTROLLER: &str = "root";

/// 示教器 SSH 密码（请替换为实机密码）。
pub const SFTP_PASSWORD_TEACH_PANEL: &str = "1234";

/// `/root/log` 日志文件名：`YYYYMMDDHHmmss.log`（14 位数字 + `.log`，扩展名大小写不敏感）。
pub fn control_log_basename_matches_calendar_date(name: &str, yyyymmdd: &str) -> bool {
    let lower = name.to_ascii_lowercase();
    let Some(stem) = lower.strip_suffix(".log") else {
        return false;
    };
    if stem.len() != 14 || !stem.chars().all(|c| c.is_ascii_digit()) {
        return false;
    }
    stem.starts_with(yyyymmdd)
}

fn has_date_token(stem: &str, yyyymmdd: &str) -> bool {
    stem.match_indices(yyyymmdd).any(|(idx, _)| {
        let before_is_digit = idx > 0
            && stem[..idx]
                .chars()
                .next_back()
                .is_some_and(|c| c.is_ascii_digit());
        let after_idx = idx + yyyymmdd.len();
        let after_is_digit = after_idx < stem.len()
            && stem[after_idx..]
                .chars()
                .next()
                .is_some_and(|c| c.is_ascii_digit());
        !before_is_digit && !after_is_digit
    })
}

/// `/root/app_log` 日志文件名：服务名 + 日期，可为 `xxx_YYYYMMDD.log` 或 `xxx_YYYYMMDD_HHMMSS.log`。
pub fn app_log_basename_matches_calendar_date(name: &str, yyyymmdd: &str) -> bool {
    let lower = name.to_ascii_lowercase();
    let Some(stem) = lower.strip_suffix(".log") else {
        return false;
    };
    has_date_token(stem, yyyymmdd)
}

fn ensure_password_set(pw: &str, label: &str) -> Result<(), String> {
    if pw.is_empty() {
        return Err(sftp_ipc_err(&format!("SFTP password not configured: {label}")));
    }
    Ok(())
}

fn tcp_connect(host: &str) -> Result<TcpStream, String> {
    let addr: SocketAddr = format!("{host}:{SFTP_PORT}")
        .parse()
        .map_err(|_| sftp_ipc_err(&format!("invalid address: {host}:{SFTP_PORT}")))?;
    TcpStream::connect_timeout(&addr, Duration::from_secs(20))
        .map_err(|e| sftp_ipc_err(&format!("tcp connect {host}:{SFTP_PORT}: {e}")))
}

fn ssh_session(host: &str, password: &str) -> Result<Session, String> {
    let tcp = tcp_connect(host)?;
    let mut sess = Session::new().map_err(|e| sftp_ipc_err(&format!("ssh session new: {e}")))?;
    sess.set_tcp_stream(tcp);
    sess.handshake()
        .map_err(|e| sftp_ipc_err(&format!("ssh handshake {host}: {e}")))?;
    sess.userauth_password(SFTP_USER, password)
        .map_err(|e| sftp_ipc_err(&format!("ssh auth {host}: {e}")))?;
    if !sess.authenticated() {
        return Err(sftp_ipc_err(&format!("ssh auth failed: {host}")));
    }
    Ok(sess)
}

/// 控制柜 / 示教器上机器人 Python SDK 包名（`pip list` 输出第一列）。
const ROBOT_SDK_PIP_PACKAGE: &str = "Agilebot.Robot.SDK.A";

/// 从 `pip list` 输出中取 SDK 的完整版本字符串（可含 `+local`）。
fn parse_pip_list_sdk_version(stdout: &str) -> Option<String> {
    for line in stdout.lines() {
        let line = line.trim();
        if line.is_empty() || line.starts_with("---") {
            continue;
        }
        // 表头行，如 "Package Version"
        let lower = line.to_ascii_lowercase();
        if lower.starts_with("package") && lower.contains("version") {
            continue;
        }
        let mut parts = line.split_whitespace();
        let name = parts.next()?;
        if name != ROBOT_SDK_PIP_PACKAGE {
            continue;
        }
        let rest: String = parts.collect::<Vec<_>>().join(" ");
        let v = rest.trim();
        if !v.is_empty() {
            return Some(v.to_string());
        }
    }
    None
}

/// 界面展示用：只保留 PEP 440 主版本段，去掉 `+` 及之后的本地版本（如 `2.0.1.0+0998ac28...` → `2.0.1.0`）。
fn sdk_version_for_display(full: &str) -> String {
    full.trim()
        .split('+')
        .next()
        .unwrap_or("")
        .trim()
        .to_string()
}

/// 通过 SSH 在指定主机执行与手操一致的 `cd /opt/python3.12/bin && ./pip3.12 list`，
/// 从列表中解析 `Agilebot.Robot.SDK.A` 版本；返回值为**展示用**（无 `+` 后缀）。
/// `password` 须与控制柜或示教器上 `root` 账号一致（见本文件顶部常量）。
pub fn fetch_agilebot_sdk_version(host: &str, password: &str) -> Result<String, String> {
    if password.is_empty() {
        return Err(sftp_ipc_err("SFTP password not configured for SDK version fetch"));
    }
    let host = host.trim();
    if host.is_empty() {
        return Err(sftp_ipc_err("SDK version fetch host is empty"));
    }
    let sess = ssh_session(host, password)?;
    let cmd = "bash -lc 'cd /opt/python3.12/bin && ./pip3.12 list'";
    let mut channel = sess
        .channel_session()
        .map_err(|e| sftp_ipc_err(&format!("ssh channel open {host}: {e}")))?;
    channel
        .exec(cmd)
        .map_err(|e| sftp_ipc_err(&format!("ssh exec pip list {host}: {e}")))?;

    let mut stdout = String::new();
    channel
        .read_to_string(&mut stdout)
        .map_err(|e| sftp_ipc_err(&format!("read pip list stdout {host}: {e}")))?;

    let mut stderr = String::new();
    channel
        .stderr()
        .read_to_string(&mut stderr)
        .map_err(|e| sftp_ipc_err(&format!("read pip list stderr {host}: {e}")))?;

    channel
        .wait_close()
        .map_err(|e| sftp_ipc_err(&format!("wait pip list close {host}: {e}")))?;

    let code = channel.exit_status().unwrap_or(-1);
    if code != 0 {
        let tail = stderr.trim();
        let hint = if tail.is_empty() {
            stdout.trim().chars().take(120).collect::<String>()
        } else {
            tail.chars().take(200).collect::<String>()
        };
        return Err(sftp_ipc_err(&format!("pip list exit {code} on {host}: {hint}")));
    }

    let full = parse_pip_list_sdk_version(&stdout).ok_or_else(|| {
        sftp_ipc_err(&format!(
            "pip list missing {ROBOT_SDK_PIP_PACKAGE} on {host}: {}",
            stdout.trim().chars().take(200).collect::<String>()
        ))
    })?;
    let display = sdk_version_for_display(&full);
    if display.is_empty() {
        return Err(sftp_ipc_err(&format!("empty SDK version parsed from: {full}")));
    }
    Ok(display)
}

#[cfg(test)]
mod sdk_version_tests {
    use super::{parse_pip_list_sdk_version, sdk_version_for_display};

    #[test]
    fn sdk_version_for_display_strips_plus_local() {
        assert_eq!(
            sdk_version_for_display("2.0.1.0+0998ac28.20260130"),
            "2.0.1.0"
        );
        assert_eq!(sdk_version_for_display("2.0.1.0"), "2.0.1.0");
        assert_eq!(sdk_version_for_display("  1.0.0+abc  "), "1.0.0");
    }

    #[test]
    fn parse_pip_list_finds_package() {
        let out = "\
Package    Version
---------- -------
foo 1.0
Agilebot.Robot.SDK.A 2.0.1.0+0998ac28.20260130
bar 2.0
";
        let full = parse_pip_list_sdk_version(out).expect("parse");
        assert_eq!(full, "2.0.1.0+0998ac28.20260130");
        assert_eq!(sdk_version_for_display(&full), "2.0.1.0");
    }
}

fn download_remote_file(sftp: &Sftp, remote_path: &Path, local_path: &Path) -> Result<(), String> {
    if let Some(parent) = local_path.parent() {
        std::fs::create_dir_all(parent)
            .map_err(|e| sftp_ipc_err(&format!("mkdir {}: {e}", parent.display())))?;
    }
    let mut remote = sftp
        .open(remote_path)
        .map_err(|e| sftp_ipc_err(&format!("open remote {}: {e}", remote_path.display())))?;
    let mut local = File::create(local_path)
        .map_err(|e| sftp_ipc_err(&format!("create local {}: {e}", local_path.display())))?;
    std::io::copy(&mut remote, &mut local)
        .map_err(|e| sftp_ipc_err(&format!("download {}: {e}", remote_path.display())))?;
    Ok(())
}

/// 将 `staging` 目录下所有条目写入 zip，路径为相对于 `staging` 的 POSIX 风格。
/// 同时写入目录条目，保证空目录也能保留在 ZIP 中（修复 robot_data 导出时
/// 空子目录如 `event_history` / `nvram` / `palletizing` / `simulator` 丢失的问题）。
fn zip_staging_dir(staging: &Path, zip_path: &Path) -> Result<(), String> {
    let file = File::create(zip_path).map_err(|e| sftp_ipc_err(&format!("create zip: {e}")))?;
    let mut zip = ZipWriter::new(file);
    let opts = FileOptions::default().compression_method(CompressionMethod::Deflated);

    for entry in WalkDir::new(staging).into_iter().filter_map(|e| e.ok()) {
        let rel = entry
            .path()
            .strip_prefix(staging)
            .map_err(|e| sftp_ipc_err(&format!("zip strip_prefix: {e}")))?;
        let name_in_zip = rel.to_string_lossy().replace('\\', "/");
        if name_in_zip.is_empty() {
            continue;
        }
        let ft = entry.file_type();
        if ft.is_dir() {
            zip.add_directory(name_in_zip.clone(), opts)
                .map_err(|e| sftp_ipc_err(&format!("zip add dir {name_in_zip}: {e}")))?;
            continue;
        }
        if !ft.is_file() {
            continue;
        }
        zip.start_file(name_in_zip.clone(), opts)
            .map_err(|e| sftp_ipc_err(&format!("zip start {name_in_zip}: {e}")))?;
        let mut f =
            File::open(entry.path()).map_err(|e| sftp_ipc_err(&format!("zip read {name_in_zip}: {e}")))?;
        std::io::copy(&mut f, &mut zip)
            .map_err(|e| sftp_ipc_err(&format!("zip write {name_in_zip}: {e}")))?;
    }
    zip.finish().map_err(|e| sftp_ipc_err(&format!("zip finish: {e}")))?;
    Ok(())
}

fn copy_logs_to_staging(
    sftp: &Sftp,
    remote_dirs: &[(&Path, &str, fn(&str, &str) -> bool)],
    yyyymmdd: &str,
    staging: &Path,
    on_progress: &mut ExportProgressCallback<'_>,
) -> Result<usize, String> {
    // 先扫描出所有匹配日期的文件，得到总数后再逐个下载，
    // 这样前端能显示“导出中 i/N，已导出 j”而不是只有递增的当前数。
    report_progress(on_progress, "scan", 0, 0, 0);
    let mut files: Vec<(PathBuf, PathBuf)> = Vec::new();
    for (remote_dir, folder_name, matches_date) in remote_dirs {
        let entries = sftp
            .readdir(remote_dir)
            .map_err(|e| sftp_ipc_err(&format!("readdir {}: {e}", remote_dir.display())))?;
        for (path, stat) in entries {
            if stat.is_dir() {
                continue;
            }
            let name = path.file_name().and_then(|n| n.to_str()).unwrap_or("");
            if name == "." || name == ".." {
                continue;
            }
            if !matches_date(name, yyyymmdd) {
                continue;
            }
            let local_path = staging.join(folder_name).join(name);
            files.push((path, local_path));
        }
    }

    let total = files.len();
    report_progress(on_progress, "scan", 0, total, 0);

    let mut downloaded = 0usize;
    for (remote_path, local_path) in &files {
        // 下载当前文件之前先上报：current=正在下载的序号，done=此前已完成数量。
        report_progress(on_progress, "download", downloaded + 1, total, downloaded);
        download_remote_file(sftp, remote_path, local_path)?;
        downloaded += 1;
    }
    if total > 0 {
        report_progress(on_progress, "download", total, total, downloaded);
    }
    Ok(downloaded)
}

/// 导出控制柜 `/root/log` 与 `/root/app_log` 中指定日期的日志为 ZIP。
pub fn run_export_controller_logs(
    host: &str,
    yyyymmdd: &str,
    zip_path: &Path,
    on_progress: &mut ExportProgressCallback<'_>,
) -> Result<usize, String> {
    ensure_password_set(SFTP_PASSWORD_CONTROLLER, "SFTP_PASSWORD_CONTROLLER")?;
    let sess = ssh_session(host, SFTP_PASSWORD_CONTROLLER)?;
    let sftp = sess.sftp().map_err(|e| sftp_ipc_err(&format!("open sftp {host}: {e}")))?;

    let staging = tempfile::tempdir().map_err(|e| sftp_ipc_err(&format!("tempdir: {e}")))?;
    let dirs = [
        (
            Path::new("/root/log"),
            "log",
            control_log_basename_matches_calendar_date as fn(&str, &str) -> bool,
        ),
        (
            Path::new("/root/app_log"),
            "app_log",
            app_log_basename_matches_calendar_date as fn(&str, &str) -> bool,
        ),
    ];
    let n = copy_logs_to_staging(&sftp, &dirs, yyyymmdd, staging.path(), on_progress)?;
    if n == 0 {
        return Ok(0);
    }
    report_progress(on_progress, "zip", n, n, n);
    zip_staging_dir(staging.path(), zip_path)?;
    Ok(n)
}

/// 导出示教器 `/root/app_log` 中指定日期的日志为 ZIP。
pub fn run_export_teach_panel_logs(
    host: &str,
    yyyymmdd: &str,
    zip_path: &Path,
    on_progress: &mut ExportProgressCallback<'_>,
) -> Result<usize, String> {
    ensure_password_set(SFTP_PASSWORD_TEACH_PANEL, "SFTP_PASSWORD_TEACH_PANEL")?;
    let sess = ssh_session(host, SFTP_PASSWORD_TEACH_PANEL)?;
    let sftp = sess.sftp().map_err(|e| sftp_ipc_err(&format!("open sftp {host}: {e}")))?;

    let staging = tempfile::tempdir().map_err(|e| sftp_ipc_err(&format!("tempdir: {e}")))?;
    let dirs = [(
        Path::new("/root/app_log"),
        "app_log",
        app_log_basename_matches_calendar_date as fn(&str, &str) -> bool,
    )];
    let n = copy_logs_to_staging(&sftp, &dirs, yyyymmdd, staging.path(), on_progress)?;
    if n == 0 {
        return Ok(0);
    }
    report_progress(on_progress, "zip", n, n, n);
    zip_staging_dir(staging.path(), zip_path)?;
    Ok(n)
}

/// 递归下载控制柜 `/root/robot_data` 并打包为 ZIP（先扫描整棵目录树得到总数，再逐个下载，
/// 以便前端显示“导出中 i/N，已导出 j”；空目录会被保留以维持 ZIP 结构完整）。
pub fn run_export_program_data(
    host: &str,
    zip_path: &Path,
    on_progress: &mut ExportProgressCallback<'_>,
) -> Result<usize, String> {
    ensure_password_set(SFTP_PASSWORD_CONTROLLER, "SFTP_PASSWORD_CONTROLLER")?;
    let sess = ssh_session(host, SFTP_PASSWORD_CONTROLLER)?;
    let sftp = sess.sftp().map_err(|e| sftp_ipc_err(&format!("open sftp {host}: {e}")))?;

    let remote_root = Path::new("/root/robot_data");
    let staging = tempfile::tempdir().map_err(|e| sftp_ipc_err(&format!("tempdir: {e}")))?;
    let local_root = staging.path().join("robot_data");

    // 第一步：递归扫描整棵目录树，收集所有文件与目录（含空目录），得到总数。
    report_progress(on_progress, "scan", 0, 0, 0);
    let mut files: Vec<(PathBuf, PathBuf)> = Vec::new();
    let mut dirs: Vec<PathBuf> = Vec::new();
    scan_remote_tree(&sftp, remote_root, &local_root, &mut files, &mut dirs)?;

    // 第二步：先创建所有目录（保留空目录），再逐个下载文件并上报进度。
    std::fs::create_dir_all(&local_root)
        .map_err(|e| sftp_ipc_err(&format!("mkdir {}: {e}", local_root.display())))?;
    for dir in &dirs {
        std::fs::create_dir_all(dir)
            .map_err(|e| sftp_ipc_err(&format!("mkdir {}: {e}", dir.display())))?;
    }

    let total = files.len();
    report_progress(on_progress, "scan", 0, total, 0);

    let mut downloaded = 0usize;
    for (remote_path, local_path) in &files {
        report_progress(on_progress, "download", downloaded + 1, total, downloaded);
        download_remote_file(&sftp, remote_path, local_path)?;
        downloaded += 1;
    }
    if total > 0 {
        report_progress(on_progress, "download", total, total, downloaded);
    }

    report_progress(on_progress, "zip", downloaded.max(1), downloaded.max(1), downloaded);
    zip_staging_dir(staging.path(), zip_path)?;
    Ok(downloaded)
}

/// 递归列举远端目录树：收集文件 `(remote, local)` 与所有子目录的本地路径（含空目录）。
fn scan_remote_tree(
    sftp: &Sftp,
    remote: &Path,
    local: &Path,
    files: &mut Vec<(PathBuf, PathBuf)>,
    dirs: &mut Vec<PathBuf>,
) -> Result<(), String> {
    let entries = sftp
        .readdir(remote)
        .map_err(|e| sftp_ipc_err(&format!("readdir {}: {e}", remote.display())))?;
    for (path, stat) in entries {
        let name = path.file_name().and_then(|n| n.to_str()).unwrap_or("");
        if name == "." || name == ".." {
            continue;
        }
        let local_child = local.join(name);
        if stat.is_dir() {
            dirs.push(local_child.clone());
            scan_remote_tree(sftp, &path, &local_child, files, dirs)?;
        } else {
            files.push((path, local_child));
        }
    }
    Ok(())
}

/// 校验 `YYYY-MM-DD` 并返回 `YYYYMMDD`。
pub fn parse_export_date(date_yyyy_mm_dd: &str) -> Result<String, String> {
    let d = NaiveDate::parse_from_str(date_yyyy_mm_dd.trim(), "%Y-%m-%d")
        .map_err(|_| GBT_INVALID_EXPORT_DATE.to_string())?;
    Ok(d.format("%Y%m%d").to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn control_log_name_matches_day() {
        assert!(control_log_basename_matches_calendar_date(
            "20260429094606.log",
            "20260429"
        ));
        assert!(!control_log_basename_matches_calendar_date(
            "20260428120000.log",
            "20260429"
        ));
        assert!(!control_log_basename_matches_calendar_date(
            "controller_routine_service_20260429_094606.log",
            "20260429"
        ));
        assert!(!control_log_basename_matches_calendar_date(
            "bad.log", "20260429"
        ));
        assert!(!control_log_basename_matches_calendar_date(
            "20260429094606.txt",
            "20260429"
        ));
    }

    #[test]
    fn app_log_name_matches_day() {
        assert!(app_log_basename_matches_calendar_date(
            "controller_routine_service_20260511_200449.log",
            "20260511"
        ));
        assert!(app_log_basename_matches_calendar_date(
            "charcoal_active_alarm_service_20260511.log",
            "20260511"
        ));
        assert!(!app_log_basename_matches_calendar_date(
            "controller_routine_service_20260509_182321.log",
            "20260511"
        ));
        assert!(!app_log_basename_matches_calendar_date(
            "service_202605111.log",
            "20260511"
        ));
    }
}
