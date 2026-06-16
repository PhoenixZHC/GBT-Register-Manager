<script setup lang="ts">
import { computed, h, onMounted, onUnmounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import {
  NAlert,
  NButton,
  NCard,
  NDataTable,
  NDatePicker,
  NDropdown,
  NForm,
  NFormItem,
  NInput,
  NInputNumber,
  NRadio,
  NRadioGroup,
  NSelect,
  NSpace,
  useDialog,
  useMessage
} from "naive-ui";
import type { DataTableColumns, MessageReactive } from "naive-ui";
import type { CommonResponse, ConflictPolicy, ConnectionState, ReadMode, RegisterProgressEvent, RegisterType } from "./types";
import { getCurrentWindow } from "@tauri-apps/api/window";
import { listen, type UnlistenFn } from "@tauri-apps/api/event";
import { open } from "@tauri-apps/plugin-dialog";
import {
  applyRegisters,
  connectRobot,
  disconnectRobot,
  exportControllerLogsZip,
  exportPreviewToExcel,
  exportProgramDataZip,
  exportTeachPanelLogsZip,
  exportTemplate,
  fetchRobotMeta,
  fetchRobotSdkVersion,
  getAppVersion,
  getConnectionStatus,
  installRobotExtension,
  installRobotWheel,
  readRegisters
} from "./services/tauriApi";
import { expectedHeaders, parseExcelForPreview, ExcelUserError } from "./utils/excel";
import { setStoredLocale, SUPPORTED_LOCALES, type AppLocale } from "./i18n";

type FeatureKey = "batchCreate" | "dataImport" | "dataExport" | "logDataExport" | "pluginInstall";

/** 闁荤姴顑呴崯鎶芥儊椤栫偛绀傞柕澶堝劚缂嶆捇鏌ㄥ☉娆庝孩缂侀鍙冨畷妤呭Ψ椤垵娈?IP 濡ょ姷鍋涙晶搴ㄥ磻閿濆棙浜ら柣鎰綑婢跺秹鏌ㄥ☉妯肩劮闁绘埊闄勫濠氬炊閳哄倸鐒搁柣搴℃贡閸嬬偛鈹冮埀顒勬煕閿濆啫濡烘慨鐟邦槹濞煎鎮欓弶鎴濐槻闂佹寧绋戞總鏃傚垝鎼淬劍鍋ㄩ柕濞垮€楅懝楣冩煟閿濆懐鐒告繛鑲╁缁嬪鎯旈姀顫亰缂備礁顑呴澶愭偘濞嗘垶瀚?*/
const DEBUG_BYPASS_IP = "255.255.255.255";

/** 缂備胶濮崑鎾绘煕?IPv4 闂佸搫绋勭换婵嬫偘濞嗘挻鏅慨姗嗗墯绾捐姤绻?0-255闂佹寧绋戦懟顖炲储閹寸姵濯?DEBUG_BYPASS_IP */
function isValidIPv4(ip: string): boolean {
  if (ip === DEBUG_BYPASS_IP) return true;
  const parts = ip.split(".");
  if (parts.length !== 4) return false;
  return parts.every((p) => {
    if (!/^\d{1,3}$/.test(p)) return false;
    const n = Number(p);
    return n >= 0 && n <= 255;
  });
}

/** 婵炴垶鎸告鎼佸箖濡ゅ啰鍗?IPC 闂備焦瀵ч悷銊╊敋閵堝鍎樺ù锝夘棑椤忛亶鏌ら悿顖涘涧缂佽鲸绻冪粭鐔封槈濮楀棙鈻奸柣鐘叉祩閸欌偓闁宠鐗撳浼存偐閼碱剚顔忛梺?*/
const UNSUPPORTED_ROBOT_MODEL_CODE = "GBT_UNSUPPORTED_ROBOT_MODEL";
const PLUGIN_NEEDS_TEACH_PANEL_IP_CODE = "GBT_PLUGIN_NEEDS_TEACH_PANEL_IP";
const PLUGIN_DEBUG_BYPASS_CODE = "GBT_PLUGIN_DEBUG_BYPASS";
const PLUGIN_NO_EXT_FILE_CODE = "GBT_PLUGIN_NO_EXT_FILE";
const PLUGIN_NO_WHL_FILE_CODE = "GBT_PLUGIN_NO_WHL_FILE";

function ipcMessageIsCode(e: unknown, code: string): boolean {
  const m = errMessage(e);
  return m === code || m.includes(code);
}

/** 缂傚倷鑳堕崰宥囩博閺夋埈鍤曢柛灞炬皑閸╂鏌嶉锝呅昬ssage 闂佺绻戠划宀€鑺遍幎鑺ユ櫖鐎光偓閸曨亞绱氶梺?try/finally 婵炴垶鎼╅崢钘夛耿椤撱垹绠查柡鍥ｂ偓宕囶唵闁诲簼绲绘竟鍫ュ吹瑜斿Λ鍐ㄢ枎閹捐泛绗℃繝銏″劶缁墽鎲撮敃鍌毼?*/
function errMessage(e: unknown): string {
  if (e instanceof Error) return e.message;
  if (typeof e === "string") return e;
  try {
    return JSON.stringify(e);
  } catch {
    return String(e);
  }
}

function isUnsupportedRobotModelError(e: unknown): boolean {
  return ipcMessageIsCode(e, UNSUPPORTED_ROBOT_MODEL_CODE);
}

const { t, te, locale } = useI18n();

function formatIpcError(e: unknown): string {
  if (isUnsupportedRobotModelError(e)) return t("messages.unsupportedRobotModel");
  if (ipcMessageIsCode(e, PLUGIN_NEEDS_TEACH_PANEL_IP_CODE)) return t("pluginInstall.errorNeedsTeachPanelIp");
  if (ipcMessageIsCode(e, PLUGIN_DEBUG_BYPASS_CODE)) return t("pluginInstall.errorDebugBypass");
  if (ipcMessageIsCode(e, PLUGIN_NO_EXT_FILE_CODE)) return t("pluginInstall.errorNoExtFile");
  if (ipcMessageIsCode(e, PLUGIN_NO_WHL_FILE_CODE)) return t("pluginInstall.errorNoWhlFile");
  const m = errMessage(e);
  const errKey = `errors.${m}`;
  if (te(errKey)) return t(errKey);
  return t("errors.GBT_INTERNAL_ERROR");
}

function formatRobotModelOrConnectError(e: unknown): string {
  return formatIpcError(e);
}

const message = useMessage();
const dialog = useDialog();
let progressMessageReactive: MessageReactive | undefined;
let unlistenRegisterProgress: UnlistenFn | undefined;
let progressListenerDisposed = false;
let activeProgressOp = 0;
let activeSessionId = 0;

type RegisterConflictChoice = "overwrite" | "skip" | "stop";

/** 闂佸憡鍔樼亸娆撴偘婵犲洤绫嶉柡鍫㈡暩閻熷繘姊洪銏╂Х缂佹梹鎸抽弫宥咁潩閹颁焦鑸归梺?/ 闁荤姴鎼悿鍥╂崲閸愵煈鍟呴柟缁樺笧閹界娀鏌?/ 闂佺顑嗙划宥夘敆濞戙垹鏋侀悗娑欙供閸嬔兠归悩渚殭濠殿喚鍠栭弫宥夊醇濠靛棗缍樼紓浣瑰姈椤ㄥ棝宕?Esc 闁荤喐鐟ュΛ鏃傛嫻閻旂厧纾绘繝濠傚閸撻箖鏌?*/
function promptRegisterConflict(content: string): Promise<RegisterConflictChoice> {
  return new Promise((resolve) => {
    let settled = false;
    let inst: { destroy: () => void };
    const finish = (choice: RegisterConflictChoice) => {
      if (settled) return;
      settled = true;
      inst.destroy();
      resolve(choice);
    };
    inst = dialog.warning({
      title: t("conflict.title"),
      content,
      maskClosable: false,
      closable: true,
      onClose: () => finish("stop"),
      action: () =>
        h(
          NSpace,
          { justify: "end", wrap: true, size: 12 },
          () => [
            h(
              NButton,
              {
                onClick: () => finish("stop"),
                style: "background:#fff;color:#1f2329;border:1px solid #d9d9d9;"
              },
              { default: () => t("conflict.stop") }
            ),
            h(NButton, { onClick: () => finish("skip") }, { default: () => t("conflict.skipExisting") }),
            h(NButton, { type: "primary", onClick: () => finish("overwrite") }, { default: () => t("conflict.overwriteExisting") })
          ]
        )
    });
  });
}

const loading = ref(false);
const connectBusy = ref(false);
/** 闂佺鐭囬崘銊у幀闂?IP闂佹寧绋戦悧鍡欐崲閳ь剙鈹戞径妯轰壕缂佽鲸宀告俊?*/
const ip = ref("");
/** 缂備讲鍋撻柣鎴炆戝▓宀勬煕?IP闂佹寧绋戦悧鍡氥亹閺屻儲鐒诲鑸电〒楠炪垻鈧鎮堕崕鎵箔閻旂厧瀚夐柛婵嗗閻濄倕霉濠婂嫭銇濋柍褜鍓氶懝楣冩偉閸洘顥嗛柍褜鍓涢幉鐗堟媴闂堚晝绋忛梺鎸庣☉閼活垰煤閹惧瓨濮滈悗娑櫳戦敓?TP 闂佸搫鍟晶搴ㄥ汲閳ь剛绱掑畝鈧亸銊ф濮樿泛违?*/
const teachPanelIp = ref("");
/**
 * 闂佽鍘界敮濠勬嫻?true闂佹寧绋掗懝楣冿綖閹邦喚纾奸柛顐ｇ矊閳诲繘鏌?SDK 闂佸搫鐗滈崜娆忥耿鐎涙顩烽柨婵嗘处閸婄偤鏌ㄥ☉妯荤rm(local_proxy=True)闂佹寧绋戦ˇ顓㈠焵?
 * 闂佸搫绉烽～澶婄暤?SDK 闂佸綊娼ч鍛村船?4.1.1闂?
 *  - 闂佸搫鍟版慨鐑藉Φ濮樿泛鏋佹繛鍡楃箲閻濄倝鏌ㄥ☉妯煎婵炲弶鎸诲顏嗏偓闈涙憸閹煎ジ鏌ㄥ☉姗嗘Ч闁搞劊鍔嶅顏堫敍濞嗘劦鍋?< v7.7 闂佸搫鍟冲▔娑氭崲閳ь剙顪冮妶鍫殭缂佽鲸鍨垮畷銉╊敍閵堝洤鑰?
 *  - 闂佸搫鐗嗛ˇ閬嶅Φ濮樿泛鏋佹繛鍡楃箲閻?闂佸搫鍊瑰妯好归幇顓狀浄閻犺櫣鍎ょ花姘舵煛閸滀礁鐏熺紒妤€鎳庨锝夊焵椤掑嫬瑙︽い鏍ㄧ閸婇亶鏌″鍛Щ鐟滅増鐓￠幃浠嬧€﹂幒鏃傤槷婵炴垶鎸哥粔瀛樼附閺嶎厼浼犵€广儱鎳庨～鐘绘煠閸愬樊娼熼柍?
 * 婵炴垶鎸诲鑺ュ閳哄懎绀傜€广儱娲﹂弳蹇涙煙閺夋垵妲绘繛鎻掔埣楠炲秶鏁鍓ь槷闂佷紮绲介惌鍌氼焽閻楀牏鈻旂€广儱鎳庨弲娆撴煛閸℃ɑ灏︽繝鈧捄渚桨闁靛牆鎳愮壕濠氭煕韫囨洖浠洪柍?
 */
const LOCAL_PROXY_ALWAYS_ON = true;
const recentIps = ref<string[]>([]);
const recentPickerKey = ref(0);
const connection = ref<ConnectionState>({ connected: false, ip: "", message: "" });
const activeFeature = ref<FeatureKey>("batchCreate");
const robotModel = ref("");
/** 闂佸搫鐗嗛幖顐⑩枍閹烘挾顩查弶鐐靛濞?Agilebot.Robot.SDK.A 闂佺粯顨呴悧濠傦耿娴煎瓨鏅柛锔惧房H闂佹寧绋掗悺鐚歞 /opt/python3.12/bin && ./pip3.12 list`闂佹寧绋戦懟顖炴儓瀹ュ洨鐭嗛弶鐐村缁€?`+` 闂佸憡鎸哥粔宕団偓闈涚焸閹囧醇閻斿憡瀚抽梺鎸庣☉椤︻參鍩€?*/
const robotSdkVersion = ref("");
const DEFAULT_APP_VERSION = "1.2.8";
const appVersion = ref(DEFAULT_APP_VERSION);

const langMenuOptions = [
  { label: "中文", key: "zh" },
  { label: "English", key: "en" },
  { label: "日本語", key: "ja" },
  { label: "한국어", key: "ko" },
  { label: "Русский", key: "ru" }
];

const currentLangLabel = computed(() => {
  const m: Record<AppLocale, string> = { zh: "ZH", en: "EN", ja: "JA", ko: "KO", ru: "RU" };
  return m[locale.value as AppLocale] ?? "ZH";
});

const createButtonText = computed(() => {
  return createLoading.value ? t("create.running") : t("create.start");
});

const exportReadButtonText = computed(() => {
  return ioReadLoading.value ? t("export.reading") : t("export.readPreview");
});

const importApplyButtonText = computed(() => {
  return ioApplyLoading.value ? t("import.applying") : t("import.applyRobot");
});

function onLangSelect(key: string) {
  if (!SUPPORTED_LOCALES.includes(key as AppLocale)) return;
  locale.value = key as AppLocale;
  setStoredLocale(key as AppLocale);
}

function applyChromeLocale() {
  const l = locale.value as AppLocale;
  const htmlLang: Record<AppLocale, string> = {
    zh: "zh-CN",
    en: "en",
    ja: "ja",
    ko: "ko",
    ru: "ru"
  };
  if (typeof document !== "undefined") {
    document.documentElement.lang = htmlLang[l] ?? "zh-CN";
  }
  const title = t("app.title");
  try {
    // 闂佸搫顦崯鏉戭瀶閻戞鈻旂€广儱鐗嗛崰鏇㈡煛?setTitle 婵?reject闂佹寧绋戦張顒€螣婢跺鍤曢煫鍥ㄦ煥缁€瀣煠閸撗冨幋濞村皷鏅犲畷妤€顓奸崱妞剧帛闂佸憡甯熷▔娑溿亹閹绢喖绀勯柧蹇曟嚀缁犳盯鏌￠崼顐＄盎妞わ腹鏅犻幃?Promise 闂備焦瀵ч悷銊╊敋閵堝违?
    void getCurrentWindow().setTitle(title).catch(() => {});
  } catch {
    /* 闂?Tauri闂佹寧绋戦悧鍡涖€呰缁?vite 濠电偞娼欑换妤咃綖瀹ュ闂い顓熷笧缁€鍡涙煛閸愵亜校妞?API */
  }
  if (typeof document !== "undefined") {
    document.title = title;
  }
}

const registerOptions = [
  { label: "R", value: "R" },
  { label: "P", value: "P" },
  { label: "PR", value: "PR" }
];

function localResponseMessage(res: CommonResponse, fallbackKey: string, params: Record<string, unknown> = {}): string {
  const key = res.code ? `response.${res.code}` : fallbackKey;
  return te(key) ? t(key, { ...(res.stats ?? {}), count: res.count ?? 0, ...params }) : t(fallbackKey, params);
}

function applyResultMessage(res: CommonResponse): string {
  if (!res.ok) {
    if (res.code && te(`errors.${res.code}`)) return t(`errors.${res.code}`);
    if (res.stats) return t("messages.applyFailed", res.stats);
    return localResponseMessage(res, "response.operation_failed");
  }
  if (res.stats) return t("messages.applyDone", res.stats);
  return localResponseMessage(res, "response.operation_failed");
}

function formatRegisterProgress(payload: RegisterProgressEvent): string {
  const params = {
    current: payload.current,
    total: payload.total ?? "",
    matched: payload.matched
  };
  if (payload.action === "export") {
    const phase = payload.phase ?? "download";
    if (phase === "scan") {
      if (payload.total == null || payload.total === 0) return t("progress.exportStarting");
      return t("progress.exportScan", params);
    }
    if (phase === "zip") return t("progress.exportZip", params);
    if (payload.total == null || payload.total === 0) return t("progress.exportStarting");
    return t("progress.exportDownload", params);
  }
  if (payload.action === "write") return t("progress.write", params);
  return payload.total == null ? t("progress.readAll", params) : t("progress.read", params);
}

function robotSessionId(): number {
  return connection.value.sessionId ?? 0;
}

function beginProgressOp(): number {
  activeSessionId = robotSessionId();
  activeProgressOp += 1;
  return activeProgressOp;
}

function endProgressOp(op: number): void {
  if (activeProgressOp === op) {
    activeProgressOp = 0;
    activeSessionId = 0;
    hideRegisterProgress();
  }
}

function showRegisterProgress(content: string): void {
  if (activeProgressOp === 0) return;
  // 复用同一个 loading 提示，仅原地更新文案；避免每次进度都销毁+重建导致弹窗快速闪烁，
  // 这样用户能看到 1/10 -> 2/10 ... 平滑递增，而不是直接跳到最终结果。
  if (progressMessageReactive) {
    progressMessageReactive.content = content;
    return;
  }
  progressMessageReactive = message.loading(content, { duration: 0 });
}

function hideRegisterProgress(): void {
  progressMessageReactive?.destroy();
  progressMessageReactive = undefined;
}

/**
 * 结束一次读写进度：把正在显示的进度弹窗“原地切换”成最终结果（如“写入完成”），
 * 而不是销毁进度弹窗再新建一个结果弹窗，从而避免闪烁、让进度自然过渡到完成提示。
 * 若当前没有进度弹窗（极快完成或被对话框打断），则退回为普通提示。
 */
function finishRegisterProgress(
  op: number,
  type: "success" | "error" | "warning" | "info",
  content: string
): void {
  const isActive = activeProgressOp === op;
  if (isActive && progressMessageReactive) {
    const reactive = progressMessageReactive;
    progressMessageReactive = undefined;
    activeProgressOp = 0;
    activeSessionId = 0;
    reactive.type = type;
    reactive.content = content;
    const duration = type === "error" ? 5000 : 3000;
    window.setTimeout(() => reactive.destroy(), duration);
    return;
  }
  if (isActive) endProgressOp(op);
  if (type === "success") message.success(content);
  else if (type === "error") message.error(content);
  else if (type === "warning") message.warning(content);
  else message.info(content);
}

// 闂佽桨鑳舵晶妤€鐣垫担琛″亾閻㈤潧甯堕柛娆忔閳ь剛鏁搁崢褔宕甸鐔翠簻?
const ioType = ref<RegisterType>("R");
const ioMode = ref<ReadMode>("all");
const ioStartId = ref(1);
const ioEndId = ref(10);
const ioProgramName = ref("");
const ioRows = ref<Record<string, unknown>[]>([]);
const ioDetails = ref<string[]>([]);
const ioReadLoading = ref(false);
const ioApplyLoading = ref(false);
const fileInputRef = ref<HTMLInputElement | null>(null);

// 闂佸綊娼х紞濠囧闯濞差亜妫橀柡澶庢硶缁憋箑顪?
const createType = ref<RegisterType>("R");
const createProgramName = ref("");
const createStartId = ref(1);
const createCount = ref(10);
const createDetails = ref<string[]>([]);
const createLoading = ref(false);

function startOfTodayMs(): number {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  return d.getTime();
}

/** 闂佸搫鍟ㄩ崕杈╂崲?闂佽桨鑳舵晶妤€鐣垫担琛″亾閻㈤潧甯堕柛銈庡幗閵囧嫮鍠婃径宀€鐛ラ梺鍦暯閸嬫捇姊洪銏╂Ц闁告瑦娲熷畷銏ゅ幢濡紮绱氶梺姹囧妼鐎氼厼锕㈡导鏉戞嵍濞寸厧鐡ㄧ粊鈺呮煟閹邦垼娼愭俊鐐插€垮鑽も偓娑櫭悡鍫ユ煥濞戞澧旂紒?NDatePicker闂佹寧绋戦ˇ顓㈠焵?*/
const exportLogDate = ref<number | null>(startOfTodayMs());
const logExportBusy = ref(false);

/** 闂佸湱绮敮濠傗枎閵忊懇鍋撻悷閭︽Ъ妞ゃ儱锕弫宥咁潩椤撶喐瀚抽梺?.gbtapp / .whl 闁荤姳璀﹂崹鎵閻愮儤鏅柛顐犲灪閺嗙姷绱掗婵嗗惞缂侇喗妞藉顒勫炊閿旂瓔鍋ㄩ柣搴ｆ暩椤㈠﹪鎯侀挊澶樻禆闁糕剝绋堥崑鎾村緞鐎ｎ亶浠撮梺鎸庣☉椤︻參鍩€?*/
const pluginExtLocalPath = ref("");
const pluginWhlLocalPath = ref("");
const pluginExtInstallBusy = ref(false);
const pluginWhlInstallBusy = ref(false);

const recentOptions = computed(() => recentIps.value.map((v) => ({ label: v, value: v })));
const isConnected = computed(() => connection.value.connected);

/** 闁荤姴顑呴崯鎶芥儊椤栫偛绠ｉ柡宥冨妽瀵捇寮堕埡鍐ㄤ沪閻㈩垱鎸冲顕€宕滄笟鍥ㄧ煑闂?SFTP 闁诲海鏁搁崢褔宕甸銏犖?*/
const logExportDisabled = computed(
  () => !isConnected.value || connection.value.ip === DEBUG_BYPASS_IP
);
const disconnectDisabled = computed(
  () => loading.value || logExportBusy.value || pluginExtInstallBusy.value || pluginWhlInstallBusy.value
);
/** 闂佸搫鍟版慨鐑藉Φ濮樿泛鏋佹繛鍡楃箲閻?IP 闂佸搫鍟晶搴ㄣ€呴敃鍌涘仺闁靛ě浣风驳闂佽桨鐒﹂悷銉モ枍閹烘绫嶉柕澶堝劤缁犲爼鎮楅悽闈涘付闁搞値鍙冩俊?*/
const teachPanelLogDisabled = computed(
  () => logExportDisabled.value || !(connection.value.teachPanelIp ?? "").trim()
);

/** 闂佸搫绉村ú顓€傛禒瀣唨闊洦娲忔禒娑㈡煛娴ｅ湱鎳冩繛?IP闂佹寧绋戦悧濠傤焽閻㈠憡鍤婃い蹇撳暟缁愭鎮归崶銊х缂佽鲸绻冪粙澶嬫償閵堝洨鐐曢梺绋跨箞閸庢煡銆佺€ｎ喖鐭楁い鏍ㄧ箓閸樻潙鈽夐幘宕囆㈤柟顔芥尭椤垽濡烽婊咁槴闂?*/
const teachPanelIpDisplay = computed(() => (connection.value.teachPanelIp ?? "").trim());

/** GBT-P/C/S 婵炴垶鎸诲鐟帮耿椤撶喓绠欐い鎰╁€戞禒娑㈡煛娴ｅ湱鎳冩繛?IP闂佹寧绋掗惌顔剧箔婢跺á娑㈠焵椤掆偓闇?SDK闂侀潧妫旈懗鍫曘€呴敃鍌涘仺闁靛绠戠徊璇裁归悩鐑樼【闁伙絻鍔庨幉妤呭椽閸愵亞顦㏒ 闂佸憡鐟崹鍗炍涢妶鍥╃焼闁绘垶蓱濞堝矂鏌涢敐鍐ㄥ婵犙€鍋撻梺鍝勬媼閸ㄧ晫妲愬璺何?*/
const pluginSeriesBlocksTeach = computed(() => {
  if (!isConnected.value || connection.value.ip === DEBUG_BYPASS_IP) return false;
  const m = robotModel.value.trim().toUpperCase();
  if (!m) return false;
  const isPcs = m.includes("GBT-P") || m.includes("GBT-C") || m.includes("GBT-S");
  if (!isPcs) return false;
  return !(connection.value.teachPanelIp ?? "").trim();
});

function exportDateToYmd(ms: number): string {
  const d = new Date(ms);
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

const ioColumns = computed<DataTableColumns<Record<string, unknown>>>(() =>
  expectedHeaders(ioType.value).map((key) => ({ title: key, key, ellipsis: { tooltip: true } }))
);

const needProgramForIO = computed(() => ioType.value === "P");
const needProgramForCreate = computed(() => createType.value === "P");

watch(activeFeature, (v, prev) => {
  if (
    (v === "dataImport" && prev === "dataExport") ||
    (v === "dataExport" && prev === "dataImport")
  ) {
    ioRows.value = [];
    ioDetails.value = [];
  }
});

watch(ioType, () => {
  ioRows.value = [];
  ioDetails.value = [];
});

watch(locale, applyChromeLocale, { immediate: true });

function onPickRecent(v: string | null) {
  if (v) ip.value = v;
  recentPickerKey.value += 1;
}

async function refreshConnection() {
  connection.value = await getConnectionStatus();
  if (!connection.value.connected || connection.value.ip === DEBUG_BYPASS_IP) {
    robotModel.value = "";
    robotSdkVersion.value = "";
  } else {
    try {
      await loadRobotHeader();
    } catch (e) {
      message.error(formatRobotModelOrConnectError(e) || t("messages.connectFailed"));
      connection.value = await getConnectionStatus();
      robotModel.value = "";
      robotSdkVersion.value = "";
    }
  }
}

async function loadRobotHeader() {
  robotModel.value = "";
  robotSdkVersion.value = "";
  const meta = await fetchRobotMeta();
  robotModel.value = meta.model?.trim() || "";
  const tp = (connection.value.teachPanelIp ?? "").trim();
  const m = robotModel.value.toUpperCase();
  const isPcs = m.includes("GBT-P") || m.includes("GBT-C") || m.includes("GBT-S");
  if (isPcs && !tp) {
    robotSdkVersion.value = "";
  } else {
    robotSdkVersion.value = (await fetchRobotSdkVersion(robotModel.value || null)).trim();
  }
}

async function onConnect() {
  if (connectBusy.value) return;
  const trimmed = ip.value.trim();
  const tpTrimmed = teachPanelIp.value.trim();
  if (!trimmed) {
    message.warning(t("messages.enterIp"));
    return;
  }
  if (!isValidIPv4(trimmed)) {
    message.warning(t("messages.invalidIp"));
    return;
  }
  // 缂備讲鍋撻柣鎴炆戝▓宀勬煕?IP 闂備緡鍋勯ˇ顖炴晲閻愮儤鏅悘鐐跺亹缁嬪鏌涘▎妯规捣妞も晪闄勭换鍛搭敃閿涘嫬鏅╅柣蹇撶箰瀹曨剛鎹㈤埀顒€顪冮妶鍥╁笡婵″弶鎮傚畷銉╁醇閻旀亽鈧?IPv4闂?
  if (tpTrimmed && !isValidIPv4(tpTrimmed)) {
    message.warning(t("messages.invalidTeachPanelIp"));
    return;
  }
  connectBusy.value = true;
  loading.value = true;
  let connectLoadingReactive: { destroy: () => void } | undefined;
  try {
    connectLoadingReactive = message.loading(t("messages.connecting"), { duration: 0 });
    connection.value = await connectRobot({
      controllerIp: trimmed,
      teachPanelIp: tpTrimmed || undefined,
      localProxy: LOCAL_PROXY_ALWAYS_ON
    });
    if (connection.value.connected) {
      if (trimmed !== DEBUG_BYPASS_IP && !recentIps.value.includes(trimmed)) {
        recentIps.value = [trimmed, ...recentIps.value].slice(0, 5);
        localStorage.setItem("gbt_recent_ips", JSON.stringify(recentIps.value));
      }
      if (trimmed === DEBUG_BYPASS_IP) {
        robotModel.value = "";
        robotSdkVersion.value = "";
        message.success(t("messages.connectDebug"));
      } else {
        try {
          await loadRobotHeader();
          message.success(t("messages.connectSuccess"));
        } catch (e) {
          connection.value = await getConnectionStatus();
          message.error(formatRobotModelOrConnectError(e) || t("messages.connectFailed"));
        }
      }
    } else {
      const m = connection.value.message;
      message.error(m.startsWith("GBT_") ? formatIpcError(m) : t("messages.connectFailed"));
    }
  } catch (e) {
    message.error(formatIpcError(e));
  } finally {
    connectLoadingReactive?.destroy();
    connectBusy.value = false;
    loading.value = false;
  }
}

async function onDisconnect() {
  loading.value = true;
  try {
    const res = await disconnectRobot();
    message.info(localResponseMessage(res, "messages.disconnected"));
    robotModel.value = "";
    robotSdkVersion.value = "";
    await refreshConnection();
  } catch (e) {
    message.error(formatIpcError(e));
  } finally {
    loading.value = false;
  }
}

function openImportDialog() {
  fileInputRef.value?.click();
}

async function onReadPreviewIO() {
  if (!isConnected.value) return message.warning(t("messages.needConnect"));
  if (needProgramForIO.value && !ioProgramName.value.trim()) return message.warning(t("messages.pReadNeedProgram"));
  ioReadLoading.value = true;
  loading.value = true;
  const progressOp = beginProgressOp();
  try {
    ioRows.value = await readRegisters({
      registerType: ioType.value,
      programName: ioProgramName.value.trim() || undefined,
      selector: { mode: ioMode.value, startId: ioStartId.value, endId: ioEndId.value },
      progressOpId: progressOp,
      sessionId: robotSessionId()
    });
    ioDetails.value = [];
    finishRegisterProgress(progressOp, "success", t("messages.readDone", { total: ioRows.value.length }));
  } catch (e) {
    finishRegisterProgress(progressOp, "error", formatIpcError(e));
  } finally {
    endProgressOp(progressOp);
    ioReadLoading.value = false;
    loading.value = false;
  }
}

async function onImportExcel(ev: Event) {
  const input = ev.target as HTMLInputElement;
  const file = input.files?.[0];
  if (!file) return;
  loading.value = true;
  try {
    ioRows.value = await parseExcelForPreview(file, ioType.value);
    ioDetails.value = [];
    message.success(t("messages.excelPreview", { total: ioRows.value.length }));
  } catch (error) {
    if (error instanceof ExcelUserError) {
      message.error(t(error.message, error.params ?? {}));
    } else {
      message.error(formatIpcError(error));
    }
  } finally {
    loading.value = false;
    input.value = "";
  }
}

async function onExportIO() {
  if (!ioRows.value.length) return message.warning(t("messages.noExportData"));
  loading.value = true;
  try {
    const res = await exportPreviewToExcel(ioType.value, ioRows.value);
    if (res.code === "save_cancelled") return;
    res.ok ? message.success(localResponseMessage(res, "response.export_saved")) : message.error(localResponseMessage(res, "response.operation_failed"));
  } catch (e) {
    message.error(formatIpcError(e));
  } finally {
    loading.value = false;
  }
}

function collectImportRowIds(rows: Record<string, unknown>[]): number[] {
  const ids: number[] = [];
  for (const row of rows) {
    const id = Number(row["ID"]);
    if (!Number.isNaN(id)) ids.push(id);
  }
  return ids;
}

async function onApplyIO() {
  if (!isConnected.value) return message.warning(t("messages.needConnect"));
  if (!ioRows.value.length) return message.warning(t("messages.needPreviewData"));
  if (needProgramForIO.value && !ioProgramName.value.trim()) return message.warning(t("messages.pWriteNeedProgram"));
  const rowIds = collectImportRowIds(ioRows.value);
  if (!rowIds.length) return message.warning(t("messages.noValidRegIds"));
  ioApplyLoading.value = true;
  loading.value = true;
  let progressOp = 0;
  try {
    const start = Math.min(...rowIds);
    const end = Math.max(...rowIds);
    progressOp = beginProgressOp();
    const existingRows = await readRegisters({
      registerType: ioType.value,
      programName: ioProgramName.value.trim() || undefined,
      selector: { mode: "range", startId: start, endId: end },
      progressOpId: progressOp,
      sessionId: robotSessionId()
    });
    const existingIds = new Set<number>();
    for (const row of existingRows) {
      const id = Number(row["ID"]);
      if (!Number.isNaN(id)) existingIds.add(id);
    }
    let conflictPolicy: ConflictPolicy = "skip";
    const uniqueImportIds = [...new Set(rowIds)];
    const conflictCount = uniqueImportIds.filter((id) => existingIds.has(id)).length;
    if (conflictCount > 0) {
      hideRegisterProgress();
      const choice = await promptRegisterConflict(t("conflict.bodyImport", { total: conflictCount }));
      if (choice === "stop") {
        message.info(t("messages.importCancelled"));
        return;
      }
      conflictPolicy = choice === "overwrite" ? "overwrite" : "skip";
    }
    const res = await applyRegisters({
      registerType: ioType.value,
      programName: ioProgramName.value.trim() || undefined,
      conflictPolicy,
      rows: ioRows.value,
      progressOpId: progressOp,
      sessionId: robotSessionId()
    });
    if (res.ok) {
      ioDetails.value = [];
      finishRegisterProgress(progressOp, "success", applyResultMessage(res));
    } else {
      ioDetails.value = res.details || [];
      finishRegisterProgress(progressOp, "error", applyResultMessage(res));
    }
  } catch (e) {
    finishRegisterProgress(progressOp, "error", formatIpcError(e));
  } finally {
    if (progressOp) endProgressOp(progressOp);
    ioApplyLoading.value = false;
    loading.value = false;
  }
}

async function onExportTemplate() {
  loading.value = true;
  try {
    const res = await exportTemplate(ioType.value);
    if (res.code === "save_cancelled") return;
    res.ok ? message.success(localResponseMessage(res, "response.template_saved")) : message.error(localResponseMessage(res, "response.operation_failed"));
  } catch (e) {
    message.error(formatIpcError(e));
  } finally {
    loading.value = false;
  }
}

function isExportSaveCancelled(res: CommonResponse): boolean {
  return res.code === "save_cancelled";
}

async function onExportControllerLogsZip() {
  if (logExportDisabled.value) return message.warning(t("messages.needConnect"));
  const ts = exportLogDate.value;
  if (ts == null) return message.warning(t("logExport.pickDate"));
  logExportBusy.value = true;
  const progressOp = beginProgressOp();
  showRegisterProgress(t("progress.exportStarting"));
  try {
    const res = await exportControllerLogsZip({
      controllerIp: connection.value.ip,
      dateYyyyMmDd: exportDateToYmd(ts),
      sessionId: robotSessionId(),
      progressOpId: progressOp
    });
    if (isExportSaveCancelled(res)) return;
    res.ok
      ? finishRegisterProgress(progressOp, "success", localResponseMessage(res, "response.logs_exported"))
      : finishRegisterProgress(progressOp, "error", localResponseMessage(res, "response.no_logs"));
  } catch (e) {
    finishRegisterProgress(progressOp, "error", formatIpcError(e));
  } finally {
    endProgressOp(progressOp);
    logExportBusy.value = false;
  }
}

async function onExportTeachPanelLogsZip() {
  if (teachPanelLogDisabled.value) {
    if (logExportDisabled.value) return message.warning(t("messages.needConnect"));
    return message.warning(t("logExport.noTeachIpHint"));
  }
  const ts = exportLogDate.value;
  if (ts == null) return message.warning(t("logExport.pickDate"));
  const tp = (connection.value.teachPanelIp ?? "").trim();
  logExportBusy.value = true;
  const progressOp = beginProgressOp();
  showRegisterProgress(t("progress.exportStarting"));
  try {
    const res = await exportTeachPanelLogsZip({
      controllerIp: connection.value.ip,
      teachPanelIp: tp,
      dateYyyyMmDd: exportDateToYmd(ts),
      sessionId: robotSessionId(),
      progressOpId: progressOp
    });
    if (isExportSaveCancelled(res)) return;
    res.ok
      ? finishRegisterProgress(progressOp, "success", localResponseMessage(res, "response.logs_exported"))
      : finishRegisterProgress(progressOp, "error", localResponseMessage(res, "response.no_logs"));
  } catch (e) {
    finishRegisterProgress(progressOp, "error", formatIpcError(e));
  } finally {
    endProgressOp(progressOp);
    logExportBusy.value = false;
  }
}

async function onExportProgramDataZip() {
  if (logExportDisabled.value) return message.warning(t("messages.needConnect"));
  logExportBusy.value = true;
  const progressOp = beginProgressOp();
  showRegisterProgress(t("progress.exportStarting"));
  try {
    const res = await exportProgramDataZip({
      controllerIp: connection.value.ip,
      sessionId: robotSessionId(),
      progressOpId: progressOp
    });
    if (isExportSaveCancelled(res)) return;
    res.ok
      ? finishRegisterProgress(progressOp, "success", localResponseMessage(res, "response.program_data_exported"))
      : finishRegisterProgress(progressOp, "error", localResponseMessage(res, "response.operation_failed"));
  } catch (e) {
    finishRegisterProgress(progressOp, "error", formatIpcError(e));
  } finally {
    endProgressOp(progressOp);
    logExportBusy.value = false;
  }
}

async function onPickPluginExtensionFile() {
  try {
    const sel = await open({
      multiple: false,
      filters: [{ name: t("pluginInstall.fileFilterExt"), extensions: ["gbtapp"] }]
    });
    if (sel === null) return;
    if (typeof sel === "string") pluginExtLocalPath.value = sel;
    else if (Array.isArray(sel) && sel[0]) pluginExtLocalPath.value = sel[0];
  } catch (e) {
    message.error(formatIpcError(e));
  }
}

async function onPickPluginWhlFile() {
  try {
    const sel = await open({
      multiple: false,
      filters: [{ name: t("pluginInstall.fileFilterWhl"), extensions: ["whl"] }]
    });
    if (sel === null) return;
    if (typeof sel === "string") pluginWhlLocalPath.value = sel;
    else if (Array.isArray(sel) && sel[0]) pluginWhlLocalPath.value = sel[0];
  } catch (e) {
    message.error(formatIpcError(e));
  }
}

async function onInstallPluginExtension() {
  if (!isConnected.value) return message.warning(t("messages.needConnect"));
  if (connection.value.ip === DEBUG_BYPASS_IP) return message.warning(t("pluginInstall.errorDebugBypass"));
  if (!pluginExtLocalPath.value.trim()) return message.warning(t("pluginInstall.noExtFile"));
  pluginExtInstallBusy.value = true;
  try {
    const info = await installRobotExtension(pluginExtLocalPath.value.trim(), robotModel.value || null);
    message.success(t("pluginInstall.extSuccess", { name: info.name || "-", version: info.version || "-" }));
  } catch (e) {
    message.error(formatRobotModelOrConnectError(e));
  } finally {
    pluginExtInstallBusy.value = false;
  }
}

async function onInstallPluginWhl() {
  if (!isConnected.value) return message.warning(t("messages.needConnect"));
  if (connection.value.ip === DEBUG_BYPASS_IP) return message.warning(t("pluginInstall.errorDebugBypass"));
  if (!pluginWhlLocalPath.value.trim()) return message.warning(t("pluginInstall.noWhlFile"));
  pluginWhlInstallBusy.value = true;
  try {
    const res = await installRobotWheel(pluginWhlLocalPath.value.trim(), robotModel.value || null);
    if (res.ok) message.success(localResponseMessage(res, "pluginInstall.whlSuccess"));
    else message.error(localResponseMessage(res, "response.operation_failed"));
  } catch (e) {
    message.error(formatRobotModelOrConnectError(e));
  } finally {
    pluginWhlInstallBusy.value = false;
  }
}

function buildCreateRows(start: number, count: number): Record<string, unknown>[] {
  const rows: Record<string, unknown>[] = [];
  for (let i = 0; i < count; i += 1) {
    const id = start + i;
    if (createType.value === "R") {
      rows.push({ type: "R", ID: id, value: 0 });
    } else if (createType.value === "PR") {
      rows.push({
        TYPE: "PR",
        ID: id,
        X: 0,
        Y: 0,
        Z: 0,
        A: 0,
        B: 0,
        C: 0,
        coord: "L"
      });
    } else {
      rows.push({
        Type: "P",
        ID: id,
        X: 0,
        Y: 0,
        Z: 0,
        A: 0,
        B: 0,
        C: 0,
        TF: 0,
        UF: 0,
        Coord: "L"
      });
    }
  }
  return rows;
}

function formatIdsForConflict(ids: number[]): string {
  if (!ids.length) return "";
  const sorted = [...new Set(ids)].sort((a, b) => a - b);
  return sorted.map((id) => `ID${id}`).join(", ");
}

function createConflictContent(idsText: string): string {
  return t("conflict.bodyCreate", { ids: idsText });
}

async function onCreateRegisters() {
  if (!isConnected.value) return message.warning(t("messages.needConnect"));
  const start = Math.max(0, Number(createStartId.value || 0));
  const count = Math.max(1, Number(createCount.value || 0));
  if (count <= 0) return message.warning(t("messages.countPositive"));
  if (needProgramForCreate.value && !createProgramName.value.trim()) return message.warning(t("messages.pCreateNeedProgram"));
  createLoading.value = true;
  loading.value = true;
  let progressOp = 0;
  try {
    const end = start + count - 1;
    progressOp = beginProgressOp();
    const existing = await readRegisters({
      registerType: createType.value,
      programName: createProgramName.value.trim() || undefined,
      selector: { mode: "range", startId: start, endId: end },
      progressOpId: progressOp,
      sessionId: robotSessionId()
    });
    let conflictPolicy: ConflictPolicy = "skip";
    if (existing.length > 0) {
      const existingIds = existing
        .map((row) => Number(row["ID"]))
        .filter((id) => !Number.isNaN(id));
      const idsText = formatIdsForConflict(existingIds);
      if (!idsText) {
        message.error(t("messages.noValidRegIds"));
        return;
      }
      hideRegisterProgress();
      const choice = await promptRegisterConflict(createConflictContent(idsText));
      if (choice === "stop") {
        message.info(t("messages.createCancelled"));
        return;
      }
      conflictPolicy = choice === "overwrite" ? "overwrite" : "skip";
    }
    const rows = buildCreateRows(start, count);
    const res = await applyRegisters({
      registerType: createType.value,
      programName: createProgramName.value.trim() || undefined,
      conflictPolicy,
      rows,
      progressOpId: progressOp,
      sessionId: robotSessionId()
    });
    if (res.ok) {
      createDetails.value = [];
      finishRegisterProgress(progressOp, "success", applyResultMessage(res));
    } else {
      createDetails.value = res.details || [];
      finishRegisterProgress(progressOp, "error", applyResultMessage(res));
    }
  } catch (e) {
    finishRegisterProgress(progressOp, "error", formatIpcError(e));
  } finally {
    if (progressOp) endProgressOp(progressOp);
    createLoading.value = false;
    loading.value = false;
  }
}

onMounted(async () => {
  const unlisten = await listen<RegisterProgressEvent>("register-progress", (event) => {
    if (activeProgressOp === 0) return;
    const { opId, sessionId } = event.payload;
    if (sessionId == null || sessionId !== activeSessionId) return;
    if (opId == null || opId !== activeProgressOp) return;
    showRegisterProgress(formatRegisterProgress(event.payload));
  });
  if (progressListenerDisposed) {
    unlisten();
    return;
  }
  unlistenRegisterProgress = unlisten;
  try {
    appVersion.value = await getAppVersion();
  } catch {
    appVersion.value = DEFAULT_APP_VERSION;
  }
  await refreshConnection();
  try {
    recentIps.value = JSON.parse(localStorage.getItem("gbt_recent_ips") || "[]");
  } catch {
    recentIps.value = [];
  }
});

onUnmounted(() => {
  progressListenerDisposed = true;
  unlistenRegisterProgress?.();
  activeProgressOp = 0;
  activeSessionId = 0;
  hideRegisterProgress();
});
</script>

<template>
  <div class="app-shell">
    <header class="top-nav">
      <div class="top-nav-left">
        <template v-if="isConnected">
          <div class="top-nav-header-meta" role="status">
            <div class="top-nav-header-col top-nav-header-col--ip">
              <div class="top-nav-header-line">
                <span class="top-nav-header-label">{{ t("app.controllerIp") }}</span>
                <span class="top-nav-header-value">{{ connection.ip }}</span>
              </div>
              <div v-if="teachPanelIpDisplay" class="top-nav-header-line">
                <span class="top-nav-header-label">{{ t("app.teachPanelIp") }}</span>
                <span class="top-nav-header-value">{{ teachPanelIpDisplay }}</span>
              </div>
            </div>
            <span class="top-nav-meta-sep" aria-hidden="true">|</span>
            <div class="top-nav-header-col">
              <div class="top-nav-header-line">
                <span class="top-nav-header-label">{{ t("app.model") }}</span>
                <span class="top-nav-header-value">{{ robotModel || "-" }}</span>
              </div>
            </div>
            <span class="top-nav-meta-sep" aria-hidden="true">|</span>
            <div class="top-nav-header-col">
              <div class="top-nav-header-line">
                <span class="top-nav-header-label">{{ t("app.robotSdk") }}</span>
                <span class="top-nav-header-value top-nav-header-value--sdk">{{ robotSdkVersion || "-" }}</span>
              </div>
            </div>
            <span class="top-nav-meta-sep" aria-hidden="true">|</span>
            <button type="button" class="disconnect-link" :disabled="disconnectDisabled" @click="onDisconnect">
              {{ t("connect.disconnect") }}
            </button>
          </div>
        </template>
      </div>
      <div class="top-nav-title">{{ t("app.title") }}</div>
      <div class="top-nav-right">
        <n-dropdown trigger="click" :options="langMenuOptions" @select="onLangSelect">
          <button type="button" class="lang-switcher" :title="t('lang.switcherTitle')">
            {{ currentLangLabel }}
          </button>
        </n-dropdown>
        <span class="top-nav-meta-sep top-nav-meta-sep--right" aria-hidden="true">|</span>
        <span class="top-nav-version">{{ appVersion ? `v${appVersion}` : "" }}</span>
      </div>
    </header>
    <main class="main-area">
      <div class="content-inner" :class="{ 'content-inner--workspace': isConnected }">
        <section v-if="!isConnected" class="hero-connect connect-only">
          <h1 class="section-title">{{ t("connect.title") }}</h1>
          <div class="connect-grid">
            <n-input
              v-model:value="ip"
              :placeholder="t('connect.controllerIpPlaceholder')"
              :disabled="connectBusy"
              clearable
            />
            <n-input
              v-model:value="teachPanelIp"
              :placeholder="t('connect.teachPanelIpPlaceholder')"
              :disabled="connectBusy"
              clearable
            />
            <n-select
              :key="recentPickerKey"
              :options="recentOptions"
              :placeholder="t('connect.recentPlaceholder')"
              clearable
              :disabled="connectBusy || !recentOptions.length"
              @update:value="onPickRecent"
            />
            <n-button type="primary" :loading="connectBusy" :disabled="connectBusy" @click="onConnect">{{ t("connect.connect") }}</n-button>
          </div>
        </section>

        <div v-else class="workspace-shell">
          <aside class="sidebar">
            <div class="sidebar-title">{{ t("sidebar.title") }}</div>
            <button class="side-btn" :class="{ active: activeFeature === 'batchCreate' }" @click="activeFeature = 'batchCreate'">
              {{ t("sidebar.batchCreate") }}
            </button>
            <button class="side-btn" :class="{ active: activeFeature === 'dataExport' }" @click="activeFeature = 'dataExport'">
              {{ t("sidebar.dataExport") }}
            </button>
            <button class="side-btn" :class="{ active: activeFeature === 'dataImport' }" @click="activeFeature = 'dataImport'">
              {{ t("sidebar.dataImport") }}
            </button>
            <button class="side-btn" :class="{ active: activeFeature === 'logDataExport' }" @click="activeFeature = 'logDataExport'">
              {{ t("sidebar.logDataExport") }}
            </button>
            <button class="side-btn" :class="{ active: activeFeature === 'pluginInstall' }" @click="activeFeature = 'pluginInstall'">
              {{ t("sidebar.pluginInstall") }}
            </button>
          </aside>

          <section class="feature-area">
            <n-card v-if="activeFeature === 'batchCreate'" class="card-apple section-light" :bordered="false" size="medium">
              <template #header>
                <h2 class="section-title section-title--on-light">{{ t("create.cardTitle") }}</h2>
              </template>
              <n-form label-placement="top" :show-feedback="false">
                <div class="create-inline-row">
                  <n-form-item :label="t('form.regType')" class="fixed-field fixed-field--type">
                    <n-select v-model:value="createType" :options="registerOptions" />
                  </n-form-item>
                  <n-form-item :label="t('form.count')" class="fixed-field fixed-field--num">
                    <n-input-number v-model:value="createCount" :min="1" :show-button="false" style="width: 100%" />
                  </n-form-item>
                  <n-form-item :label="t('form.startId')" class="fixed-field fixed-field--num">
                    <n-input-number v-model:value="createStartId" :min="0" :show-button="false" style="width: 100%" />
                  </n-form-item>
                </div>
                <n-form-item v-if="createType === 'P'" :label="t('form.programName')" class="fixed-field fixed-field--program">
                  <n-input v-model:value="createProgramName" />
                </n-form-item>
              </n-form>
              <div class="toolbar-row">
                <n-button type="primary" :disabled="loading" :loading="createLoading" @click="onCreateRegisters">
                  {{ createButtonText }}
                </n-button>
              </div>
              <n-alert v-if="createDetails.length" type="warning" class="alert-block" :title="t('alert.failTop20')">
                <div v-for="(d, i) in createDetails.slice(0, 20)" :key="`${d}-${i}`">{{ d }}</div>
              </n-alert>
            </n-card>

            <template v-else-if="activeFeature === 'dataExport'">
              <div class="feature-io-stack">
              <n-card class="card-apple section-light" :bordered="false" size="medium">
                <template #header><h2 class="section-title section-title--on-light">{{ t("export.title") }}</h2></template>
                <n-form label-placement="top" :show-feedback="false">
                  <div class="create-inline-row">
                    <n-form-item :label="t('form.regType')" class="fixed-field fixed-field--type">
                      <n-select v-model:value="ioType" :options="registerOptions" />
                    </n-form-item>
                    <n-form-item :label="t('form.readMode')" class="fixed-field fixed-field--mode">
                      <n-radio-group v-model:value="ioMode">
                        <n-space
                          ><n-radio value="range">{{ t("form.range") }}</n-radio
                          ><n-radio value="all">{{ t("form.all") }}</n-radio></n-space
                        >
                      </n-radio-group>
                    </n-form-item>
                    <template v-if="ioMode === 'range'">
                      <n-form-item :label="t('form.startId')" class="fixed-field fixed-field--num">
                        <n-input-number v-model:value="ioStartId" :min="0" :show-button="false" style="width: 100%" />
                      </n-form-item>
                      <n-form-item :label="t('form.endId')" class="fixed-field fixed-field--num">
                        <n-input-number v-model:value="ioEndId" :min="0" :show-button="false" style="width: 100%" />
                      </n-form-item>
                    </template>
                  </div>
                  <n-form-item v-if="ioType === 'P'" :label="t('form.programName')" class="fixed-field fixed-field--program">
                    <n-input v-model:value="ioProgramName" />
                  </n-form-item>
                </n-form>
                <div class="toolbar-row">
                  <n-button type="primary" :disabled="loading" :loading="ioReadLoading" @click="onReadPreviewIO">
                    {{ exportReadButtonText }}
                  </n-button>
                </div>
              </n-card>
              <n-card class="card-apple section-light card-apple--io-preview" :bordered="false" size="medium">
                <div class="preview-toolbar preview-toolbar--actions-only preview-toolbar--io-tight">
                  <div class="preview-toolbar__right">
                    <n-button tertiary :disabled="!ioRows.length || loading" @click="onExportIO">{{ t("export.toExcel") }}</n-button>
                  </div>
                </div>
                <div class="table-wrap">
                  <n-data-table flex-height style="height: 100%" :columns="ioColumns" :data="ioRows" striped :bordered="false" size="small" />
                </div>
              </n-card>
              </div>
            </template>

            <template v-else-if="activeFeature === 'dataImport'">
              <div class="feature-io-stack">
              <n-card class="card-apple section-light" :bordered="false" size="medium">
                <template #header><h2 class="section-title section-title--on-light">{{ t("import.title") }}</h2></template>
                <n-form label-placement="top" :show-feedback="false">
                  <div class="create-inline-row">
                    <n-form-item :label="t('form.regType')" class="fixed-field fixed-field--type">
                      <n-select v-model:value="ioType" :options="registerOptions" />
                    </n-form-item>
                    <n-form-item
                      v-if="ioType === 'P'"
                      :label="t('form.programName')"
                      class="fixed-field fixed-field--program fixed-field--program-inline"
                    >
                      <n-input v-model:value="ioProgramName" />
                    </n-form-item>
                  </div>
                </n-form>
                <div class="toolbar-row">
                  <input ref="fileInputRef" type="file" class="visually-hidden" accept=".xlsx,.xls" :disabled="loading" @change="onImportExcel" />
                  <n-button type="primary" :disabled="loading" @click="openImportDialog">{{ t("import.pickExcel") }}</n-button>
                  <n-button tertiary :disabled="loading" @click="onExportTemplate">{{ t("import.downloadTemplate") }}</n-button>
                </div>
              </n-card>
              <n-card class="card-apple section-light card-apple--io-preview" :bordered="false" size="medium">
                <div class="preview-toolbar preview-toolbar--actions-only preview-toolbar--io-tight">
                  <div class="preview-toolbar__right">
                    <n-button type="primary" :disabled="!ioRows.length || loading" :loading="ioApplyLoading" @click="onApplyIO">
                      {{ importApplyButtonText }}
                    </n-button>
                  </div>
                </div>
                <div class="table-wrap">
                  <n-data-table flex-height style="height: 100%" :columns="ioColumns" :data="ioRows" striped :bordered="false" size="small" />
                </div>
                <n-alert v-if="ioDetails.length" type="warning" class="alert-block" :title="t('alert.failTop20')">
                  <div v-for="(d, i) in ioDetails.slice(0, 20)" :key="`${d}-${i}`">{{ d }}</div>
                </n-alert>
              </n-card>
              </div>
            </template>

            <n-card
              v-else-if="activeFeature === 'logDataExport'"
              class="card-apple section-light"
              :bordered="false"
              size="medium"
            >
              <template #header>
                <h2 class="section-title section-title--on-light">{{ t("logExport.cardTitle") }}</h2>
              </template>
              <n-alert v-if="logExportDisabled" type="warning" class="alert-block" :title="t('logExport.needConnectHint')" />
              <n-alert v-else-if="teachPanelLogDisabled" type="info" class="alert-block" :title="t('logExport.noTeachIpHint')" />
              <n-form label-placement="top" :show-feedback="false">
                <n-form-item :label="t('logExport.pickDate')">
                  <n-date-picker
                    v-model:value="exportLogDate"
                    type="date"
                    :disabled="logExportBusy"
                    clearable
                    style="max-width: 280px"
                  />
                </n-form-item>
              </n-form>
              <p class="log-export-hint">{{ t("logExport.hintProgramData") }}</p>
              <div class="toolbar-row toolbar-row--wrap">
                <n-button
                  type="primary"
                  :disabled="logExportDisabled || logExportBusy || exportLogDate == null"
                  :loading="logExportBusy"
                  @click="onExportControllerLogsZip"
                >
                  {{ t("logExport.exportControllerLogs") }}
                </n-button>
                <n-button
                  :disabled="teachPanelLogDisabled || logExportBusy || exportLogDate == null"
                  :loading="logExportBusy"
                  @click="onExportTeachPanelLogsZip"
                >
                  {{ t("logExport.exportTeachPanelLogs") }}
                </n-button>
                <n-button :disabled="logExportDisabled || logExportBusy" :loading="logExportBusy" @click="onExportProgramDataZip">
                  {{ t("logExport.exportProgramData") }}
                </n-button>
              </div>
            </n-card>

            <n-card
              v-else-if="activeFeature === 'pluginInstall'"
              class="card-apple section-light"
              :bordered="false"
              size="medium"
            >
              <template #header>
                <h2 class="section-title section-title--on-light">{{ t("pluginInstall.title") }}</h2>
              </template>
              <n-alert v-if="pluginSeriesBlocksTeach" type="warning" class="alert-block" :title="t('pluginInstall.seriesNeedsTeachPanel')" />
              <div class="plugin-install-stack">
                <n-form label-placement="top" :show-feedback="false">
                  <n-form-item :label="t('pluginInstall.extPathLabel')">
                    <n-input
                      v-model:value="pluginExtLocalPath"
                      type="textarea"
                      :autosize="{ minRows: 1, maxRows: 3 }"
                      readonly
                      :placeholder="t('pluginInstall.extPathPlaceholder')"
                    />
                  </n-form-item>
                  <div class="toolbar-row">
                    <n-button :disabled="pluginExtInstallBusy" @click="onPickPluginExtensionFile">{{ t("pluginInstall.pickExt") }}</n-button>
                    <n-button
                      type="primary"
                      :disabled="loading || pluginExtInstallBusy || pluginSeriesBlocksTeach"
                      :loading="pluginExtInstallBusy"
                      @click="onInstallPluginExtension"
                    >
                      {{ t("pluginInstall.installExt") }}
                    </n-button>
                  </div>
                </n-form>
                <n-form label-placement="top" :show-feedback="false">
                  <n-form-item :label="t('pluginInstall.whlPathLabel')">
                    <n-input
                      v-model:value="pluginWhlLocalPath"
                      type="textarea"
                      :autosize="{ minRows: 1, maxRows: 3 }"
                      readonly
                      :placeholder="t('pluginInstall.whlPathPlaceholder')"
                    />
                  </n-form-item>
                  <div class="toolbar-row">
                    <n-button :disabled="pluginWhlInstallBusy" @click="onPickPluginWhlFile">{{ t("pluginInstall.pickWhl") }}</n-button>
                    <n-button
                      type="primary"
                      :disabled="loading || pluginWhlInstallBusy || pluginSeriesBlocksTeach"
                      :loading="pluginWhlInstallBusy"
                      @click="onInstallPluginWhl"
                    >
                      {{ t("pluginInstall.installWhl") }}
                    </n-button>
                  </div>
                </n-form>
              </div>
            </n-card>
          </section>
        </div>
      </div>
    </main>
  </div>
</template>

<style scoped>
.hero-connect {
  background: #000;
  color: #fff;
  border-radius: 12px;
  padding: 22px 24px 20px;
}
.hero-connect .section-title {
  margin: 0 0 26px;
}
.connect-only {
  max-width: 760px;
  margin: 80px auto;
}
.workspace-shell {
  display: grid;
  grid-template-columns: 220px minmax(0, 1fr);
  gap: 16px;
}
.sidebar {
  background: linear-gradient(180deg, #111214 0%, #17181b 100%);
  color: #fff;
  border-radius: 12px;
  padding: 16px 14px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  display: flex;
  flex-direction: column;
  gap: 14px;
  height: fit-content;
}
.sidebar-title {
  font-size: 16px;
  font-weight: 600;
  letter-spacing: -0.12px;
  color: #f5f5f7;
  margin-bottom: 4px;
}
.side-btn {
  border: 1px solid rgba(255, 255, 255, 0.14);
  background: rgba(255, 255, 255, 0.04);
  color: rgba(255, 255, 255, 0.92);
  border-radius: 8px;
  padding: 12px 14px;
  text-align: left;
  cursor: pointer;
}
.side-btn.active {
  background: #0071e3;
  border-color: #0071e3;
  color: #fff;
}
.feature-area {
  display: grid;
  gap: 20px;
}
/* 闁诲海鏁搁崢褔宕?闁诲海鏁搁崢褔宕甸銏℃櫖婵﹩鍋嗛悷鎰槈閹炬剚鍎庨悶姘朵憾瀹曠螖閳ь剙鐣烽柆宥嗗亱闁搞儺鍓氶敍鐔兼偣閻戞绠栭柡浣告贡濡叉劘顧傜紒杈ㄧ箖閿涙劙宕熼鍛秾闂佸憡鐗滈崕銈夊汲閿濆棙濯撮柟鎹愬皺閻熸劗绱?*/
.feature-io-stack {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.feature-io-stack .card-apple--io-preview :deep(.n-card__content) {
  padding-top: 4px;
}
.feature-io-stack .preview-toolbar--io-tight {
  margin-bottom: 8px;
}
.feature-io-stack > .card-apple:first-of-type :deep(.n-card__content) {
  padding-bottom: 12px;
}
.section-title--on-light {
  color: #1d1d1f;
  margin: 0;
}
.connect-grid {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr) 200px 100px;
  gap: 12px;
  align-items: end;
}
.pose-grid {
  grid-template-columns: repeat(3, minmax(0, 160px));
}
.create-inline-row {
  display: flex;
  flex-wrap: wrap;
  gap: 0 14px;
  align-items: flex-start;
}
.fixed-field {
  margin-bottom: 0;
}
.fixed-field--type {
  width: 160px;
}
.fixed-field--num {
  width: 140px;
}
.fixed-field--mode {
  width: 200px;
  flex-shrink: 0;
}
.fixed-field--program {
  width: 320px;
  margin-top: 8px;
}
.fixed-field--program-inline {
  margin-top: 0;
}
.visually-hidden {
  position: absolute;
  width: 1px;
  height: 1px;
  padding: 0;
  margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}
.lang-switcher {
  margin: 0;
  padding: 2px 8px;
  border: 1px solid rgba(255, 255, 255, 0.28);
  border-radius: 6px;
  background: rgba(255, 255, 255, 0.08);
  font: inherit;
  font-size: 11px;
  font-weight: 600;
  letter-spacing: 0.04em;
  color: rgba(255, 255, 255, 0.92);
  cursor: pointer;
  line-height: 1.35;
}
.lang-switcher:hover {
  background: rgba(255, 255, 255, 0.14);
}
.top-nav-meta-sep--right {
  margin: 0 6px;
}
.top-nav-version {
  color: rgba(255, 255, 255, 0.65);
}
@media (max-width: 1024px) {
  .workspace-shell {
    grid-template-columns: 1fr;
  }
  .connect-grid {
    grid-template-columns: 1fr;
  }
}
</style>


