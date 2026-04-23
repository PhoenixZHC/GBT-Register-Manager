export default {
  app: {
    title: "GBT 로봇 레지스터 관리 도구",
    model: "기종",
    software: "소프트웨어"
  },
  errors: {
    appRuntime: "애플리케이션 오류가 발생했습니다. 콘솔 로그를 확인하세요."
  },
  conflict: {
    title: "레지스터 충돌",
    stop: "중지",
    skipExisting: "기존 건너뛰기",
    overwriteExisting: "기존 덮어쓰기",
    bodyImport:
      "로봇에 이미 존재하는 레지스터 {total}개가 감지되었습니다(표 ID와 겹침). 선택: 덮어쓰기는 기존 값을 교체합니다. 건너뛰기는 로봇의 값을 유지합니다. 중지는 가져오기를 취소하고 기록하지 않습니다.",
    bodyCreate:
      "이미 존재하는 레지스터가 감지되었습니다: {ids}. 선택: 덮어쓰기는 기존 값을 교체합니다. 건너뛰기는 로봇의 값을 유지합니다. 중지는 일괄 생성을 취소하고 기록하지 않습니다."
  },
  messages: {
    enterIp: "컨트롤러 IP 주소를 입력하세요.",
    invalidIp: "올바른 IPv4 주소를 입력하세요 (예: 192.168.1.100).",
    invalidTeachPanelIp: "티치 펜던트 IP 형식이 올바르지 않습니다. 올바른 IPv4를 입력하거나 비워 두세요.",
    connectSuccess: "로봇에 연결되었습니다.",
    connectDebug: "디버그 모드입니다(실제 로봇 미연결).",
    connectFailed: "연결에 실패했습니다.",
    needConnect: "먼저 로봇에 연결하세요.",
    pReadNeedProgram: "P 레지스터 읽기에는 프로그램 이름이 필요합니다.",
    readDone: "읽기 완료: {total}건.",
    excelPreview: "파일을 불러와 미리보기: {total}행.",
    noExportData: "보낼 미리보기 데이터가 없습니다.",
    needPreviewData: "먼저 미리보기 데이터를 준비하세요.",
    pWriteNeedProgram: "P 레지스터 쓰기 전에 프로그램 이름이 필요합니다.",
    noValidRegIds: "미리보기 데이터에 유효한 레지스터 ID가 없습니다.",
    importCancelled: "가져오기가 취소되었습니다.",
    countPositive: "개수는 0보다 커야 합니다.",
    pCreateNeedProgram: "P 레지스터 생성 전에 프로그램 이름이 필요합니다.",
    createCancelled: "일괄 생성이 취소되었습니다."
  },
  excel: {
    empty: "Excel 내용이 비어 있습니다.",
    headerMismatch: "헤더가 일치하지 않습니다. 예상: {expected}; 실제: {actual}",
    readFailed: "파일을 읽지 못했습니다.",
    tooLarge: "파일이 너무 큽니다({limitMb} MB 초과). 먼저 분할하세요.",
    tooManyRows: "행이 너무 많습니다({actual}행, 최대 {limit}행)."
  },
  connect: {
    title: "로봇 연결",
    ipPlaceholder: "IP, 예: 10.27.1.254",
    controllerIpPlaceholder: "컨트롤러 IP, 예: 10.27.1.254",
    teachPanelIpPlaceholder: "티치 펜던트 IP(선택, 없으면 비워 두세요)",
    recentPlaceholder: "최근 사용 IP",
    connect: "연결",
    disconnect: "연결 끊기"
  },
  sidebar: {
    title: "기능 메뉴",
    batchCreate: "레지스터 일괄 생성",
    dataExport: "데이터보내기",
    dataImport: "데이터 가져오기"
  },
  create: {
    cardTitle: "레지스터 빠른 일괄 생성",
    start: "일괄 생성 시작",
    running: "생성 중..."
  },
  export: {
    title: "데이터보내기",
    readPreview: "로봇에서 읽고 미리보기",
    reading: "읽는 중...",
    toExcel: "Excel로보내기"
  },
  import: {
    title: "데이터 가져오기",
    pickExcel: "Excel 가져오기 및 미리보기",
    downloadTemplate: "현재 유형 템플릿 다운로드",
    applyRobot: "로봇으로 가져오기",
    applying: "가져오는 중..."
  },
  form: {
    regType: "레지스터 유형",
    count: "개수",
    startId: "시작 ID",
    endId: "끝 ID",
    programName: "프로그램 이름",
    readMode: "읽기 모드",
    range: "범위 지정",
    all: "전체"
  },
  alert: {
    failTop20: "실패 내역(상위 20건)"
  },
  lang: {
    switcherTitle: "표시 언어 변경"
  }
};
