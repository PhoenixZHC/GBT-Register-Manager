# v1.3.5 点位双类型导入导出

> 2026-10-29：用户确认当前交付 v1.3.6 实机测试通过。来源为本会话用户反馈；本次仅同步记录，不重跑设备测试。未提供逐项结果、机型/固件或安装升级矩阵。此前未测描述保留为历史时点，当前结论以本条及 docs/acceptance-1.3.6-2026-10-29.md 为准。

目标：修正 v1.3.4 对关节点的拒绝策略，完整支持 P/PR 的 JOINT / CART 导出、导入、新建与覆盖。问题 1 不在本次范围；保留预览失效处理与 Excel 安全保存。

格式：新版在 ID 后增加 PoseType（CART / JOINT），包括 XYZABC、J1～J9、原有 TF/UF（P）、Coord/coord，以及 WristFlip、ArmUpDown、ArmBackFront、Turn1～Turn9、Name、Comment。Coord 支持 L / R / U（未指定）。非活动坐标字段留空，避免误用。新版完整保留 SDK 点位信息；旧格式仍按 CART 解释。

单位：使用 SDK 的数值表示，不在表格层额外转换；SDK Joint 文档定义角度，P 的协议弧度转换留给 SDK。实际外部轴的物理单位及固件差异需实机确认，不据此推断直线外部轴单位。

实施顺序：后端点位序列化与校验 → 前端表头兼容与校验 → 双类型混合往返、覆盖切换、旧格式、异常输入回归 → 版本递增、冻结组件和完整安装包。以真实 SDK 对象及序列化结果验证，不使用生产 Mock，不连接机器人。

## 表格填写与兼容

- 推荐先导出点位，再在导出表上修改。新模板的 PoseType 必填 CART / JOINT（不区分大小写）；两种坐标列不能同时填写，活动列必须完整，J7～J9 也保留 SDK 原值。
- Coord/coord：L=-1，R=1，U=0（未指定）。WristFlip、ArmUpDown、ArmBackFront 是 SDK 原始整数 -1/0/1；Turn1～Turn9 是各轴整数圈数，允许负数。新格式必须填写这些字段，不以默认值掩盖缺失信息。
- P 的 TF、UF 为非负整数。Name、Comment 可以为空；以等号开头的名称/注释作为文字保存，不生成 Excel 公式。
- 旧表格保持旧格式和原有覆盖语义，不凭空补充姿态字段。新版覆盖的类型以导入行 PoseType 为准；CART ↔ JOINT 切换是替换点数据，不是数学转换。批量新建页面原有默认 CART 行为保留，通过导入可新增 JOINT 点。
- SDK 的新版 PR 数值接口 GET/UPDATE_POSE_REGISTER_VALUE 不传名称/注释，旧接口和 P 支持相应文本。新版 PR 若导入文本与可读原文本不同，会提前提示 GBT_POSE_METADATA_UNSUPPORTED；保持原文本（新点留空）可正常导入任一坐标类型。不能宣称该 SDK 接口支持未发送的文本变更。

## 自动化

先运行 Python unittest discover（会生成隔离的 `.local-testing/pose-P.xlsx` / `pose-PR.xlsx` 及期望值），再运行 `node --test scripts/test-register-ui.cjs scripts/test-discovery-ui.cjs`；前端用实际 Python 导出文件验证混合表解析、精度及类型。冻结包检查运行 test-frozen-discovery.py 与 test-frozen-excel.py。

本轮自动化 **86 通过、0 失败**：Python 59、前端 20、冻结发现 4、冻结 Excel 3。类型检查和正式前端构建通过。冻结 Excel 测试实际运行 EXE，核验 P/PR 混合表、模板、文字、精度与原文件保护。新版空类型在预览中保持空白，不误显示为旧格式默认 CART。

## 实机验收边界

本轮没有机器人。真实固件读写、外部轴物理单位、安装升级仍待现场验证；SDK 数值对象/序列化和本地表格往返通过不等于实机通过。问题 1 的 P 通信异常中止行为未修复。

现场可先分别导出含 CART / JOINT 的 P、PR 数据核对类型与数值，再在获准的测试程序/编号内验证新增、同类型覆盖、跨类型覆盖和跳过；写入后重新读取比较，不能仅依据成功提示认定数据正确。

## 交付核验

- 完整离线 NSIS：`src-tauri/target/release/bundle/nsis/AgilebotRobotToolbox_1.3.5_x64-setup.exe`，261912948 字节。
- SHA256：`B593C1995BCBDD1540DAB919C3916CD05EC0C3D29A13B4F2FEB971FB7D6300D6`。
- 主程序 ProductVersion / FileVersion 均为 `1.3.5`；npm、Cargo、Tauri、界面回退版本字段同步。
- 冻结组件与打包输入 SHA256 一致：`C859DA86ED2D820C4C001DD40EF6FDC2C9456E01A6396821AEC9359DB2FBC8B1`。
- 正式前端使用 `.local-testing/frontend-1.3.5-release`，局部配置为 `.local-testing/tauri-full-1.3.5.json`。PyInstaller、类型检查、Vite、最终 Tauri 构建退出码均为 0；构建未使用 clean 钩子。
- 1.3.4 安装包保留，SHA256 仍为 `03D42FAAF57B54E8F345ADB19D17138B1FD2A2182146A0E5162744F9D67DE36D`。
- 未外部发布、未安装升级、未实机验证；无子代理、无新分支/worktree。
