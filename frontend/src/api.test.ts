/**
 * axios 实例的两个拦截器。
 *
 * 这里不去真发请求，而是把实例的 adapter 换掉：
 * adapter 是 axios 里真正负责「发出请求」的那一层，
 * 换掉它就能在不联网的情况下拿到完整的请求配置、也能伪造响应。
 */

import { AxiosError, type AxiosResponse, type InternalAxiosRequestConfig } from "axios";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import api from "./api";

function okResponse(config: InternalAxiosRequestConfig, data: unknown = {}): AxiosResponse {
  return { data, status: 200, statusText: "OK", headers: {}, config };
}

function unauthorizedError(config: InternalAxiosRequestConfig): AxiosError {
  const response: AxiosResponse = {
    data: {},
    status: 401,
    statusText: "Unauthorized",
    headers: {},
    config,
  };
  return new AxiosError("Unauthorized", "ERR_BAD_REQUEST", config, null, response);
}

let loc: { pathname: string; href: string };

beforeEach(() => {
  localStorage.clear();
  // jsdom 的 window.location 不可直接赋值，用 stubGlobal 换成普通对象，
  // 这样拦截器里的跳转就变成一次可断言的属性赋值，而不是真的触发导航。
  loc = { pathname: "/dashboard", href: "" };
  vi.stubGlobal("location", loc);
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("请求拦截器", () => {
  it("本地有令牌时自动加上 Authorization 头", async () => {
    localStorage.setItem("token", "tk-123");
    let captured: InternalAxiosRequestConfig | null = null;
    api.defaults.adapter = async (config) => {
      captured = config;
      return okResponse(config);
    };

    await api.get("/auth/me");

    expect(captured).not.toBeNull();
    expect(captured!.headers.Authorization).toBe("Bearer tk-123");
  });

  it("本地没有令牌时不加 Authorization 头", async () => {
    let captured: InternalAxiosRequestConfig | null = null;
    api.defaults.adapter = async (config) => {
      captured = config;
      return okResponse(config);
    };

    await api.get("/transactions");

    expect(captured!.headers.Authorization).toBeUndefined();
  });
});

describe("响应拦截器", () => {
  it("401 且不在登录页：清掉令牌并跳登录页", async () => {
    localStorage.setItem("token", "tk-expired");
    loc.pathname = "/dashboard";
    api.defaults.adapter = async (config) => {
      throw unauthorizedError(config);
    };

    await expect(api.get("/auth/me")).rejects.toThrow();

    expect(localStorage.getItem("token")).toBeNull();
    expect(loc.href).toBe("/login");
  });

  it("401 且已在登录页：不踢会话也不跳转（登录页的 401 是密码错，不是令牌失效）", async () => {
    localStorage.setItem("token", "tk-valid");
    loc.pathname = "/login";
    api.defaults.adapter = async (config) => {
      throw unauthorizedError(config);
    };

    await expect(api.get("/auth/me")).rejects.toThrow();

    expect(localStorage.getItem("token")).toBe("tk-valid");
    expect(loc.href).toBe("");
  });

  it("非 401 的错误原样抛出，且不动本地令牌", async () => {
    localStorage.setItem("token", "tk-123");
    api.defaults.adapter = async (config) => {
      const response: AxiosResponse = {
        data: { detail: "服务器内部错误" },
        status: 500,
        statusText: "Internal Server Error",
        headers: {},
        config,
      };
      throw new AxiosError("boom", "ERR_BAD_RESPONSE", config, null, response);
    };

    await expect(api.get("/transactions")).rejects.toThrow("boom");

    expect(localStorage.getItem("token")).toBe("tk-123");
    expect(loc.href).toBe("");
  });
});
