<script setup lang="ts">
import { computed, h, onMounted, onUnmounted, ref } from "vue";
import { useI18n } from "vue-i18n";
import { NAlert, NButton, NDataTable, NSpin, useMessage } from "naive-ui";
import type { DataTableColumns } from "naive-ui";
import { listen, type UnlistenFn } from "@tauri-apps/api/event";
import { cancelControllerDiscovery, checkControllerDiscovery, openNpcapDownload, startControllerDiscovery } from "../services/tauriApi";
import type { DiscoveryCheck, DiscoveryEvent, DiscoveryWarning, DiscoveredController } from "../types";

const emit = defineEmits<{ back: []; select: [ip: string] }>();
const { t, te } = useI18n();
const message = useMessage();
const check = ref<DiscoveryCheck | null>(null);
const rows = ref<DiscoveredController[]>([]);
const warnings = ref<DiscoveryWarning[]>([]);
const stage = ref("checking");
const error = ref("");
const leaving = ref(false);
const starting = ref(false);
let scanId = "";
let disposed = false;
let generation = 0;
let unlisten: UnlistenFn | undefined;
let pendingStart: Promise<void> | undefined;
let pendingCheck: Promise<DiscoveryCheck> | undefined;
const busy = computed(() => stage.value === "checking" || stage.value === "scanning" || leaving.value || starting.value);
const addressConflict = computed(() => rows.value.some((row, index, list) => row.mac && list.some((other, j) => j !== index && other.mac && other.ip === row.ip && other.mac !== row.mac)));
const incompleteIdentity = computed(() => rows.value.some(row => row.macStatus !== "valid"));
function describe(code: unknown): string {
  const key = `discovery.errors.${String(code)}`;
  return t(te(key) ? key : "discovery.errors.internal");
}
function adapterName(id?: string): string {
  return check.value?.interfaces.find(i => i.id === id)?.name ?? id ?? "";
}
function onEvent(payload: DiscoveryEvent) {
  if (disposed || payload.scanId !== scanId) return;
  if (payload.kind === "interfaces" && payload.interfaces && check.value) {
    check.value.interfaces = payload.interfaces;
    // 扫描重新打开接口；清除预检警告，以本轮实际结果为准。
    warnings.value = [];
  } else if (payload.kind === "device" && payload.device) {
    const row = payload.device;
    const index = rows.value.findIndex(item => item.key === row.key);
    if (index >= 0) rows.value[index] = row;
    else rows.value.push(row);
  } else if (payload.kind === "warning") {
    const warning = { code: payload.code ?? "internal", interfaceId: payload.interfaceId };
    if (!warnings.value.some(w => w.code === warning.code && w.interfaceId === warning.interfaceId)) warnings.value.push(warning);
  } else if (payload.kind === "error") {
    error.value = payload.code ?? "internal";
    stage.value = "failed";
  } else if (payload.kind === "finished") {
    stage.value = payload.reason === "cancelled" ? "stopped" : "complete";
  }
}
async function stop() {
  starting.value = true;
  try {
    // 启动命令完成后再取消，防止快速返回时先取消、后启动。
    await pendingStart?.catch(() => {});
    if (scanId) await cancelControllerDiscovery(scanId);
    if (stage.value === "scanning") stage.value = "stopped";
  } finally { starting.value = false; }
}
async function stopFromButton() {
  try { await stop(); } catch (e) { error.value = String(e); }
}
async function prepare() {
  if (leaving.value || starting.value || (pendingCheck != null)) return;
  const run = ++generation;
  error.value = "";
  stage.value = "checking";
  try {
    await stop();
    if (disposed || run !== generation) return;
    scanId = "";
    rows.value = [];
    warnings.value = [];
    pendingCheck = checkControllerDiscovery();
    const result = await pendingCheck;
    if (disposed || run !== generation) return;
    check.value = result;
    warnings.value = result.warnings ?? [];
    if (result.status !== "ready") {
      error.value = result.status;
      stage.value = "failed";
      return;
    }
    scanId = crypto.randomUUID();
    stage.value = "scanning";
    starting.value = true;
    pendingStart = startControllerDiscovery(scanId);
    await pendingStart;
  } catch (e) {
    if (!disposed && run === generation) { error.value = String(e); stage.value = "failed"; }
  } finally {
    pendingCheck = undefined;
    pendingStart = undefined;
    starting.value = false;
  }
}
async function leave(ip?: string) {
  if (leaving.value) return;
  leaving.value = true;
  ++generation;
  try {
    if (pendingCheck) {
      await cancelControllerDiscovery("check");
      await pendingCheck.catch(() => {});
    }
    await stop();
    if (ip) emit("select", ip);
    else emit("back");
  } catch (e) { error.value = String(e); }
  finally { leaving.value = false; }
}
async function download() {
  try { await openNpcapDownload(); }
  catch { message.error(t("discovery.downloadFailed")); }
}
const columns = computed<DataTableColumns<DiscoveredController>>(() => [
  { title: t("discovery.ip"), key: "ip", width: 170 },
  { title: t("discovery.mac"), key: "mac", width: 190, render: row => row.mac || t(`discovery.mac${row.macStatus === "missing" ? "Missing" : "Invalid"}`) },
  { title: t("discovery.via"), key: "interfaceIds", render: row => row.interfaceIds.map(adapterName).join(" / ") },
  { title: t("discovery.actions"), key: "actions", width: 160, render: row => h(NButton, { size: "small", type: "primary", disabled: !row.connectable || leaving.value || starting.value, onClick: () => row.connectable && leave(row.ip) }, { default: () => t(row.connectable ? "discovery.use" : "discovery.ipv6Only") }) }
]);
onMounted(async () => {
  try {
    const off = await listen<DiscoveryEvent>("controller-discovery-event", event => onEvent(event.payload));
    if (disposed) { off(); return; }
    unlisten = off;
    await prepare();
  } catch (e) { if (!disposed) { error.value = String(e); stage.value = "failed"; } }
});
onUnmounted(() => {
  disposed = true;
  ++generation;
  unlisten?.();
  void (async () => {
    if (pendingCheck) await cancelControllerDiscovery("check");
    await stop();
  })().catch(e => console.error("Discovery cleanup failed", e));
});
</script>

