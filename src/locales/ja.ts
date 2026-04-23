export default {
  app: {
    title: "GBT ロボットレジスタ管理ツール",
    model: "機種",
    software: "ソフト"
  },
  errors: {
    appRuntime: "アプリケーションでエラーが発生しました。コンソールログを確認してください。"
  },
  conflict: {
    title: "レジスタの競合",
    stop: "中止",
    skipExisting: "既存をスキップ",
    overwriteExisting: "既存を上書き",
    bodyImport:
      "ロボット上に既に存在するレジスタが {total} 件検出されました（表の ID と重複）。選択：上書きは既存を置き換えます。スキップはロボット側の値を保持します。中止はインポートを行わずキャンセルします。",
    bodyCreate:
      "既存レジスタが検出されました：{ids}。選択：上書きは既存を置き換えます。スキップはロボット側の値を保持します。中止は一括作成を行わずキャンセルします。"
  },
  messages: {
    enterIp: "制御装置の IP アドレスを入力してください。",
    invalidIp: "有効な IPv4 アドレスを入力してください（例：192.168.1.100）。",
    invalidTeachPanelIp: "ティーチペンダントの IP が不正です。有効な IPv4 を入力するか空欄にしてください。",
    connectSuccess: "ロボットに接続しました。",
    connectDebug: "デバッグモードです（実機は接続されていません）。",
    connectFailed: "接続に失敗しました。",
    needConnect: "先にロボットに接続してください。",
    pReadNeedProgram: "P レジスタの読み取りにはプログラム名が必要です。",
    readDone: "読み取り完了：{total} 件。",
    excelPreview: "ファイルを読み込みプレビュー：{total} 行。",
    noExportData: "エクスポートするプレビューデータがありません。",
    needPreviewData: "先にプレビューデータを用意してください。",
    pWriteNeedProgram: "P レジスタの書き込み前にプログラム名が必要です。",
    noValidRegIds: "プレビューデータに有効なレジスタ ID がありません。",
    importCancelled: "インポートをキャンセルしました。",
    countPositive: "件数は 0 より大きい必要があります。",
    pCreateNeedProgram: "P レジスタの作成前にプログラム名が必要です。",
    createCancelled: "一括作成をキャンセルしました。"
  },
  excel: {
    empty: "Excel が空です。",
    headerMismatch: "ヘッダーが一致しません。期待：{expected}；実際：{actual}",
    readFailed: "ファイルの読み取りに失敗しました。",
    tooLarge: "ファイルが大きすぎます（{limitMb} MB 超）。分割してください。",
    tooManyRows: "行数が多すぎます（{actual} 行、上限 {limit} 行）。"
  },
  connect: {
    title: "ロボットに接続",
    ipPlaceholder: "IP（例：10.27.1.254）",
    controllerIpPlaceholder: "制御装置 IP（例：10.27.1.254）",
    teachPanelIpPlaceholder: "ティーチペンダント IP（任意。無ければ空欄）",
    recentPlaceholder: "最近使った IP",
    connect: "接続",
    disconnect: "切断"
  },
  sidebar: {
    title: "メニュー",
    batchCreate: "レジスタ一括作成",
    dataExport: "データエクスポート",
    dataImport: "データインポート"
  },
  create: {
    cardTitle: "レジスタの一括作成",
    start: "一括作成を開始",
    running: "作成中..."
  },
  export: {
    title: "データエクスポート",
    readPreview: "ロボットから読み取り・プレビュー",
    reading: "読み取り中...",
    toExcel: "Excel にエクスポート"
  },
  import: {
    title: "データインポート",
    pickExcel: "Excel をインポートしてプレビュー",
    downloadTemplate: "現在の型のテンプレートを取得",
    applyRobot: "ロボットへインポート",
    applying: "インポート中..."
  },
  form: {
    regType: "レジスタ種別",
    count: "件数",
    startId: "開始 ID",
    endId: "終了 ID",
    programName: "プログラム名",
    readMode: "読み取りモード",
    range: "範囲指定",
    all: "すべて"
  },
  alert: {
    failTop20: "失敗詳細（先頭20件）"
  },
  lang: {
    switcherTitle: "表示言語を切り替え"
  }
};
