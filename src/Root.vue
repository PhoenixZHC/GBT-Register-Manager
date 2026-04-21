<script setup lang="ts">
import { computed } from "vue";
import { useI18n } from "vue-i18n";
import { NConfigProvider, NDialogProvider, NMessageProvider } from "naive-ui";
import {
  dateEnUS,
  dateJaJP,
  dateKoKR,
  dateRuRU,
  dateZhCN,
  enUS,
  jaJP,
  koKR,
  ruRU,
  zhCN
} from "naive-ui";
import type { NLocale, NDateLocale } from "naive-ui";
import App from "./App.vue";
import { appleThemeOverrides } from "./naiveTheme";
import type { AppLocale } from "./i18n";

const { locale } = useI18n();

const naiveLocale = computed<NLocale>(() => {
  const l = locale.value as AppLocale;
  if (l === "en") return enUS;
  if (l === "ja") return jaJP;
  if (l === "ko") return koKR;
  if (l === "ru") return ruRU;
  return zhCN;
});

const naiveDateLocale = computed<NDateLocale>(() => {
  const l = locale.value as AppLocale;
  if (l === "en") return dateEnUS;
  if (l === "ja") return dateJaJP;
  if (l === "ko") return dateKoKR;
  if (l === "ru") return dateRuRU;
  return dateZhCN;
});
</script>

<template>
  <n-config-provider :theme-overrides="appleThemeOverrides" :locale="naiveLocale" :date-locale="naiveDateLocale">
    <n-message-provider :duration="5000">
      <n-dialog-provider>
        <App />
      </n-dialog-provider>
    </n-message-provider>
  </n-config-provider>
</template>
