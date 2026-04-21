import { createApp } from "vue";
import { createDiscreteApi } from "naive-ui";
import Root from "./Root.vue";
import i18n from "./i18n";
import "./styles.css";

const app = createApp(Root);
app.use(i18n);
app.mount("#app");

const { message } = createDiscreteApi(["message"], {
  messageProviderProps: { duration: 5000 }
});
window.addEventListener("error", () => {
  message.error(String(i18n.global.t("errors.appRuntime")));
});
