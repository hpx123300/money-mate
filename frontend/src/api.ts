/** axios 封装：统一 baseURL、超时、自动带令牌、401 自动跳登录、网络类错误统一提示 */

import axios from "axios";

// 普通接口 20s 足够；AI 接口在调用处单独放宽（见 AI_TIMEOUT）
const DEFAULT_TIMEOUT = 20000;
/** AI 接口要等模型返回，单独放宽，避免用户点一下就被判超时 */
export const AI_TIMEOUT = 90000;

/**
 * 提示函数由 UI 层注入（main.ts 里接 ElMessage）。
 * api 层不直接 import element-plus：测试里跑 jsdom 没必要把整个组件库拉进来。
 */
type ErrorNotifier = (message: string) => void;
let notifyError: ErrorNotifier = () => {};

export function setErrorNotifier(fn: ErrorNotifier) {
  notifyError = fn;
}

const api = axios.create({ baseURL: "/api", timeout: DEFAULT_TIMEOUT });

api.interceptors.request.use((config) => {
  const token = localStorage.getItem("token");
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (res) => res,
  (err) => {
    // 注意这里的判断顺序：清令牌和跳转都只在「不在登录页」时做。
    // 因为登录页上的 401 通常是密码输错，此时若把令牌也清掉，
    // 会把一个本来有效的已登录会话误踢下线。
    if (err.response?.status === 401 && window.location.pathname !== "/login") {
      localStorage.removeItem("token");
      window.location.href = "/login";
      return Promise.reject(err);
    }

    // 只统一提示「没有响应」和 5xx 这两类：业务错误（4xx）带 detail，
    // 交给调用方展示，避免同一个错误弹两次。
    // 打上 __notified 标记，调用方据此跳过重复 toast。
    const status = err.response?.status;
    if (!err.response || (status && status >= 500)) {
      const timeout = err.code === "ECONNABORTED" || err.code === "ETIMEDOUT";
      notifyError(
        timeout
          ? "请求超时了，检查网络后再试一次"
          : !err.response
            ? "网络异常，请检查连接"
            : "服务器开小差了，请稍后重试"
      );
      err.__notified = true;
    }
    return Promise.reject(err);
  }
);

export default api;
