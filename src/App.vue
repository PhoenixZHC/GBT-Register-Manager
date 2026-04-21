<script setup lang="ts">
import { computed, h, onMounted, ref, watch } from "vue";
import { useI18n } from "vue-i18n";
import {
  NAlert,
  NButton,
  NCard,
  NDataTable,
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
import type { DataTableColumns } from "naive-ui";
import type { ConflictPolicy, ConnectionState, ReadMode, RegisterType } from "./types";
import { getCurrentWindow } from "@tauri-apps/api/window";
import {
  applyRegisters,
  connectRobot,
  disconnectRobot,
  exportPreviewToExcel,
  exportTemplate,
  fetchRobotMeta,
  getAppVersion,
  getConnectionStatus,
  readRegisters
} from "./services/tauriApi";
import { expectedHeaders, parseExcelForPreview, ExcelUserError } from "./utils/excel";
import { setStoredLocale, SUPPORTED_LOCALES, type AppLocale } from "./i18n";

type FeatureKey = "batchCreate" | "dataImport" | "dataExport";

/** 调试入口：输入该 IP 并点连接，跳过真实机器人连接，仅用于界面与流程验证 */
const DEBUG_BYPASS_IP = "255.255.255.255";

const { t, locale } = useI18n();

const message = useMessage();
const dialog = useDialog();

type RegisterConflictChoice = "overwrite" | "skip" | "stop";

/** 冲突时三选一：覆盖 / 跳过已存在 / 停止整次任务（关窗或 Esc 视为停止） */
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
            h(NButton, { tertiary: true, onClick: () => finish("stop") }, { default: () => t("conflict.stop") }),
            h(NButton, { onClick: () => finish("skip") }, { default: () => t("conflict.skipExisting") }),
            h(NButton, { type: "primary", onClick: () => finish("overwrite") }, { default: () => t("conflict.overwriteExisting") })
          ]
        )
    });
  });
}

