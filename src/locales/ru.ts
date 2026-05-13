export default {
  app: {
    title: "Agilebot robot toolbox",
    model: "Модель",
    software: "ПО",
    controllerIp: "Контроллер:",
    teachPanelIp: "Пульт:",
    robotSdk: "SDK:"
  },
  errors: {
    appRuntime: "Произошла ошибка приложения. См. журнал консоли."
  },
  conflict: {
    title: "Конфликт регистров",
    stop: "Остановить",
    skipExisting: "Пропустить существующие",
    overwriteExisting: "Перезаписать существующие",
    bodyImport:
      "Обнаружено {total} регистров, которые уже есть на роботе (пересечение ID с таблицей). Выберите: перезапись заменит существующие значения; пропуск сохранит значения на роботе; остановка отменит импорт без записи данных.",
    bodyCreate:
      "Обнаружены существующие регистры: {ids}. Выберите: перезапись заменит существующие значения; пропуск сохранит значения на роботе; остановка отменит пакетное создание без записи данных."
  },
  messages: {
    enterIp: "Введите IP-адрес контроллера.",
    invalidIp: "Введите корректный IPv4-адрес (например, 192.168.1.100).",
    invalidTeachPanelIp: "Неверный IP пульта обучения. Введите корректный IPv4 или оставьте поле пустым.",
    connectSuccess: "Подключение к роботу выполнено.",
    connecting: "Подключение…",
    connectDebug: "Режим отладки (реальный робот не подключён).",
    connectFailed: "Не удалось подключиться.",
    unsupportedRobotModel:
      "Нераспознанная модель робота (допустимы только GBT-P, GBT-C, GBT-S). Сеанс разорван. Проверьте модель или обратитесь в поддержку.",
    needConnect: "Сначала подключитесь к роботу.",
    pReadNeedProgram: "Для чтения регистров P укажите имя программы.",
    readDone: "Чтение завершено: записей — {total}.",
    excelPreview: "Файл загружен для предпросмотра: строк — {total}.",
    noExportData: "Нет данных предпросмотра для экспорта.",
    needPreviewData: "Сначала подготовьте данные предпросмотра.",
    pWriteNeedProgram: "Перед записью регистров P укажите имя программы.",
    noValidRegIds: "В данных предпросмотра нет допустимых ID регистров.",
    importCancelled: "Импорт отменён.",
    countPositive: "Количество должно быть больше 0.",
    pCreateNeedProgram: "Перед созданием регистров P укажите имя программы.",
    createCancelled: "Пакетное создание отменено."
  },
  excel: {
    empty: "Файл Excel пуст.",
    headerMismatch: "Заголовки не совпадают. Ожидалось: {expected}; фактически: {actual}",
    readFailed: "Не удалось прочитать файл.",
    tooLarge: "Файл слишком большой (свыше {limitMb} МБ). Разделите его.",
    tooManyRows: "Слишком много строк ({actual}, предел {limit})."
  },
  connect: {
    title: "Подключение к роботу",
    ipPlaceholder: "IP, например 10.27.1.254",
    controllerIpPlaceholder: "IP контроллера, например 10.27.1.254",
    teachPanelIpPlaceholder: "IP пульта обучения (необязательно; оставьте пустым, если отсутствует)",
    recentPlaceholder: "Недавние IP",
    connect: "Подключить",
    disconnect: "Отключить"
  },
  sidebar: {
    title: "Меню",
    batchCreate: "Пакетное создание регистров",
    dataExport: "Экспорт данных регистров",
    dataImport: "Импорт данных регистров",
    logDataExport: "Журналы / программы и данные — экспорт",
    pluginInstall: "Установка плагина"
  },
  pluginInstall: {
    title: "Установка плагина",
    seriesNeedsTeachPanel:
      "Для GBT-P / GBT-C / GBT-S без IP пульта обучения недоступны проверка SDK и установка плагина/зависимостей. Укажите IP на экране подключения и подключитесь снова.",
    errorNeedsTeachPanelIp:
      "Для GBT-P / GBT-C / GBT-S без IP пульта обучения нельзя установить плагин или wheel. Укажите IP на экране подключения и подключитесь снова.",
    errorDebugBypass: "В режиме отладки установка плагинов и зависимостей на робота недоступна.",
    errorNoExtFile: "Файл плагина не выбран.",
    errorNoWhlFile: "Файл зависимости (.whl) не выбран.",
    extPathLabel: "Путь к пакету плагина (.gbtapp)",
    extPathPlaceholder: "Используйте «Выбрать файл плагина» ниже",
    whlPathLabel: "Путь к зависимости (.whl)",
    whlPathPlaceholder: "Используйте «Выбрать файл зависимости» ниже",
    pickExt: "Выбрать файл плагина",
    pickWhl: "Выбрать файл зависимости",
    installExt: "Установить плагин",
    installWhl: "Установить зависимость",
    noExtFile: "Сначала выберите файл плагина.",
    noWhlFile: "Сначала выберите файл .whl.",
    extSuccess: "Плагин установлен: {name} (версия {version})",
    whlSuccess: "Установка wheel завершена.",
  },
  logExport: {
    cardTitle: "Экспорт журналов и данных программ",
    pickDate: "Дата журнала (календарь)",
    hintProgramData: "Экспорт данных программы не использует дату выше.",
    exportControllerLogs: "Экспорт журналов контроллера",
    exportTeachPanelLogs: "Экспорт журналов пульта обучения",
    exportProgramData: "Экспорт данных программы",
    needConnectHint: "Сначала подключитесь к роботу.",
    noTeachIpHint: "IP пульта обучения пуст — экспорт журналов пульта недоступен.",
    cancelledSave: "Сохранение отменено"
  },
  create: {
    cardTitle: "Быстрое пакетное создание регистров",
    start: "Начать пакетное создание",
    running: "Создание..."
  },
  export: {
    title: "Экспорт данных регистров",
    readPreview: "Считать с робота и предпросмотр",
    reading: "Чтение...",
    toExcel: "Экспорт в Excel"
  },
  import: {
    title: "Импорт данных регистров",
    pickExcel: "Импорт Excel и предпросмотр",
    downloadTemplate: "Скачать шаблон для текущего типа",
    applyRobot: "Импорт на робота",
    applying: "Импорт..."
  },
  form: {
    regType: "Тип регистра",
    count: "Количество",
    startId: "Начальный ID",
    endId: "Конечный ID",
    programName: "Имя программы",
    readMode: "Режим чтения",
    range: "Диапазон",
    all: "Все"
  },
  alert: {
    failTop20: "Сведения об ошибках (первые 20)"
  },
  lang: {
    switcherTitle: "Сменить язык интерфейса"
  }
};
