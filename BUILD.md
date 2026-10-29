# 捷勃特机器人工具箱（Agilebot robot toolbox）— 构建说明

> 2026-10-29：用户确认当前交付 v1.3.6 实机测试通过。来源为本会话用户反馈；本次仅同步记录，不重跑设备测试。未提供逐项结果、机型/固件或安装升级矩阵。此前未测描述保留为历史时点，当前结论以本条及 docs/acceptance-1.3.6-2026-10-29.md 为准。

本文说明如何从源码在本机构建桌面应用（Tauri 2 + Vue 3 + Python Sidecar）。功能与使用说明见 [README.md](README.md)。

2026-10-28：当前版本 **v1.3.6** 增加 P 批量写入结果确认，单点通信失败后继续后续点，保留双类型导入导出及问题 3、4 修复。最新测试和校验值见 [P 结果确认验收](docs/p-write-results-1.3.6.md)。控制柜发现客户现场对照仍待完成；下方旧包保留为历史记录。

当前版本：**v1.3.6**。默认构建目标为 Windows **MSI + NSIS** 双安装包，发布者（Publisher）为 **Agilebot**。本轮完整离线 NSIS 构建成功，261918752 字节，不声明 MSI 构建或安装升级验收。复用下方命令，将 Sidecar 独立目录版本改为 1.3.6，正式前端目录为 `.local-testing/frontend-1.3.6`；局部配置 `.local-testing/tauri-full-1.3.6.json` 指向该目录，清空 beforeBuildCommand。冻结组件额外运行 `scripts/test-frozen-excel.py`（先运行 Python tests 生成测试表格）。

已生成 `src-tauri/target/release/bundle/nsis/AgilebotRobotToolbox_1.3.3_x64-setup.exe`，261907814 字节，SHA256 `4821B90247A8DBB9FBCD27C9D9488BD1E578C2F8DBBF6D9A9975AFB80754FD57`。完整构建退出码 0；版本号、Sidecar 打包输入及 WebView2 离线安装器签名已核对。

本轮使用独立目录，绕开会删除文件的 npm prebuild/clean 钩子；未调用清理脚本：

```powershell
# 仓库根目录：先类型检查，再构建正式前端（不含 .local-testing 的模拟入口）
& '.\node_modules\.bin\vue-tsc.cmd' --noEmit
# 确认上一条退出码为 0 后继续
& '.\node_modules\.bin\vite.cmd' build --outDir '.local-testing/frontend-1.3.3'
# 在 python-sidecar 目录执行，确认退出码为 0
& '..\.venv\Scripts\python.exe' -m PyInstaller gbt_bridge.spec --distpath dist-1.3.3 --workpath build-1.3.3
# 回到根目录，先验证冻结组件，再复制供 Tauri 打包
& '.\.venv\Scripts\python.exe' -B scripts/test-frozen-discovery.py python-sidecar/dist-1.3.3/gbt-bridge.exe
Copy-Item -LiteralPath 'python-sidecar\dist-1.3.3\gbt-bridge.exe' -Destination 'src-tauri\binaries\gbt-bridge-x86_64-pc-windows-msvc.exe' -Force
& '.\node_modules\.bin\tauri.cmd' build --config '.local-testing/tauri-full-1.3.3.json' --bundles nsis
```

每条外部命令均须检查 `$LASTEXITCODE`，失败时停止，不复制旧产物。局部构建配置内容为 `{"build":{"beforeBuildCommand":"","frontendDist":"../.local-testing/frontend-1.3.3"}}`；其他安装配置继承正式 `tauri.conf.json`，包含 WebView2 离线运行时，不包含 Npcap。新目录首次构建无需删除旧包；重复构建前按授权范围处理构建工具的输出覆盖行为。

1.3.2 完整安装包：`src-tauri/target/release/bundle/nsis/AgilebotRobotToolbox_1.3.2_x64-setup.exe`，261098264 字节，SHA256 `798DE8280BA7C83CEAC8BC812CD87EF1F1040B18C1B4C5E0EFB8506D4349E3BE`。完整 `tauri build --config .local-testing/tauri-full-1.3.2.json --bundles nsis` 退出码 0，含 WebView2 离线安装器；安装升级未执行。

