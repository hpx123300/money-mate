import { defineConfig } from "vitest/config";
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
  test: {
    // api.ts 与登录 store 都依赖 localStorage / window，需要浏览器环境
    environment: "jsdom",
    include: ["src/**/*.test.ts"],
    // jsdom 环境初始化较重，单进程串行跑更稳，也避免 CI 上多 worker 抢资源
    fileParallelism: false,
    maxWorkers: 1,
    testTimeout: 20000,
    hookTimeout: 20000,
  },
});

