# GBT Register Manager — 构建说明

本文说明如何从源码在本机构建桌面应用（Tauri 2 + Vue 3 + Python Sidecar）。功能与使用说明见 [README.md](README.md)。

当前版本：**v1.0.2**。构建产物为 Windows **MSI + NSIS** 双安装包，发布者（Publisher）为 **Agilebot**。

## 1. 环境与工具

| 依赖 | 说明 |
|------|------|
| **Windows 10/11（x64）** | 当前仓库脚本与安装包目标以 Windows 为主；`bundle.targets` = **MSI** + **NSIS**。 |
| **Node.js + npm** | 用于前端与调用 Tauri CLI；建议 LTS 版本。 |
| **Rust（stable）** | `rustc`、`cargo`；Windows 上一般为 **MSVC 工具链**（`x86_64-pc-windows-msvc`）。需安装 **Visual Studio Build Tools**（含「使用 C++ 的桌面开发」负载）。 |
| **Python 3.9+** | 需加入 `PATH`（`python` 或 `py` 可用）；用于开发期直连 `bridge.py`，以及 **PyInstaller 打包 sidecar**。 |
| **WiX Toolset 3.11** | 打 MSI 时 Tauri 会用到；本仓库通过脚本安装到 `%LOCALAPPDATA%\tauri\WixTools314`。 |
| **NSIS** | 打 NSIS `-setup.exe` 时 Tauri 会用到；脚本会下载到 `%LOCALAPPDATA%\tauri\NSIS`。 |

可选：若 `.cargo/config.toml` 中配置了国内 crates 镜像，可缓解 `cargo` 拉取依赖较慢的问题；网络正常时也可按需调整或删除该配置。

## 2. 克隆仓库后首次准备

项目根目录执行：

```powershell
npm install
```

**首次打 MSI/NSIS 前**（或 `prepare_tauri_tools.ps1` 报找不到 WiX/NSIS 时），下载并解压 WiX / NSIS 到本机 Tauri 缓存目录：

```powershell
npm run tauri:download-wix-nsis
```

说明：`download_tauri_wix_nsis_tools.ps1` 内默认使用 `ghproxy.net` 作为 GitHub 下载前缀；若本机可直连 GitHub，可把脚本中的 `$ghproxy` 改为 `""` 后重新执行。

## 3. 捷勃特 Python SDK（Sidecar 必需）

`python-sidecar/requirements.txt` 会通过 **本地 wheel 路径** 安装 Agilebot SDK。请确保：

- 仓库中存在与 `requirements.txt` 中路径一致的 **wheel 文件**（历史上放在 `Python_v2.0.1.0/` 下）；或
- 把其中 `pip install` 的那一行改为 **你本机实际 wheel 路径 / 私有索引**，再执行 sidecar 构建。

未正确安装 SDK 时，`npm run sidecar:build` 中的 `pip install` 会失败。

## 4. 构建 Python Sidecar（发布安装包前必做）

发布构建（`tauri build`）会把 `externalBin` 指向的 **`gbt-bridge-<target-triple>.exe`** 打进安装包。必须先打出真实可执行文件：

```powershell
npm run sidecar:build
```

脚本会：安装 `python-sidecar/requirements.txt` 与 `requirements-build.txt`（含 PyInstaller）→ 按 `gbt_bridge.spec` 生成 `python-sidecar/dist/gbt-bridge.exe` → 按 `rustc -vV` 的 host 三元组复制到：

```
src-tauri/binaries/gbt-bridge-<target-triple>.exe
```

64 位 Windows 一般为 `gbt-bridge-x86_64-pc-windows-msvc.exe`。

开发模式（`npm run tauri:dev`）下 Rust 走调试分支，直接调用系统 Python + `python-sidecar/bridge.py`，**不依赖** 上述 exe；但 `cargo`/Tauri 仍会检查 `binaries/` 目录占位，详见 `src-tauri/binaries/README.md`。

## 5. 构建正式安装包（MSI + NSIS）

在已完成 **第 4 节 sidecar 构建** 的前提下，项目根目录执行：

```powershell
npm run tauri:build
```

该命令会依次：

1. **`pretauri:build` 自动清理**：执行 `npm run clean`，删除 `dist/`、Vite 缓存、以及 `src/` 下误生成的 `.js` / `.js.map` / `.d.ts` / `.tsbuildinfo`（见第 9 节；没有这一步打出来的 bundle 可能仍是旧代码）。
2. 运行 `scripts/prepare_tauri_tools.ps1`：确认 `%LOCALAPPDATA%\tauri\WixTools314\candle.exe` 与 NSIS 已就位（不存在则按提示先执行 `npm run tauri:download-wix-nsis`）。
3. 执行 `beforeBuildCommand`：`npm run build`（`prebuild` 再跑一次清理 → `vue-tsc --noEmit` → `vite build` → 产物写入 `dist/`）。
4. 执行 `cargo` 编译并调用 Tauri 打包 **MSI** 与 **NSIS**。
5. 运行 `scripts/rename_bundles.ps1`：把 `_x64_xx-XX` 语言区域后缀从 MSI/NSIS 文件名里去掉，得到干净文件名（如 `GBTRegisterManager_1.0.2.msi`、`GBTRegisterManager_1.0.2-setup.exe`）。