历史交付（1.3.1）：完整离线 EXE 位于 `src-tauri/target/release/bundle/nsis/AgilebotRobotToolbox_1.3.1_x64-setup.exe`，261100088 字节，版本 1.3.1，SHA256 `D85F708DE188A026961682F09620CB7C4A2C6A24AED6AC30889D318D2B9A964F`。已替换下述早期精简测试包，内嵌主程序、Python 通信组件及微软 WebView2 离线安装器（214090448 字节，Authenticode Valid，Microsoft Corporation）。生成的 NSIS 脚本确认为 offlineInstaller；未执行安装。Npcap 按项目约定仍由用户另行安装，不捆绑。

本次 `tauri bundle --config .local-testing/tauri-full-1.3.1.json --bundles nsis,msi` 先完成 NSIS，随后 MSI 等待 GitHub WiX 下载；为交付现成 EXE，仅停止该构建进程的下载等待。整体双格式命令不是成功退出，本次仅交付 NSIS，不声明 MSI 构建成功。原 release 程序重复打包仍有 bundle-type 标记告警，未启用 updater。

2026-10-10 修复测试包：release NSIS 已生成，路径为 `src-tauri/target/release/bundle/nsis/AgilebotRobotToolbox_1.3.1_x64-setup.exe`。WebView2 离线安装器下载遇到 TLS 错误，本次局部覆盖 `webviewInstallMode=skip`，要求目标机已安装 WebView2；默认完整离线配置未变。冻结组件已验证 R/PR 及 P A1 读取导出，Python 后端完成获准的 R/PR 写入清理，release 桌面完成 R 读/导出/导入预览。P 写入、完整桌面写入和安装未验收，另有单个程序空响应待诊断，见 [本轮记录](docs/register-regression-2026-10-10.md)。

审查修复与回归命令见 [v1.3.0 修复记录](docs/review-fixes-2026-10-09.md)。Sidecar 构建脚本现要求项目 `.venv`；pip、PyInstaller 或 rustc 失败即终止，不允许继续复制旧 EXE。本轮验证生成 NSIS 调试测试包，未执行安装或发布。

## 查找控制柜

[当前修复计划](docs/superpowers/plans/2026-10-28-controller-discovery-parity.md) 与 [本轮验收](docs/controller-discovery-parity-acceptance.md) 记录 v1.3.3；旧计划保留历史证据。Npcap 仅在进入查找页面或主动重新检测／搜索时检查，不随工具箱分发或自动安装。

新增 Python 依赖 `scapy==2.6.1`，由现有 Sidecar 冻结打包；最终用户无需安装 Python 或 Go。开发建议先执行 `py -m venv .venv`，使用 `& '.\.venv\Scripts\python.exe' -m pip install -r python-sidecar/requirements.txt -r python-sidecar/requirements-build.txt` 准备环境。Rust 开发模式优先使用项目 `.venv/Scripts/python.exe`；未找到时沿用原系统 `python` 入口。

在 `python-sidecar` 目录使用项目解释器运行 `& '..\.venv\Scripts\python.exe' -m PyInstaller gbt_bridge.spec`，再将生成的 EXE 按第 4 节复制至目标三元组路径。本次验证采用此方式，未调用带清理行为的脚本。`gbt_bridge.spec` 显式排除 Npcap 驱动、DLL 和辅助程序，仍需审计最终产物；构建机不需要安装 Npcap。网络扫描实测则需要用户自行安装并启动可用的 Npcap。

新增测试：项目根目录运行 `& '.\.venv\Scripts\python.exe' -m unittest discover -s python-sidecar/tests`；Rust 在 `src-tauri` 运行 `cargo test -p gbt-register-manager --lib`。Rust 扫描测试使用项目 `.venv`，包括真实 Sidecar 的只读依赖检测；测试不发送发现报文。

## 1. 环境与工具

| 依赖 | 说明 |
|------|------|
| **Windows 10/11（x64）** | 当前仓库脚本与安装包目标以 Windows 为主；`bundle.targets` = **MSI** + **NSIS**。 |
| **Node.js + npm** | 用于前端与调用 Tauri CLI；建议 LTS 版本。 |
| **Rust（stable）** | `rustc`、`cargo`；Windows 上一般为 **MSVC 工具链**（`x86_64-pc-windows-msvc`）。需安装 **Visual Studio Build Tools**（含「使用 C++ 的桌面开发」负载）。 |
| **Python / 项目 .venv** | 本轮使用 Python 3.13.15；先用 `py -m venv .venv` 建立环境。Sidecar 构建必须使用该环境，其他 Python 版本尚未在本轮验证。 |
| **WiX Toolset 3.11** | 打 MSI 时 Tauri 会用到；本仓库通过脚本安装到 `%LOCALAPPDATA%\tauri\WixTools314`。 |
| **NSIS** | 打 NSIS `-setup.exe` 时 Tauri 会用到；脚本会下载到 `%LOCALAPPDATA%\tauri\NSIS`。 |

