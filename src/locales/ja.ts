export default {
  app: {
    title: "ジエボテロボットツールボックス",
    model: "機種",
    software: "ソフト",
    controllerIp: "制御装置：",
    teachPanelIp: "ティーチ：",
    robotSdk: "SDK："
  },
  errors: {
    appRuntime: "アプリケーションでエラーが発生しました。コンソールログを確認してください。",
    GBT_CONNECTION_LOCK_ERROR: "アプリの状態が異常です。再起動してください。",
    GBT_ROBOT_OP_BUSY: "他の操作を実行中です。しばらくお待ちください。",
    GBT_NOT_CONNECTED: "先にロボットに接続してください。",
    GBT_EMPTY_CONTROLLER_IP: "制御装置の IP を入力してください。",
    GBT_META_READ_FAILED: "機種情報を読み取れません。接続と SDK を確認してください。",
    GBT_DEBUG_EXPORT_BLOCKED: "デバッグモードではログとプログラムデータのエクスポートはできません。",
    GBT_SESSION_MISMATCH: "接続情報が現在のセッションと一致しません。再接続してください。",
    GBT_TEACH_PANEL_IP_REQUIRED: "ティーチペンダントの IP が未設定です。",
    GBT_INVALID_EXPORT_DATE: "日付は YYYY-MM-DD 形式で入力してください。",
    GBT_INTERNAL_ERROR: "操作に失敗しました。ログを確認してください。",
    GBT_CONNECT_FAILED: "接続に失敗しました。IP とネットワークを確認してください。",
    GBT_PROGRAM_NOT_FOUND: "プログラムが見つかりません。プログラム名を確認してください。",
    GBT_FILE_NOT_READABLE: "選択したファイルが存在しないか、読み取れません。",
    GBT_P_READ_NEED_PROGRAM: "P 点の読み取りにはプログラム名が必要です。",
    GBT_P_WRITE_NEED_PROGRAM: "P 点の書き込み前にプログラム名が必要です。",
    GBT_P_SERVICE_UNREACHABLE: "P レジスタサービスに接続できません。制御装置のポート 5606 とネットワークを確認してください。",
    GBT_UNSUPPORTED_REGISTER_TYPE: "サポートされていないレジスタタイプです。",
    GBT_OPENPYXL_MISSING: "openpyxl がインストールされていないため Excel を処理できません。",
    GBT_SDK_NOT_FOUND: "Agilebot Python SDK が見つかりません。",
    GBT_SIDECAR_MISSING: "ロボット通信コンポーネントが見つかりません。アプリを再インストールしてください。",
    GBT_EXTENSION_INSTALL_FAILED: "プラグインまたは依存関係のインストールに失敗しました。ログを確認してください。"
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
    connecting: "接続中…",
    connectDebug: "デバッグモードです（実機は接続されていません）。",
    connectFailed: "接続に失敗しました。",
    disconnected: "切断しました。",
    unsupportedRobotModel:
      "ロボット機種を認識できません（GBT-P / GBT-C / GBT-S のみ）。接続を切断しました。機種を確認するかサポートに連絡してください。",
    needConnect: "先にロボットに接続してください。",
    pReadNeedProgram: "P レジスタの読み取りにはプログラム名が必要です。",
    readDone: "読み取り完了：{total} 件。",
    excelPreview: "ファイルを読み込みプレビュー：{total} 行。",
    noExportData: "エクスポートするプレビューデータがありません。",
    needPreviewData: "先にプレビューデータを用意してください。",
    pWriteNeedProgram: "P レジスタの書き込み前にプログラム名が必要です。",
    noValidRegIds: "プレビューデータに有効なレジスタ ID がありません。",
    importCancelled: "インポートをキャンセルしました。",
    applyDone: "完了：成功 {success}、スキップ {skipped}、失敗 {failed}。",
    applyFailed: "書き込みは完了していません：成功 {success}、スキップ {skipped}、失敗 {failed}。",
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
    dataExport: "レジスタデータのエクスポート",
    dataImport: "レジスタデータのインポート",
    logDataExport: "ログ／プログラムとデータのエクスポート",
    pluginInstall: "プラグインインストール"
  },
  pluginInstall: {
    title: "プラグインインストール",
    seriesNeedsTeachPanel:
      "GBT-P / GBT-C / GBT-S では、ティーチペンダントの IP がないと SDK 検出やプラグイン／依存のインストールができません。接続画面で IP を入力し直してください。",
    errorNeedsTeachPanelIp:
      "GBT-P / GBT-C / GBT-S ではティーチペンダントの IP がないとプラグイン／wheel をインストールできません。接続画面で IP を入力し直してください。",
    errorDebugBypass: "デバッグモードではロボットへのプラグイン／依存のインストールはできません。",
    errorNoExtFile: "プラグインファイルが選択されていません。",
    errorNoWhlFile: "依存ファイル（.whl）が選択されていません。",
    extPathLabel: "プラグインパス（.gbtapp）",
    extPathPlaceholder: "下の「プラグインファイルを選択」を使用",
    whlPathLabel: "依存パッケージパス（.whl）",
    whlPathPlaceholder: "下の「依存ファイルを選択」を使用",
    pickExt: "プラグインファイルを選択",
    pickWhl: "依存ファイルを選択",
    fileFilterExt: "GBT プラグイン（.gbtapp）",
    fileFilterWhl: "Python 依存パッケージ（.whl）",
    installExt: "プラグインをインストール",
    installWhl: "依存をインストール",
    noExtFile: "先にプラグインファイルを選択してください。",
    noWhlFile: "先に .whl ファイルを選択してください。",
    extSuccess: "プラグインをインストールしました：{name}（バージョン {version}）",
    whlSuccess: "wheel のインストールが完了しました。",
  },
  logExport: {
    cardTitle: "ログとプログラムデータのエクスポート",
    pickDate: "ログ日付（暦日）",
    hintProgramData: "プログラムデータのエクスポートは上の日付を使いません。",
    exportControllerLogs: "制御装置ログをエクスポート",
    exportTeachPanelLogs: "ティーチペンダントログをエクスポート",
    exportProgramData: "プログラムデータをエクスポート",
    needConnectHint: "先にロボットに接続してください。",
    noTeachIpHint: "ティーチペンダント IP が未入力のため、ペンダント側ログはエクスポートできません。",
    cancelledSave: "保存をキャンセルしました"
  },
  create: {
    cardTitle: "レジスタの一括作成",
    start: "一括作成を開始",
    running: "作成中..."
  },
  export: {
    title: "レジスタデータのエクスポート",
    readPreview: "ロボットから読み取り・プレビュー",
    reading: "読み取り中...",
    toExcel: "Excel にエクスポート"
  },
  import: {
    title: "レジスタデータのインポート",
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
  },
  response: {
    disconnected: "切断しました。",
    save_cancelled: "保存をキャンセルしました。",
    export_saved: "Excel ファイルをエクスポートしました。",
    template_saved: "テンプレートをエクスポートしました。",
    logs_exported: "ログファイルを {count} 件エクスポートしました。",
    no_logs: "指定日のログが見つかりませんでした。",
    program_data_exported: "プログラムデータをエクスポートしました（{count} 件）。",
    wheel_installed: "wheel のインストールが完了しました。",
    operation_failed: "操作に失敗しました。",
    write_skipped_debug: "デバッグモード：書き込みをスキップしました。"
  },
  progress: {
    readStarting: "読み取り中...",
    writeStarting: "書き込み中...",
    read: "読み取り中 {current}/{total}、一致 {matched} 件。",
    readAll: "ID {current} を読み取り中、一致 {matched} 件。",
    write: "書き込み中 {current}/{total}、完了 {matched} 件。",
    exportStarting: "エクスポートを準備中、対象ファイルをスキャン中...",
    exportScan: "スキャン完了：エクスポート対象 {total} 件",
    exportDownload: "エクスポート中 {current}/{total}、完了 {matched} 件",
    exportZip: "ZIP を作成中..."
  }
};
