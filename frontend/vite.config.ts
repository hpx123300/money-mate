import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";

export default defineConfig({
  plugins: [vue()],
  server: {
    port: 5173,
    // 开发时把 /api 请求转发到后端，前端不用关心跨域
    proxy: {
      "/api": "http://127.0.0.1:8000",
    },
  },
  build: {
    chunkSizeWarningLimit: 1500, // Element Plus + ECharts 体积较大，调高提示阈值
  },
});

