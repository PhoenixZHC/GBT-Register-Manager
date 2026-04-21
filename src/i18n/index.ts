import { createI18n } from "vue-i18n";
import en from "../locales/en";
import ja from "../locales/ja";
import ko from "../locales/ko";
import ru from "../locales/ru";
import zh from "../locales/zh";

export const LOCALE_STORAGE_KEY = "gbt_locale";

export const SUPPORTED_LOCALES = ["zh", "en", "ja", "ko", "ru"] as const;
export type AppLocale = (typeof SUPPORTED_LOCALES)[number];

function detectLocale(): AppLocale {
  try {
    const saved = localStorage.getItem(LOCALE_STORAGE_KEY);
    if (saved && SUPPORTED_LOCALES.includes(saved as AppLocale)) return saved as AppLocale;
  } catch {
    /* private mode */
  }
  const nav = typeof navigator !== "undefined" ? navigator.language.toLowerCase() : "";
  if (nav.startsWith("zh")) return "zh";
  if (nav.startsWith("ja")) return "ja";
  if (nav.startsWith("ko")) return "ko";
  if (nav.startsWith("ru")) return "ru";
  if (nav.startsWith("en")) return "en";
  return "zh";
}

const i18n = createI18n({
  legacy: false,
  locale: detectLocale(),
  fallbackLocale: "zh",
  messages: { zh, en, ja, ko, ru }
});

export function setStoredLocale(locale: AppLocale) {
  try {
    localStorage.setItem(LOCALE_STORAGE_KEY, locale);
  } catch {
    /* ignore */
  }
}

export default i18n;
