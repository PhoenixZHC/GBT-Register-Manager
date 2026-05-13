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
        return Err(format!(
            "SFTP 密码未配置：请在 src-tauri/src/sftp_export.rs 中设置 {label}"
        ));
    }
    Ok(())
}

fn tcp_connect(host: &str) -> Result<TcpStream, String> {
    let addr: SocketAddr = format!("{host}:{SFTP_PORT}")
        .parse()
        .map_err(|_| format!("无法解析地址: {host}:{SFTP_PORT}"))?;
    TcpStream::connect_timeout(&addr, Duration::from_secs(20))
        .map_err(|e| format!("连接 {host}:{SFTP_PORT} 失败: {e}"))
}

fn ssh_session(host: &str, password: &str) -> Result<Session, String> {
    let tcp = tcp_connect(host)?;
    let mut sess = Session::new().map_err(|e| format!("创建 SSH 会话失败: {e}"))?;
    sess.set_tcp_stream(tcp);
    sess.handshake().map_err(|e| format!("SSH 握手失败: {e}"))?;
    sess.userauth_password(SFTP_USER, password)
        .map_err(|e| format!("SSH 认证失败: {e}"))?;
    if !sess.authenticated() {
        return Err("SSH 认证未通过".into());
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
        return Err("SFTP 密码未配置：请在 src-tauri/src/sftp_export.rs 中设置对应设备的密码常量".into());
    }
    let host = host.trim();
    if host.is_empty() {
        return Err("目标主机 IP 为空".into());
    }
    let sess = ssh_session(host, password)?;
    let cmd = "bash -lc 'cd /opt/python3.12/bin && ./pip3.12 list'";
    let mut channel = sess
        .channel_session()
        .map_err(|e| format!("打开 SSH 通道失败: {e}"))?;
    channel
        .exec(cmd)
        .map_err(|e| format!("执行远程命令失败: {e}"))?;

    let mut stdout = String::new();
    channel
        .read_to_string(&mut stdout)
        .map_err(|e| format!("读取命令输出失败: {e}"))?;

    let mut stderr = String::new();
    channel
        .stderr()
        .read_to_string(&mut stderr)
        .map_err(|e| format!("读取 stderr 失败: {e}"))?;

    channel
        .wait_close()
        .map_err(|e| format!("等待命令结束失败: {e}"))?;

    let code = channel.exit_status().unwrap_or(-1);
    if code != 0 {
        let tail = stderr.trim();
        let hint = if tail.is_empty() {
            stdout.trim().chars().take(120).collect::<String>()
        } else {
            tail.chars().take(200).collect::<String>()
        };
        return Err(format!("pip list 退出码 {code}: {hint}"));
    }

    let full = parse_pip_list_sdk_version(&stdout).ok_or_else(|| {
        format!(
            "pip list 中未找到 {ROBOT_SDK_PIP_PACKAGE}，输出摘要: {}",
            stdout.trim().chars().take(200).collect::<String>()
        )
    })?;
    let display = sdk_version_for_display(&full);
    if display.is_empty() {
        return Err(format!("SDK 版本解析为空（原始: {full}）"));
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
            .map_err(|e| format!("创建本地目录失败 {}: {e}", parent.display()))?;
    }
    let mut remote = sftp
        .open(remote_path)
        .map_err(|e| format!("打开远程文件 {} 失败: {e}", remote_path.display()))?;
    let mut local = File::create(local_path)
        .map_err(|e| format!("创建本地文件 {} 失败: {e}", local_path.display()))?;
    std::io::copy(&mut remote, &mut local)
        .map_err(|e| format!("下载 {} 失败: {e}", remote_path.display()))?;
    Ok(())
}

/// 将 `staging` 目录下所有条目写入 zip，路径为相对于 `staging` 的 POSIX 风格。
/// 同时写入目录条目，保证空目录也能保留在 ZIP 中（修复 robot_data 导出时
/// 空子目录如 `event_history` / `nvram` / `palletizing` / `simulator` 丢失的问题）。
fn zip_staging_dir(staging: &Path, zip_path: &Path) -> Result<(), String> {
    let file = File::create(zip_path).map_err(|e| format!("创建 ZIP 失败: {e}"))?;
    let mut zip = ZipWriter::new(file);
    let opts = FileOptions::default().compression_method(CompressionMethod::Deflated);

    for entry in WalkDir::new(staging).into_iter().filter_map(|e| e.ok()) {
        let rel = entry
            .path()
            .strip_prefix(staging)
            .map_err(|e| format!("路径前缀: {e}"))?;
        let name_in_zip = rel.to_string_lossy().replace('\\', "/");
        if name_in_zip.is_empty() {
            continue;
        }
        let ft = entry.file_type();
        if ft.is_dir() {
            zip.add_directory(name_in_zip.clone(), opts)
                .map_err(|e| format!("ZIP 添加目录 {name_in_zip} 失败: {e}"))?;
            continue;
        }
        if !ft.is_file() {
            continue;
        }
        zip.start_file(name_in_zip.clone(), opts)
            .map_err(|e| format!("ZIP 添加 {name_in_zip} 失败: {e}"))?;
        let mut f =
            File::open(entry.path()).map_err(|e| format!("读取 {name_in_zip} 失败: {e}"))?;
        std::io::copy(&mut f, &mut zip).map_err(|e| format!("写入 ZIP {name_in_zip} 失败: {e}"))?;
    }
    zip.finish().map_err(|e| format!("完成 ZIP 失败: {e}"))?;
    Ok(())
}

