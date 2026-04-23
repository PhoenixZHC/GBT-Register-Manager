export default {
  app: {
    title: "GBT Robot Register Manager",
    model: "Model",
    software: "Software"
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
    connectDebug: "Debug mode (no real robot connection).",
    connectFailed: "Connection failed.",
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
    dataExport: "Data export",
    dataImport: "Data import"
  },
  create: {
    cardTitle: "Batch create registers",
    start: "Start batch create",
    running: "Creating..."
  },
  export: {
    title: "Data export",
    readPreview: "Read from robot and preview",
    reading: "Reading...",
    toExcel: "Export to Excel"
  },
  import: {
    title: "Data import",
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
