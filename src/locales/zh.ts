export default {
  app: {
    title: "捷勃特机器人寄存器管理工具",
    model: "机型",
    software: "软件"
  },
  errors: {
    appRuntime: "应用运行出现异常，请查看控制台日志。"
  },
  conflict: {
    title: "寄存器冲突",
    stop: "停止",
    skipExisting: "跳过已存在",
    overwriteExisting: "覆盖已存在",
    bodyImport:
      "检测到 {count} 个寄存器在机器人上已存在（与当前表格 ID 重叠）。请选择：覆盖将写入并替换已存在项；跳过将保留机器人上原值；停止将取消本次导入，不写入任何数据。",
    bodyCreate:
      "检测到 {count} 个已存在寄存器（ID {start}~{end}）。请选择：覆盖将写入并替换已存在项；跳过将保留机器人上原值；停止将取消本次批量新建，不写入任何数据。"
  },
  messages: {
    enterIp: "请先输入机器人 IP。",
    connectSuccess: "机器人连接成功。",
    connectDebug: "已进入调试模式（未连接真实机器人）。",
    connectFailed: "连接失败。",
    needConnect: "请先连接机器人。",
    pReadNeedProgram: "P 点读取必须填写程序名。",
    readDone: "读取完成，共 {count} 条。",
    excelPreview: "文档已加载并预览，共 {count} 行。",
    noExportData: "没有可导出的预览数据。",
    needPreviewData: "请先准备预览数据。",
    pWriteNeedProgram: "写入 P 点前必须填写程序名。",
    noValidRegIds: "预览数据中没有有效的寄存器 ID。",
    importCancelled: "已取消本次导入。",
    countPositive: "数量必须大于 0。",
    pCreateNeedProgram: "创建 P 点前必须填写程序名。",
    createCancelled: "已取消本次批量新建。"
  },
  excel: {
    empty: "Excel 内容为空。",
    headerMismatch: "表头不匹配。期望：{expected}；实际：{actual}",
    readFailed: "读取文件失败。"
  },
  connect: {
    title: "连接机器人",
    ipPlaceholder: "IP，例如 10.27.1.254",
    recentPlaceholder: "最近使用 IP",
    connect: "连接",
    disconnect: "断开连接"
  },
  sidebar: {
    title: "功能菜单",
    batchCreate: "批量新建寄存器",
    dataExport: "数据导出",
    dataImport: "数据导入"
  },
  create: {
    cardTitle: "快速批量新建寄存器",
    start: "开始批量新建"
  },
  export: {
    title: "数据导出",
    readPreview: "从机器人读取并预览",
    toExcel: "导出到 Excel"
  },
  import: {
    title: "数据导入",
    pickExcel: "导入 Excel 并预览",
    downloadTemplate: "下载当前类型模板",
    applyRobot: "导入到机器人"
  },
  form: {
    regType: "寄存器类型",
    count: "数量",
    startId: "起始 ID",
    endId: "结束 ID",
    programName: "程序名",
    readMode: "读取模式",
    range: "指定范围",
    all: "全部"
  },
  alert: {
    failTop20: "失败明细（前20条）"
  },
  lang: {
    switcherTitle: "切换界面语言"
  }
};
