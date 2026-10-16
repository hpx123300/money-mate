/** axios 封装：统一 baseURL、自动带令牌、401 自动跳登录 */

import axios from "axios";

const api = axios.create({ baseURL: "/api" });

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
    }
    return Promise.reject(err);
  }
);

export default api;

