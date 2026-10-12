# v1.3.2：P 点程序不存在提示修复

最新结论（2026-10-12）：用户确认 v1.3.2 全功能测试通过，本轮功能验收完成，详见 [验收记录](acceptance-1.3.2-2026-10-12.md)。下文保留当时的检查结果和限制，不作为当前待修清单。

用户实测剩余问题：批量新建 P 点输入不存在的程序名，被提示为通信或控制柜异常。

原因：新建和导入前的冲突预检复用 P 范围读取，SDK 的 PROGRAM_NOT_FOUND 被 ensure_read_status 归入 GBT_REGISTER_READ_FAILED；P 全部读取也将该状态归为 GBT_INTERNAL_ERROR。

修复：两个读取路径精确映射 PROGRAM_NOT_FOUND 为已有的 GBT_PROGRAM_NOT_FOUND，复用五种语言的现有提示。中文为“找不到对应程序，请检查程序名是否正确。”程序不存在不会变成空点位或触发自动创建程序。实际通信异常、未知业务错误仍中止；已有程序中不存在的点位仍按空点位处理。直接写入路径返回同一专用错误，未调用 add/write。

验证：修复前回归复现 3 个断言失败；修复后 Python 隔离测试 32 项通过、0 项失败，覆盖 P 范围/全部的错误码、未写入、点位不存在与通信异常的区分。前端类型检查及生产构建通过，差异格式检查通过。冻结构建仍有历史可选依赖告警（旧实时轨迹 google、Scapy krack），不计为相关功能实测。

实机复核未完成：对 192.168.110.2 的冻结组件只读检查返回 GBT_P_SERVICE_UNREACHABLE，在到达程序名检查前终止。没有执行机器人写入，不能将该尝试计为通过。用户已确认 ViteInPinza 程序自身有问题，继续排除，不排查。

版本更新至 1.3.2，完整 NSIS 包含 WebView2 离线安装器；安装/升级及本次修复的桌面实机提示待用户验收。

补充验证：使用已安装真实 SDK 的 PROGRAM_NOT_FOUND 枚举、本地只读替身验证两个映射，2 项通过，无网络连接及机器人写入。本轮共 34 项本地检查通过。主程序和 NSIS 完整构建退出码 0；安装包 `src-tauri/target/release/bundle/nsis/AgilebotRobotToolbox_1.3.2_x64-setup.exe`，261098264 字节，ProductVersion 1.3.2，SHA256 `798DE8280BA7C83CEAC8BC812CD87EF1F1040B18C1B4C5E0EFB8506D4349E3BE`。冻结源、打包输入、release 目录通信组件哈希三者一致：`73CF6CE7D52EE658FB5D8EB4116A7BBFC4E81F94FA667A906D8B6FDAA8B2B42B`。
