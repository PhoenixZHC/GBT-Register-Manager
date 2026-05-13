export default {
  app: {
    title: "Agilebot robot toolbox",
    model: "Model",
    software: "Software",
    controllerIp: "Controller:",
    teachPanelIp: "Teach pendant:",
    robotSdk: "SDK:"
  },
  errors: {
    appRuntime: "The application encountered an error. Please check the console log."
  },
  conflict: {
    title: "Register conflict",
    stop: "Stop",
    skipExisting: "Skip existing",
    overwriteExisting: "Overwrite existing",
    bodyImport:
      "{total} register(s) already exist on the robot (ID overlap with the table). Choose: Overwrite replaces existing values; Skip keeps values on the robot; Stop cancels the import without writing any data.",
    bodyCreate:
      "Detected existing registers: {ids}. Choose: Overwrite replaces existing values; Skip keeps current robot values; Stop cancels batch creation without writing data."
  },
  messages: {
    enterIp: "Please enter the controller IP address.",
    invalidIp: "Please enter a valid IPv4 address (e.g. 192.168.1.100).",
    invalidTeachPanelIp: "Teach pendant IP is invalid. Enter a valid IPv4 or leave it blank.",
    connectSuccess: "Connected to the robot successfully.",
    connecting: "Connecting…",
    connectDebug: "Debug mode (no real robot connection).",
    connectFailed: "Connection failed.",
    unsupportedRobotModel:
      "Unrecognized robot model (must be GBT-P, GBT-C, or GBT-S). The session has been disconnected. Verify the model or contact support.",
    needConnect: "Please connect to the robot first.",
    pReadNeedProgram: "Program name is required to read P registers.",
    readDone: "Read finished: {total} record(s).",
    excelPreview: "File loaded for preview: {total} row(s).",
    noExportData: "No preview data to export.",
    needPreviewData: "Please prepare preview data first.",
    pWriteNeedProgram: "Program name is required before writing P registers.",
    noValidRegIds: "No valid register IDs in the preview data.",
    importCancelled: "Import cancelled.",
    countPositive: "Count must be greater than 0.",
    pCreateNeedProgram: "Program name is required before creating P registers.",
    createCancelled: "Batch creation cancelled."
  },
  excel: {
    empty: "The Excel file is empty.",
    headerMismatch: "Header mismatch. Expected: {expected}; actual: {actual}",
    readFailed: "Failed to read the file.",
    tooLarge: "File too large (over {limitMb} MB). Please split it first.",
    tooManyRows: "Too many data rows ({actual}, limit {limit})."
  },
  connect: {
    title: "Connect to robot",
    ipPlaceholder: "IP, e.g. 10.27.1.254",
    controllerIpPlaceholder: "Controller IP, e.g. 10.27.1.254",
    teachPanelIpPlaceholder: "Teach pendant IP (optional; leave blank if none)",
    recentPlaceholder: "Recent IPs",
    connect: "Connect",
    disconnect: "Disconnect"
  },
  sidebar: {
    title: "Features",
    batchCreate: "Batch create registers",
    dataExport: "Register data export",
    dataImport: "Register data import",
    logDataExport: "Logs / programs & data export",
    pluginInstall: "Plugin installation"
  },
  pluginInstall: {
    title: "Plugin installation",
    seriesNeedsTeachPanel:
      "For GBT-P / GBT-C / GBT-S, SDK detection and plugin/wheel install require a teach pendant IP. Enter it on the home connection screen and reconnect.",
    errorNeedsTeachPanelIp:
      "GBT-P / GBT-C / GBT-S require a teach pendant IP to install plugins or wheels. Enter it on the home connection screen and reconnect.",
    errorDebugBypass: "Debug mode cannot install plugins or dependencies on the robot.",
    errorNoExtFile: "No plugin file was selected.",
    errorNoWhlFile: "No dependency (.whl) file was selected.",
    extPathLabel: "Plugin package path (.gbtapp)",
    extPathPlaceholder: "Use “Choose plugin file” below",
    whlPathLabel: "Dependency path (.whl)",
    whlPathPlaceholder: "Use “Choose dependency file” below",
    pickExt: "Choose plugin file",
    pickWhl: "Choose dependency file",
    installExt: "Install plugin",
    installWhl: "Install dependency",
    noExtFile: "Please choose a plugin file first.",
    noWhlFile: "Please choose a .whl file first.",
    extSuccess: "Plugin installed: {name} (version {version})",
    whlSuccess: "Wheel dependency installation finished.",
  },
  logExport: {
    cardTitle: "Logs and program data export",
    pickDate: "Log date (calendar)",
    hintProgramData: "Program data export does not use the date above.",
    exportControllerLogs: "Export controller logs",
    exportTeachPanelLogs: "Export teach pendant logs",
    exportProgramData: "Export program data",
    needConnectHint: "Connect to the robot before exporting.",
    noTeachIpHint: "Teach pendant IP is empty; cannot export pendant logs.",
    cancelledSave: "Save cancelled"
  },
  create: {
    cardTitle: "Batch create registers",
    start: "Start batch create",
    running: "Creating..."
  },
  export: {
    title: "Register data export",
    readPreview: "Read from robot and preview",
    reading: "Reading...",
    toExcel: "Export to Excel"
  },
  import: {
    title: "Register data import",
    pickExcel: "Import Excel and preview",
    downloadTemplate: "Download template for current type",
    applyRobot: "Import to robot",
    applying: "Importing..."
  },
  form: {
    regType: "Register type",
    count: "Count",
    startId: "Start ID",
    endId: "End ID",
    programName: "Program name",
    readMode: "Read mode",
    range: "Range",
    all: "All"
  },
  alert: {
    failTop20: "Failure details (first 20)"
  },
  lang: {
    switcherTitle: "Change interface language"
  }
};
