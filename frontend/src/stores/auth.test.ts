/**
 * 登录状态 store（Pinia）。
 *
 * 把 api 模块整体 mock 掉：这里要验证的是 store 自己的行为
 * ——令牌怎么存、用户信息怎么取、登出清得干不干净，
 * 而不是 axios 发请求的过程（那部分在 api.test.ts 里）。
 */

import { createPinia, setActivePinia } from "pinia";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { post, get } = vi.hoisted(() => ({ post: vi.fn(), get: vi.fn() }));

vi.mock("../api", () => ({ default: { post, get } }));

import { useAuthStore } from "./auth";

beforeEach(() => {
  localStorage.clear();
  post.mockReset();
  get.mockReset();
  setActivePinia(createPinia());
});

describe("useAuthStore", () => {
  it("初始令牌从 localStorage 读取", () => {
    localStorage.setItem("token", "tk-saved");
    const store = useAuthStore();
    expect(store.token).toBe("tk-saved");
    expect(store.user).toBeNull();
  });

  it("login 用表单格式提交，并把令牌写入 store 与 localStorage", async () => {
    post.mockResolvedValueOnce({ data: { access_token: "tk-new" } });
    get.mockResolvedValueOnce({ data: { id: 1, username: "demo", email: "demo@demo.com" } });

    const store = useAuthStore();
    await store.login("demo", "demo123456");

    expect(post).toHaveBeenCalledTimes(1);
    const [url, body, config] = post.mock.calls[0];
    expect(url).toBe("/auth/login");
    // OAuth2 密码模式要求 application/x-www-form-urlencoded
    expect(body).toBeInstanceOf(URLSearchParams);
    expect((body as URLSearchParams).get("username")).toBe("demo");
    expect((body as URLSearchParams).get("password")).toBe("demo123456");
    expect(config.headers["Content-Type"]).toBe("application/x-www-form-urlencoded");

    expect(store.token).toBe("tk-new");
    expect(localStorage.getItem("token")).toBe("tk-new");
    // 登录成功后自动拉取当前用户
    expect(get).toHaveBeenCalledWith("/auth/me");
    expect(store.user?.username).toBe("demo");
  });

  it("register 只提交注册信息，不写令牌", async () => {
    post.mockResolvedValueOnce({ data: { id: 2 } });

    const store = useAuthStore();
    await store.register("newbie", "new@example.com", "secret123");

    expect(post).toHaveBeenCalledWith("/auth/register", {
      username: "newbie",
      email: "new@example.com",
      password: "secret123",
    });
    expect(store.token).toBe("");
    expect(localStorage.getItem("token")).toBeNull();
  });

  it("logout 同时清掉 store 与 localStorage", async () => {
    post.mockResolvedValueOnce({ data: { access_token: "tk-new" } });
    get.mockResolvedValueOnce({ data: { id: 1, username: "demo", email: "demo@demo.com" } });

    const store = useAuthStore();
    await store.login("demo", "demo123456");
    expect(store.user).not.toBeNull();

    store.logout();

    expect(store.token).toBe("");
    expect(store.user).toBeNull();
    expect(localStorage.getItem("token")).toBeNull();
  });
});
