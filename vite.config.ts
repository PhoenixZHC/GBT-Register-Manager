import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

// https://vitejs.dev/config/
export default defineConfig({
  plugins: [vue()],
  clearScreen: false,
  resolve: {
    alias: {
      // 使用 vue-i18n 的纯运行时构建，不包含消息模板编译器（无需 eval/new Function）。
      // 项目消息只用 {param} 简单插值，运行时即可处理，无需切换回 full 构建。
      "vue-i18n": "vue-i18n/dist/vue-i18n.runtime.esm-bundler.js"
    }
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
