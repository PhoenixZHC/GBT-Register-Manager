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
      "{count} register(s) already exist on the robot (ID overlap with the table). Choose: Overwrite replaces existing values; Skip keeps values on the robot; Stop cancels the import without writing any data.",
    bodyCreate:
      "{count} register(s) already exist in ID range {start}~{end}. Choose: Overwrite replaces existing values; Skip keeps values on the robot; Stop cancels batch creation without writing any data."
  },
  messages: {
    enterIp: "Please enter the robot IP address.",
    connectSuccess: "Connected to the robot successfully.",
    connectDebug: "Debug mode (no real robot connection).",
    connectFailed: "Connection failed.",
    needConnect: "Please connect to the robot first.",
    pReadNeedProgram: "Program name is required to read P registers.",
    readDone: "Read finished: {count} record(s).",
    excelPreview: "File loaded for preview: {count} row(s).",
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
    readFailed: "Failed to read the file."
  },
  connect: {
    title: "Connect to robot",
    ipPlaceholder: "IP, e.g. 10.27.1.254",
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
    start: "Start batch create"
  },
  export: {
    title: "Data export",
    readPreview: "Read from robot and preview",
    toExcel: "Export to Excel"
  },
  import: {
    title: "Data import",
    pickExcel: "Import Excel and preview",
    downloadTemplate: "Download template for current type",
    applyRobot: "Import to robot"
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