<template>
  <section class="discovery-page">
    <div class="discovery-heading">
      <h1 class="section-title">{{ t("discovery.title") }}</h1>
      <n-button :loading="leaving" @click="leave()">{{ t("discovery.back") }}</n-button>
    </div>
    <p class="discovery-hint">{{ t("discovery.hint") }}</p>
    <n-alert v-if="error" type="error" :bordered="false">{{ describe(error) }}</n-alert>
    <div v-if="error === 'missing' || error === 'unavailable'" class="discovery-actions">
      <n-button @click="download">{{ t("discovery.download") }}</n-button>
    </div>
    <div class="discovery-toolbar">
      <span>{{ t("discovery.automatic") }}</span>
      <n-button v-if="stage === 'scanning'" :loading="starting" :disabled="leaving" @click="stopFromButton">{{ t("discovery.stop") }}</n-button>
      <n-button v-else type="primary" :loading="stage === 'checking'" :disabled="busy" @click="prepare()">
        {{ check?.status === 'ready' ? t("discovery.search") : t("discovery.recheck") }}
      </n-button>
    </div>
    <div class="discovery-status" role="status" aria-live="polite">
      <n-spin v-if="stage === 'checking' || stage === 'scanning'" :size="18" />
      <span>{{ t(`discovery.${stage}`) }}</span>
      <span>{{ t("discovery.count", { count: rows.length }) }}</span>
    </div>
    <n-alert v-if="warnings.length" type="warning" :title="t('discovery.partial')" :bordered="false">
      <div v-for="(warning, index) in warnings" :key="index">{{ warning.name || adapterName(warning.interfaceId) }} — {{ describe(warning.code) }}</div>
    </n-alert>
    <n-alert v-if="addressConflict" type="warning" :bordered="false">{{ t("discovery.conflict") }}</n-alert>
    <n-alert v-if="incompleteIdentity" type="warning" :bordered="false">{{ t("discovery.incompleteIdentity") }}</n-alert>
    <n-data-table :columns="columns" :data="rows" :row-key="row => row.key" :scroll-x="760" :max-height="380" :bordered="false" />
    <p v-if="stage === 'complete' && !rows.length">{{ t("discovery.empty") }}</p>
    <p class="discovery-hint">{{ t("discovery.connectionHint") }}</p>
  </section>
</template>

<style scoped>
.discovery-page { width: 100%; padding: 24px; border-radius: 16px; background: #fff; color: #263342; box-sizing: border-box; display: grid; gap: 18px; }
.discovery-heading { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.discovery-heading .section-title { color: #172b3a; margin: 0; }
.discovery-hint { margin: 0; line-height: 1.7; color: #536171; }
.discovery-toolbar { display: flex; flex-wrap: wrap; gap: 14px; align-items: center; }
.discovery-status, .discovery-actions { display: flex; align-items: center; gap: 14px; flex-wrap: wrap; }
@media (max-width: 700px) { .discovery-page { padding: 16px; } .discovery-toolbar { grid-template-columns: 1fr; } }
</style>