**产物位置**（默认 release）：

- MSI：`src-tauri/target/release/bundle/msi/`
- NSIS：`src-tauri/target/release/bundle/nsis/`

主程序名、版本、发布者以 `src-tauri/tauri.conf.json` 中 `productName` / `version` / `publisher` 为准。

## 6. 仅构建前端（不打包桌面）

```powershell
npm run build
```

会先经过 `prebuild → clean` 清理，再 `vue-tsc --noEmit` 做类型检查并 `vite build` 输出到 `dist/`。用于快速验证前端是否能通过构建，**不等于** 完整桌面安装包。

## 7. 开发调试

```powershell
npm run tauri:dev
```

启动 Vite 开发服务并打开带开发者工具的桌面窗口。调试期会直接调用系统 Python + `python-sidecar/bridge.py`，需本机 Python 环境与 SDK 可用。

## 8. 版本号修改位置

发布新版时需同步以下几处（保持一致）：

| 文件 | 字段 |
|------|------|
| `package.json` | `version` |
| `package-lock.json` | 顶层 `version` 以及 `packages.""` 里的 `version` |
| `src-tauri/tauri.conf.json` | `version` |
| `src-tauri/Cargo.toml` | `[package].version` |
| `src/App.vue` | `DEFAULT_APP_VERSION`（UI 兜底展示） |
| `README.md` / `README_en.md` | `当前软件版本` / `Current app version` 以及 **Changelog** |

改完建议执行一次 `npm run build` 让 `package-lock.json` 与 `Cargo.lock` 同步刷新。

## 9. 清理缓存 / 老产物

`scripts/clean.mjs` 是跨平台纯 Node 脚本，无额外依赖，默认清理：

- `dist/`
- `node_modules/.vite`、`node_modules/.cache`、`.eslintcache`
- `src/` 下所有残留 `.js` / `.js.map` / `.d.ts` / `.tsbuildinfo`
- 根目录 `tsconfig.tsbuildinfo` / `tsconfig.app.tsbuildinfo`

自动钩子（npm 会在对应命令前自动跑）：

- `prebuild` → `npm run build` 前自动清
- `pretauri:build` → `npm run tauri:build` 前自动清

也可以手动：

```powershell
npm run clean
```

需要连 Rust 全量产物一起清（`src-tauri/target/`，重编很慢）：

```powershell
npm run clean -- --rust
```

> **为什么必须清 `src/` 下的 `.js`**：历史上 `tsc` 曾把 `src/**/*.ts` 编译成同名 `.js` 留在源码目录里。Vite 默认 `resolve.extensions` 让 `.js` 排在 `.ts` 前，这些残留会**顶替**真正的 `.ts` 源，打出来的 bundle 里全是老代码（典型症状：连接命令报 `missing required key req`、中文 placeholder 退回英文）。本仓库已在 `vite.config.ts` 显式把 `.ts`/`.tsx` 置顶并在每次构建前清理，从两头堵住这个坑。

## 10. 常见问题

**Q：`tauri build` 报找不到 `gbt-bridge-xxx.exe`。**
A：先 `npm run sidecar:build`，确认 `src-tauri/binaries/` 下文件名与当前 `rustc` host triple 一致。

**Q：打包阶段提示 WiX / NSIS 未找到。**
A：`npm run tauri:download-wix-nsis`，确认 `%LOCALAPPDATA%\tauri\WixTools314\candle.exe` 与 NSIS 目录存在后再 `npm run tauri:build`。

**Q：`pip install -r python-sidecar/requirements.txt` 报 wheel 路径不存在。**
A：按第 3 节补齐 SDK wheel 或修改 `requirements.txt` 中的路径。

**Q：Rust 编译报 MSVC / link 相关错误。**
A：安装 Visual Studio Build Tools，勾选「使用 C++ 的桌面开发」，并确保在 x64 Native Tools 或普通 PowerShell 下使用的工具链一致。

**Q：改完代码重装后行为没变化 / UI 语言不对 / 连接命令参数报错。**
A：十有八九是命中了第 9 节那个坑。执行 `npm run clean` 后重新 `npm run tauri:build`，再卸载旧版重装新 MSI/NSIS。

**Q：`cargo` 偶发 `Access Denied (os error 5)`。**
A：通常是 `src-tauri/target/` 被杀软/资源占用锁定。关闭运行中的旧 `GBTRegisterManager.exe`，或 `npm run clean -- --rust` 后重试。

---

若构建流程有变更，请以 `package.json` 的 `scripts`、`src-tauri/tauri.conf.json` 与 `python-sidecar/build_sidecar.ps1` 为准，并同步更新本文。
