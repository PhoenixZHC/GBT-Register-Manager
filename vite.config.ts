import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  clearScreen: false,
  resolve: {
    alias: {
      // 使用 vue-i18n 完整 esm-bundler 构建（包含消息模板编译器），
      // 否则像 `{total}`、`{count}` 这种运行时传参插值不会被替换，UI 会显示字面量。
      // CSP 已放行 'unsafe-eval'（script-src），满足编译器的 new Function 需求。
      "vue-i18n": "vue-i18n/dist/vue-i18n.esm-bundler.js"
    },
    // Vite 默认把 .js 排在 .ts 前面：若 src/ 下残留旧的同名 .js（老的 tsc 产物），
    // 会"覆盖"真正的 .ts 源码导致打包结果诡异。显式把 .ts/.tsx 放到最前，保持权威源。
    extensions: [".ts", ".tsx", ".mjs", ".js", ".jsx", ".mts", ".json"]
  },
  // Tauri 前端资源走本地协议，无需远程访问，禁用 host 检查即可。
  server: {
    strictPort: true,
    host: "127.0.0.1",
    port: 5173
  },
  build: {
    // chrome105 = WebView2 ~2022-08，兼容绝大多数 Win10/Win11 系统的 WebView2 版本
    target: "chrome105",
    minify: "esbuild",
    sourcemap: false,
    chunkSizeWarningLimit: 1024,
    rollupOptions: {
      output: {
        // 粗粒度分包，减小主包并让首屏与数据相关代码分离。
        manualChunks: {
          vue: ["vue", "vue-i18n"],
          naive: ["naive-ui"],
          xlsx: ["xlsx"],
          tauri: [
            "@tauri-apps/api",
            "@tauri-apps/api/core",
            "@tauri-apps/api/window"
          ]
        }
      }
    }
  }
});