fn collect_log_files_from_remote_dir(
    sftp: &Sftp,
    remote_dir: &Path,
    yyyymmdd: &str,
    matches_date: fn(&str, &str) -> bool,
) -> Result<Vec<PathBuf>, String> {
    let mut out = Vec::new();
    let entries = sftp
        .readdir(remote_dir)
        .map_err(|e| format!("列举目录 {} 失败: {e}", remote_dir.display()))?;
    for (path, stat) in entries {
        if stat.is_dir() {
            continue;
        }
        let name = path.file_name().and_then(|n| n.to_str()).unwrap_or("");
        if name == "." || name == ".." {
            continue;
        }
        if matches_date(name, yyyymmdd) {
            out.push(path);
        }
    }
    Ok(out)
}

fn copy_logs_to_staging(
    sftp: &Sftp,
    remote_dirs: &[(&Path, &str, fn(&str, &str) -> bool)],
    yyyymmdd: &str,
    staging: &Path,
) -> Result<usize, String> {
    let mut total = 0usize;
    for (remote_dir, folder_name, matches_date) in remote_dirs {
        let paths = collect_log_files_from_remote_dir(sftp, remote_dir, yyyymmdd, *matches_date)?;
        for remote_path in paths {
            let fname = remote_path
                .file_name()
                .and_then(|n| n.to_str())
                .ok_or_else(|| "远程文件名无效".to_string())?;
            let local = staging.join(folder_name).join(fname);
            download_remote_file(sftp, &remote_path, &local)?;
            total += 1;
        }
    }
    Ok(total)
}

/// 导出控制柜 `/root/log` 与 `/root/app_log` 中指定日期的日志为 ZIP。
pub fn run_export_controller_logs(
    host: &str,
    yyyymmdd: &str,
    zip_path: &Path,
) -> Result<usize, String> {
    ensure_password_set(SFTP_PASSWORD_CONTROLLER, "SFTP_PASSWORD_CONTROLLER")?;
    let sess = ssh_session(host, SFTP_PASSWORD_CONTROLLER)?;
    let sftp = sess.sftp().map_err(|e| format!("打开 SFTP 失败: {e}"))?;

    let staging = tempfile::tempdir().map_err(|e| format!("临时目录: {e}"))?;
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
    let n = copy_logs_to_staging(&sftp, &dirs, yyyymmdd, staging.path())?;
    if n == 0 {
        return Ok(0);
    }
    zip_staging_dir(staging.path(), zip_path)?;
    Ok(n)
}

/// 导出示教器 `/root/app_log` 中指定日期的日志为 ZIP。
pub fn run_export_teach_panel_logs(
    host: &str,
    yyyymmdd: &str,
    zip_path: &Path,
) -> Result<usize, String> {
    ensure_password_set(SFTP_PASSWORD_TEACH_PANEL, "SFTP_PASSWORD_TEACH_PANEL")?;
    let sess = ssh_session(host, SFTP_PASSWORD_TEACH_PANEL)?;
    let sftp = sess.sftp().map_err(|e| format!("打开 SFTP 失败: {e}"))?;

    let staging = tempfile::tempdir().map_err(|e| format!("临时目录: {e}"))?;
    let dirs = [(
        Path::new("/root/app_log"),
        "app_log",
        app_log_basename_matches_calendar_date as fn(&str, &str) -> bool,
    )];
    let n = copy_logs_to_staging(&sftp, &dirs, yyyymmdd, staging.path())?;
    if n == 0 {
        return Ok(0);
    }
    zip_staging_dir(staging.path(), zip_path)?;
    Ok(n)
}

fn mirror_remote_dir(sftp: &Sftp, remote: &Path, local: &Path) -> Result<(), String> {
    std::fs::create_dir_all(local).map_err(|e| format!("mkdir {}: {e}", local.display()))?;
    let entries = sftp
        .readdir(remote)
        .map_err(|e| format!("列举 {} 失败: {e}", remote.display()))?;
    for (path, stat) in entries {
        let name = path.file_name().and_then(|n| n.to_str()).unwrap_or("");
        if name == "." || name == ".." {
            continue;
        }
        let local_child = local.join(name);
        if stat.is_dir() {
            mirror_remote_dir(sftp, &path, &local_child)?;
        } else {
            download_remote_file(sftp, &path, &local_child)?;
        }
    }
    Ok(())
}

/// 递归下载控制柜 `/root/robot_data` 并打包为 ZIP。
pub fn run_export_program_data(host: &str, zip_path: &Path) -> Result<(), String> {
    ensure_password_set(SFTP_PASSWORD_CONTROLLER, "SFTP_PASSWORD_CONTROLLER")?;
    let sess = ssh_session(host, SFTP_PASSWORD_CONTROLLER)?;
    let sftp = sess.sftp().map_err(|e| format!("打开 SFTP 失败: {e}"))?;

    let staging = tempfile::tempdir().map_err(|e| format!("临时目录: {e}"))?;
    let local_root = staging.path().join("robot_data");
    mirror_remote_dir(&sftp, Path::new("/root/robot_data"), &local_root)?;
    zip_staging_dir(staging.path(), zip_path)?;
    Ok(())
}

/// 校验 `YYYY-MM-DD` 并返回 `YYYYMMDD`。
pub fn parse_export_date(date_yyyy_mm_dd: &str) -> Result<String, String> {
    let d = NaiveDate::parse_from_str(date_yyyy_mm_dd.trim(), "%Y-%m-%d")
        .map_err(|_| "日期格式应为 YYYY-MM-DD".to_string())?;
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