const loading = ref(false);
const ip = ref("");
const recentIps = ref<string[]>([]);
const recentPickerKey = ref(0);
const connection = ref<ConnectionState>({ connected: false, ip: "", message: "" });
const activeFeature = ref<FeatureKey>("batchCreate");
const robotModel = ref("");
const robotVersion = ref("");
const appVersion = ref("");

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
    void getCurrentWindow().setTitle(title);
  } catch {
    /* 非 Tauri（如仅 vite 浏览器）无此 API */
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

// 数据导入导出页
const ioType = ref<RegisterType>("R");
const ioMode = ref<ReadMode>("all");
const ioStartId = ref(1);
const ioEndId = ref(10);
const ioProgramName = ref("");
const ioRows = ref<Record<string, unknown>[]>([]);
const ioDetails = ref<string[]>([]);
const fileInputRef = ref<HTMLInputElement | null>(null);

// 批量新建页
const createType = ref<RegisterType>("R");
const createProgramName = ref("");
const createStartId = ref(1);
const createCount = ref(10);
const createDetails = ref<string[]>([]);

const recentOptions = computed(() => recentIps.value.map((v) => ({ label: v, value: v })));
const isConnected = computed(() => connection.value.connected);

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

watch(locale, applyChromeLocale, { immediate: true });

function onPickRecent(v: string | null) {
  if (v) ip.value = v;
  recentPickerKey.value += 1;
}

async function refreshConnection() {
  connection.value = await getConnectionStatus();
  if (!connection.value.connected || connection.value.ip === DEBUG_BYPASS_IP) {
    robotModel.value = "";
    robotVersion.value = "";
  } else {
    await loadRobotMeta();
  }
}

async function loadRobotMeta() {
  try {
    const meta = await fetchRobotMeta();
    robotModel.value = meta.model?.trim() || "";
    robotVersion.value = meta.controllerVersion?.trim() || "";
  } catch {
    robotModel.value = "";
    robotVersion.value = "";
  }
}

async function onConnect() {
  const trimmed = ip.value.trim();
  if (!trimmed) {
    message.warning(t("messages.enterIp"));
    return;
  }
  loading.value = true;
  try {
    connection.value = await connectRobot(trimmed);
    if (connection.value.connected) {
      if (trimmed !== DEBUG_BYPASS_IP && !recentIps.value.includes(trimmed)) {
        recentIps.value = [trimmed, ...recentIps.value].slice(0, 5);
        localStorage.setItem("gbt_recent_ips", JSON.stringify(recentIps.value));
      }
      if (trimmed === DEBUG_BYPASS_IP) {
        robotModel.value = "";
        robotVersion.value = "";
      } else {
        await loadRobotMeta();
      }
      message.success(
        trimmed === DEBUG_BYPASS_IP ? t("messages.connectDebug") : t("messages.connectSuccess")
      );
    } else {
      message.error(connection.value.message || t("messages.connectFailed"));
    }
  } finally {
    loading.value = false;
  }
}

async function onDisconnect() {
  loading.value = true;
  try {
    const res = await disconnectRobot();
    message.info(res.message);
    robotModel.value = "";
    robotVersion.value = "";
    await refreshConnection();
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
  loading.value = true;
  try {
    ioRows.value = await readRegisters({
      registerType: ioType.value,
      programName: ioProgramName.value.trim() || undefined,
      selector: { mode: ioMode.value, startId: ioStartId.value, endId: ioEndId.value }
    });
    ioDetails.value = [];
    message.success(t("messages.readDone", { count: ioRows.value.length }));
  } finally {
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
    message.success(t("messages.excelPreview", { count: ioRows.value.length }));
  } catch (error) {
    if (error instanceof ExcelUserError) {
      message.error(t(error.message, error.params ?? {}));
    } else {
      message.error((error as Error).message);
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
    if (res.message === "已取消保存") return;
    res.ok ? message.success(res.message) : message.error(res.message);
  } catch (e) {
    message.error((e as Error).message || String(e));
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
  loading.value = true;
  try {
    const start = Math.min(...rowIds);
    const end = Math.max(...rowIds);
    const existingRows = await readRegisters({
      registerType: ioType.value,
      programName: ioProgramName.value.trim() || undefined,
      selector: { mode: "range", startId: start, endId: end }
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
      const choice = await promptRegisterConflict(t("conflict.bodyImport", { count: conflictCount }));
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
      rows: ioRows.value
    });
    if (res.ok) {
      ioDetails.value = [];
      message.success(res.message);
    } else {
      ioDetails.value = res.details || [];
      message.error(res.message);
    }
  } finally {
    loading.value = false;
  }
}

async function onExportTemplate() {
  loading.value = true;
  try {
    const res = await exportTemplate(ioType.value);
    if (res.message === "已取消保存") return;
    res.ok ? message.success(res.message) : message.error(res.message);
  } catch (e) {
    message.error((e as Error).message || String(e));
  } finally {
    loading.value = false;
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

async function onCreateRegisters() {
  if (!isConnected.value) return message.warning(t("messages.needConnect"));
  const start = Math.max(0, Number(createStartId.value || 0));
  const count = Math.max(1, Number(createCount.value || 0));
  if (count <= 0) return message.warning(t("messages.countPositive"));
  if (needProgramForCreate.value && !createProgramName.value.trim()) return message.warning(t("messages.pCreateNeedProgram"));
  loading.value = true;
  try {
    const end = start + count - 1;
    const existing = await readRegisters({
      registerType: createType.value,
      programName: createProgramName.value.trim() || undefined,
      selector: { mode: "range", startId: start, endId: end }
    });
    let conflictPolicy: ConflictPolicy = "skip";
    if (existing.length > 0) {
      const choice = await promptRegisterConflict(
        t("conflict.bodyCreate", { count: existing.length, start, end })
      );
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
      rows
    });
    if (res.ok) {
      createDetails.value = [];
      message.success(res.message);
    } else {
      createDetails.value = res.details || [];
      message.error(res.message);
    }
  } finally {
    loading.value = false;
  }
}

onMounted(async () => {
  try {
    appVersion.value = await getAppVersion();
  } catch {
    appVersion.value = "";
  }
  await refreshConnection();
  recentIps.value = JSON.parse(localStorage.getItem("gbt_recent_ips") || "[]");
});
</script>

<template>
  <div class="app-shell">
    <header class="top-nav">
      <div class="top-nav-left">
        <template v-if="isConnected">
          <span class="top-nav-meta-ip">{{ connection.ip }}</span>
          <span class="top-nav-meta-sep" aria-hidden="true">|</span>
          <span>{{ t("app.model") }} {{ robotModel || "—" }}</span>
          <span class="top-nav-meta-sep" aria-hidden="true">|</span>
          <span>{{ t("app.software") }} {{ robotVersion || "—" }}</span>
          <span class="top-nav-meta-sep" aria-hidden="true">|</span>
          <button type="button" class="disconnect-link" :disabled="loading" @click="onDisconnect">
            {{ t("connect.disconnect") }}
          </button>
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
            <n-input v-model:value="ip" :placeholder="t('connect.ipPlaceholder')" :disabled="loading" clearable />
            <n-select
              :key="recentPickerKey"
              :options="recentOptions"
              :placeholder="t('connect.recentPlaceholder')"
              clearable
              :disabled="loading || !recentOptions.length"
              @update:value="onPickRecent"
            />
            <n-button type="primary" :loading="loading" @click="onConnect">{{ t("connect.connect") }}</n-button>
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
                <n-button type="primary" :disabled="loading" @click="onCreateRegisters">{{ t("create.start") }}</n-button>
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
                  <n-button type="primary" :disabled="loading" @click="onReadPreviewIO">{{ t("export.readPreview") }}</n-button>
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
                    <n-button type="primary" :disabled="!ioRows.length || loading" @click="onApplyIO">{{ t("import.applyRobot") }}</n-button>
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
/* 导入/导出：上下两块卡片间距收紧，预览区整体上移 */
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
  grid-template-columns: minmax(0, 1fr) 220px 100px;
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
