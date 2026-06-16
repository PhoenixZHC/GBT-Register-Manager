import { createApp } from "vue";
import { createDiscreteApi } from "naive-ui";
import { invoke } from "@tauri-apps/api/core";
import Root from "./Root.vue";
import i18n from "./i18n";
import "./styles.css";
import { hideSplash } from "./splash";

const app = createApp(Root);
app.use(i18n);
app.mount("#app");
hideSplash();

// Register devtools shortcut in both dev and packaged builds.
window.addEventListener("keydown", (e) => {
  if (e.key === "F12" || (e.ctrlKey && e.shiftKey && e.key === "I")) {
    e.preventDefault();
    invoke("open_devtools").catch(() => {});
  }
});

const { message } = createDiscreteApi(["message"], {
  messageProviderProps: { duration: 5000 }
});

const LOG = "[GBT-UI]";

function reportRuntimeError(scope: string, payload: unknown) {
  console.error(`${LOG} ${scope}`, payload);
  try {
    message.error(String(i18n.global.t("errors.appRuntime")));
  } catch {
    message.error("Application runtime error. Check the log.");
  }
}

window.addEventListener("error", (ev) => {
  reportRuntimeError("window.error", {
    message: ev.message,
    filename: ev.filename,
    lineno: ev.lineno,
    colno: ev.colno,
    error: ev.error
  });
});

window.addEventListener("unhandledrejection", (ev) => {
  reportRuntimeError("unhandledrejection", ev.reason);
  ev.preventDefault();
});

app.config.errorHandler = (err, _instance, info) => {
  reportRuntimeError(`vue:${info}`, err);
};
