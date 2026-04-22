# Tauri externalBin placeholder

Tauri 的 `bundle.externalBin` 会在构建期检查 `gbt-bridge-<target-triple>.exe` 是否存在；如果不存在，`cargo check` / `tauri build` 会直接失败。

- **开发期**（`cargo run` / `tauri dev`）：Rust 代码会走 `cfg(debug_assertions)` 分支，直接调用系统 `python` + `python-sidecar/bridge.py`，**不会执行**此目录下的 exe——因此**零字节占位文件即可让检查通过**。
- **发布期**（`tauri build`）：必须先执行 `npm run sidecar:build`（或 `powershell -ExecutionPolicy Bypass -File python-sidecar/build_sidecar.ps1`）生成真实的 `gbt-bridge-<target-triple>.exe`，否则安装包里的 sidecar 将为空文件而无法运行。

命名约定（Tauri externalBin 规则，按 `rustc -vV` 的 host triple 决定）：

- Windows x64：`gbt-bridge-x86_64-pc-windows-msvc.exe`
- Windows ARM64：`gbt-bridge-aarch64-pc-windows-msvc.exe`
- Linux x64：`gbt-bridge-x86_64-unknown-linux-gnu`
- macOS x64：`gbt-bridge-x86_64-apple-darwin`
- macOS ARM64：`gbt-bridge-aarch64-apple-darwin`
