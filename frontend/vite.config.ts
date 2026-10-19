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
    chunkSizeWarningLimit: 900,
    rollupOptions: {
      output: {
        // 把不常变的三方库拆成独立 chunk：业务代码更新时这些文件仍可命中缓存
        manualChunks(id) {
          if (!id.includes("node_modules")) return;
          if (id.includes("echarts") || id.includes("zrender")) return "vendor-echarts";
          if (id.includes("element-plus")) return "vendor-element";
          if (id.includes("vue") || id.includes("pinia") || id.includes("axios")) return "vendor-vue";
          return "vendor";
        },
      },
    },
  },
  test: {
    // api.ts 与登录 store 都依赖 localStorage / window，需要浏览器环境
    environment: "jsdom",
    include: ["src/**/*.test.ts"],
    // 复用同一个 jsdom 实例：建三次环境要 50s，比跑用例本身还久
    isolate: false,
    fileParallelism: false,
    maxWorkers: 1,
    testTimeout: 20000,
    hookTimeout: 20000,
  },
});

