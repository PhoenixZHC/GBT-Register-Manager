# GBT Register Manager — 构建说明

本文说明如何从源码在本机构建桌面应用（Tauri 2 + Vue 3 + Python Sidecar）。日常功能说明见 [README.md](README.md)。

## 1. 环境与工具

| 依赖 | 说明 |
|------|------|
| **Windows 10/11（x64）** | 当前仓库脚本与安装包目标以 Windows 为主；`bundle.targets` 为 **MSI**。 |
| **Node.js + npm** | 用于前端与调用 Tauri CLI；建议 LTS 版本。 |
| **Rust（stable）** | `rustc`、`cargo`；Windows 上一般为 **MSVC 工具链**（`x86_64-pc-windows-msvc`）。需安装 **Visual Studio Build Tools**（含 C++ 桌面开发负载）。 |
| **Python 3.9+** | 需加入 `PATH`（`python` 或 `py` 可用）；用于开发期直连 `bridge.py` 及 **PyInstaller 打包 sidecar**。 |
| **WiX Toolset 3.11** | 打 MSI 时 Tauri 会用到；本仓库通过脚本安装到 `%LOCALAPPDATA%\tauri\WixTools314`。 |

可选：若 `.cargo/config.toml` 中配置了国内 crates 镜像，可缓解 `cargo` 拉取依赖较慢的问题；网络正常时也可按需调整或删除该配置。

## 2. 克隆仓库后首次准备

在项目根目录执行：

```powershell
npm install
```

**首次打 MSI 前**（或 `prepare_tauri_tools.ps1` 报找不到 WiX 时），下载并解压 WiX / NSIS 等到本机 Tauri 缓存目录：

```powershell
npm run tauri:download-wix-nsis
```

说明：`download_tauri_wix_nsis_tools.ps1` 内默认使用 `ghproxy.net` 作为 GitHub 下载前缀；若你环境可直连 GitHub，可将脚本中的 `$ghproxy` 改为 `""` 后重新执行。

## 3. 捷勃特 Python SDK（Sidecar 必需）

`python-sidecar/requirements.txt` 会通过 **本地 wheel 路径** 安装 Agilebot SDK。请确保：

- 仓库中存在与 `requirements.txt` 中路径一致的 **wheel 文件**（例如历史上放在 `Python_v2.0.1.0/` 下）；或  
- 将其中 `pip install` 的那一行改为 **你本机实际 wheel 路径 / 私有索引**，再执行 sidecar 构建。

未正确安装 SDK 时，`npm run sidecar:build` 中的 `pip install` 会失败。

## 4. 构建 Python Sidecar（发布安装包前必做）

发布构建（`tauri build`）会把 `externalBin` 指向的 **`gbt-bridge-<target-triple>.exe`** 打进安装包。必须先打出真实可执行文件：

```powershell
npm run sidecar:build
```

等价于：

```powershell
powershell -ExecutionPolicy Bypass -File python-sidecar/build_sidecar.ps1
```

脚本会：安装 `python-sidecar/requirements.txt` 与 `requirements-build.txt`（含 PyInstaller）、按 `gbt_bridge.spec` 生成 `python-sidecar/dist/gbt-bridge.exe`，再根据 `rustc -vV` 的 **host** 三元组复制到：

`src-tauri/binaries/gbt-bridge-<target-triple>.exe`

例如 64 位 Windows 一般为：`gbt-bridge-x86_64-pc-windows-msvc.exe`。

开发模式（`npm run tauri:dev`）下 Rust 会走调试分支，直接调用系统 Python + `python-sidecar/bridge.py`，**不依赖**上述 exe；但 `cargo`/Tauri 仍可能检查 `binaries` 目录占位，详见 `src-tauri/binaries/README.md`。

## 5. 构建正式安装包（MSI）

在已完成 **第 4 节 sidecar 构建** 的前提下，于项目根目录执行：

```powershell
npm run tauri:build
```

该命令会依次：

1. 运行 `scripts/prepare_tauri_tools.ps1`，确认 `%LOCALAPPDATA%\tauri\WixTools314\candle.exe` 存在（不存在则按提示先执行 `npm run tauri:download-wix-nsis`）。  
2. 执行 `beforeBuildCommand`：`npm run build`（`vue-tsc` + `vite build`，输出到 `dist/`）。  
3. 执行 `cargo` 编译并调用 Tauri 打包 **MSI**。

**产物位置**（默认 release）：

- MSI：`src-tauri/target/release/bundle/msi/`

主程序名与版本以 `src-tauri/tauri.conf.json` 中 `productName`、`version` 为准。

## 6. 仅构建前端（不打包桌面）

```powershell
npm run build
```

生成静态资源到 `dist/`，用于检查前端是否能通过类型检查与构建；**不等于**完整桌面应用安装包。

## 7. 开发调试

```powershell
npm run tauri:dev
```

会启动 Vite 开发服务并打开带开发者工具的桌面窗口。需本机 Python 环境与 SDK 可用，以便调试期加载 `bridge.py`。

## 8. 常见问题

**Q：`tauri build` 报找不到 `gbt-bridge-xxx.exe`。**  
A：先执行 `npm run sidecar:build`，并确认 `src-tauri/binaries/` 下文件名与当前 `rustc` host triple 一致。

**Q：打包阶段提示 WiX 未找到。**  
A：执行 `npm run tauri:download-wix-nsis`，确认 `%LOCALAPPDATA%\tauri\WixTools314\candle.exe` 存在后再 `npm run tauri:build`。

**Q：`pip install -r python-sidecar/requirements.txt` 报 wheel 路径不存在。**  
A：按第 3 节补齐 SDK wheel 或修改 `requirements.txt` 中的路径。

**Q：Rust 编译报 MSVC / link 相关错误。**  
A：安装 Visual Studio Build Tools，勾选「使用 C++ 的桌面开发」，并确保在 **x64 Native Tools** 或普通 PowerShell 下使用的工具链一致。

---

若构建流程有变更，请以 `package.json` 中的 `scripts`、`src-tauri/tauri.conf.json` 及 `python-sidecar/build_sidecar.ps1` 为准，并同步更新本文。
