/**
 * 启动画面控制：在 Vue 挂载前显示加载动画；若超时则展示错误提示。
 * 由 index.html 以 <script type="module"> 引入，不依赖任何框架。
 */

const TIMEOUT_MS = 12_000;

const splash = document.getElementById("gbt-splash");
const errorBox = document.getElementById("gbt-splash-error");
const hintBox = document.getElementById("gbt-splash-hint");

let timer: ReturnType<typeof setTimeout> | null = setTimeout(() => {
  if (!splash || splash.classList.contains("hidden")) return;
  if (errorBox) {
    errorBox.style.display = "block";
    errorBox.textContent =
      "应用加载超时，JavaScript 可能未能正常执行。\n" +
      "请按 F12 打开开发者工具查看错误，或联系技术支持。";
  }
  if (hintBox) {
    hintBox.textContent =
      "日志位置：%APPDATA%\\com.gbt.register.manager\\logs\\gbt-rs.log";
  }
}, TIMEOUT_MS);

/** 由 main.ts 在 Vue 挂载完毕后调用，隐藏启动画面 */
export function hideSplash() {
  if (timer !== null) {
    clearTimeout(timer);
    timer = null;
  }
  if (splash) {
    splash.classList.add("hidden");
    setTimeout(() => {
      splash.style.display = "none";
    }, 350);
  }
}
