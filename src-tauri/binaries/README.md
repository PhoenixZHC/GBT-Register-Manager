# Tauri Python Sidecar 二进制

Tauri 的 `bundle.externalBin` 需要 `gbt-bridge-<target-triple>.exe`。当前目标为 Windows x64：`gbt-bridge-x86_64-pc-windows-msvc.exe`；其他平台未在本轮验证。

- 开发调试分支优先使用项目 `.venv/Scripts/python.exe` 执行 `python-sidecar/bridge.py`，找不到虚拟环境时沿用系统 `python` 入口。Tauri 构建期仍检查 externalBin 路径。
- 打包前必须执行根目录 `npm run sidecar:build`，生成真实 EXE；不要把占位文件或旧二进制当成可交付产物。
- 构建脚本要求项目 `.venv`，依赖安装、PyInstaller 或 rustc 失败就终止，避免继续复制旧 EXE。脚本包含 PyInstaller 清理步骤。
- 发现模块及 Scapy 打入 Sidecar；Npcap 驱动、DLL、辅助程序和安装器不随包分发。普通启动不检测 Npcap，只有进入发现功能或主动重检／搜索时才检测。

当前已交付 v1.3.2 完整 NSIS，包含冻结 Sidecar 和 WebView2 离线运行时；2026-10-12 用户确认全功能测试通过。源码、冻结及实测记录见 [最新验收](../../docs/acceptance-1.3.2-2026-10-12.md)。开发调试分支运行成功不能替代冻结 EXE 检查，用户功能验收也不等同于跨环境安装矩阵。

环境、构建命令及限制见 [BUILD.md](../../BUILD.md)；结果见 [修复与验证记录](../../docs/review-fixes-2026-10-09.md)。