本仓库根目录 [`.cargo/config.toml`](.cargo/config.toml) **不**再覆盖 `crates-io`（避免与 Cargo 内置官方源重复定义）；仅保留 `net` 重试与 MSVC 静态 CRT 等设置。若你曾在用户级 `~/.cargo/config.toml` 里把 `crates-io` 指到 **rsproxy**，而本机 `127.0.0.1:7890` 代理又不可用，仍可能拉依赖失败——可临时改回官方默认、修好代理，或在**当前终端**去掉代理再打包：`Remove-Item Env:HTTP_PROXY,Env:HTTPS_PROXY -ErrorAction SilentlyContinue`。

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

开发模式（`npm run tauri:dev`）下 Rust 走调试分支，优先调用项目 `.venv` 中的 Python + `python-sidecar/bridge.py`，**不依赖** 上述 exe；但 `cargo`/Tauri 仍会检查 `binaries/` 目录占位，详见 `src-tauri/binaries/README.md`。

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
5. 运行 `scripts/rename_bundles.ps1`：把 `_x64_xx-XX` 语言区域后缀从 MSI/NSIS 文件名里去掉，得到干净文件名（如 `AgilebotRobotToolbox_1.3.0.msi`、`AgilebotRobotToolbox_1.3.0-setup.exe`）。

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

启动 Vite 开发服务并打开带开发者工具的桌面窗口。调试期会优先调用项目 `.venv` 中的 Python + `python-sidecar/bridge.py`，需本机 Python 环境与 SDK 可用。

## 8. 版本号修改位置

发布新版时需同步以下几处（保持一致）：

| 文件 | 字段 |
|------|------|
| `package.json` | `version` |
| `package-lock.json` | 顶层 `version` 以及 `packages.""` 里的 `version` |
| `src-tauri/tauri.conf.json` | `version` |
| `src-tauri/Cargo.toml` | `[package].version` |
| `src-tauri/Cargo.lock` | 本项目 `gbt-register-manager` 包版本 |
| `src/App.vue` | `DEFAULT_APP_VERSION`（UI 兜底展示） |
| `README.md` / `README_en.md` | `当前软件版本` / `Current app version` 以及 **Changelog** |

分别核对 npm 与 Cargo 锁文件中的本项目版本；`npm run build` 不会自动同步这两个锁文件。依赖不变时仅同步本项目版本字段，随后运行类型检查及相应构建验证。

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
A：通常是 `src-tauri/target/` 被杀软/资源占用锁定。关闭运行中的旧 `AgilebotRobotToolbox.exe`（或旧版 `GBTRegisterManager.exe`），或 `npm run clean -- --rust` 后重试。

**Q：`tauri build` / `cargo` 报 `Could not connect to server ... 127.0.0.1 port 7890`，或 `failed to query replaced source registry` / `rsproxy.cn`。**
A：多为 **HTTP(S) 代理环境变量** 指向本机 **7890**，但 Clash / v2rayN 等未监听或未对命令行生效。处理顺序建议：① 确认代理已开且终端能访问 `127.0.0.1:7890`；② 检查用户级 `~/.cargo/config.toml` 是否把 `crates-io` 指到 rsproxy（与本仓库根目录 `.cargo/config.toml` 无关时仍会走镜像）；③ 仍失败时在**同一 PowerShell** 清除代理变量再编（见上文 `Remove-Item Env:HTTP_PROXY...`）。

**Q：`source crates-io-sparse defines source registry crates-io, but that source is already defined`。**
A：不能把 `replace-with` 再指向 `sparse+https://index.crates.io/`，会与 Cargo 内置 `crates-io` 冲突。本仓库 `.cargo/config.toml` 已去掉该写法；若你本地又加回类似配置，请删除 `replace-with` 整段，使用默认 `crates-io` 即可。

---

若构建流程有变更，请以 `package.json` 的 `scripts`、`src-tauri/tauri.conf.json` 与 `python-sidecar/build_sidecar.ps1` 为准，并同步更新本文。
