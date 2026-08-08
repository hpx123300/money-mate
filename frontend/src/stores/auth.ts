/** 登录状态管理（Pinia） */

import { defineStore } from "pinia";
import { ref } from "vue";
import api from "../api";
import type { User } from "../types";

export const useAuthStore = defineStore("auth", () => {
  const token = ref(localStorage.getItem("token") || "");
  const user = ref<User | null>(null);

  async function login(username: string, password: string) {
    // OAuth2 密码模式：后端要求 application/x-www-form-urlencoded 格式
    const form = new URLSearchParams();
    form.append("username", username);
    form.append("password", password);
    const { data } = await api.post("/auth/login", form, {
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
    });
    token.value = data.access_token;
    localStorage.setItem("token", data.access_token);
    await fetchMe();
  }

  async function register(username: string, email: string, password: string) {
    await api.post("/auth/register", { username, email, password });
  }

  async function fetchMe() {
    const { data } = await api.get<User>("/auth/me");
    user.value = data;
  }

  function logout() {
    token.value = "";
    user.value = null;
    localStorage.removeItem("token");
  }

  return { token, user, login, register, fetchMe, logout };
});

