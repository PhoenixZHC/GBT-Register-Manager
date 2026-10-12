# 架构与模块

当前状态见 [CONTEXT.md](CONTEXT.md)。本项目以 Vue 3 / TypeScript / Naive UI 展示界面，Tauri 2 / Rust 管理桌面能力、会话和任务，Python Sidecar 调用 Agilebot SDK。当前构建目标主要为 Windows x64。

## 模块职责

| 模块 | 职责 |
|---|---|
| `src/App.vue` | 连接与会话、R/PR/P 操作、导入导出、日志和插件页面；异步写入前固定参数，操作中锁定表单 |
| `src/utils/excel.ts`、`registerValidation.ts` | 保留 Excel 原始数值，执行整批输入校验 |
| `src/components/ControllerDiscovery.vue` | 独立发现页、驱动状态、网卡选择、增量结果、取消及 IP 回填 |
| `src/services/tauriApi.ts`、`src/types.ts` | 前后端命令及数据契约；五语文案在 `src/locales/` |
| `src-tauri/src/lib.rs` | Tauri 命令、机器人会话和操作互斥、Sidecar 调用、退出清理 |
| `controller_discovery.rs`、`discovery_job.rs` | 发现任务及共享有界进程运行器、协议帧、超时和取消；Windows Job 回收进程树 |
| `sftp_export.rs` | SSH 元数据、SFTP 下载、同目录临时 ZIP 完成后替换目标 |
| `extension_install.rs` | 向控制柜 Extension_Service（HTTP 5615）上传插件或 wheel |
| `python-sidecar/bridge.py` | SDK 连接及寄存器操作、后端校验、Excel 输出、进度与结果帧 |
| `python-sidecar/controller_discovery.py` | 按需加载 Scapy、Npcap 检测、二层收发和回复校验 |

Rust 模块路径均相对于 `src-tauri/src/`。原 Go 扫描源码目录仅作为协议参考，不是运行依赖。

## 发现链路

进入独立页面 → 检查 Npcap → 选择网卡 → 启动独立 Sidecar 任务 → 先监听后发包 → 增量结果 → 停止或到时结束。启动工具箱及手动 IP 连接不会触发检测。安装依赖由用户在官方页面自行完成。

请求 EtherType 为 `0xEEEA`，广播 JSON 含 8 位字母数字 ID、`src="send_broadcast.go"`、`cmd="get_controller_ips"`、空 `param`。回复 EtherType 为 `0xEEEB`，校验 ID、`dest`、`data.code=1000`，读取 IP/MAC/掩码/网关。按 MAC+IP 去重并合并来源网卡，提示 IP 冲突。

无 IPv4 或链路本地地址网卡不因地址状态被排除。未知 IP 网段发现要求二层互通及固件支持，不能跨路由或隔离 VLAN。使用结果只回填控制柜 IP，不改 TP、不自动连接或配置网络。

## 操作与失败边界

- P 的 PROGRAM_NOT_FOUND 统一映射为 GBT_PROGRAM_NOT_FOUND；新建/导入预检和范围/全部读取均给出程序名提示。它不同于已有程序中的点位不存在，不允许据此继续写入。

- R/PR 可指定范围或使用旧版「全部」扫描（ID 1 起，连续 10 个空编号停止）；P 使用 SDK 全部读取。R/PR 兼容实机返回的 `REG_MANAGER_INVALID_ARG` + `inner_code=0001000200A40007`，按无可读取记录跳过；该码也用于越界，可创建范围仍由写接口校验。此兼容不用于 P，不放行通用 -254、通信错误或其他业务码。
- 前后端校验整批输入：整数 ID 0～100000、无重复、有限数值及合法姿态字段。范围读取／创建最多 10000 个 ID，导入最多 50000 行，冲突检查限制 ID 跨度；机器人实际范围另需固件验收。
- 运行期写入异常保留此前确认计数，当前项可能未知，后续项停止。进程被终止后可能无法取得最终统计，必须核对设备；无自动重试或回滚。
- 普通 Sidecar 调用也使用有界进程运行器：连接／元数据／Excel 120 秒，寄存器读写 900 秒；发现扫描看门狗 30 秒，检测 20 秒，取消清理上限 5 秒。SSH 阻塞操作超时 30 秒。工程限值不代表实机性能承诺。
- Windows 子进程挂起创建，加入具备关闭即回收能力的 Job 后恢复；退出取消进行中的进程任务。普通操作没有新增任意时刻的用户取消入口。
- ZIP 在目标同目录临时文件中完成、同步后替换；无日志或打包失败保留旧 ZIP。

## 构建与验证

2026-10-12 用户确认 v1.3.2 全功能测试通过；本轮验收结论见 [验收记录](docs/acceptance-1.3.2-2026-10-12.md)。以下测试层级区分继续适用。

PyInstaller 将 SDK、发现模块及 Scapy 冻结进同一 Sidecar；Npcap 不分发。开发优先项目 `.venv`，构建脚本强制使用 `.venv` 并检查外部命令退出码。具体命令见 [BUILD.md](BUILD.md)。

测试覆盖协议、任务生命周期、读写校验、前端真实处理函数及构建失败保护。模拟 IPC、源码检测、冻结产物验证、安装及实机验收分别记录，不能相互替代。当前证据及缺口见 [修复记录](docs/review-fixes-2026-10-09.md) 与 [发现计划](docs/superpowers/plans/2026-10-09-controller-discovery.md)。
