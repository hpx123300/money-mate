/** 金额格式化：卡片上的数字展示规则 */

import { describe, expect, it } from "vitest";

import { formatMoney, newClientToken } from "./utils";

describe("formatMoney", () => {
  it("普通金额用千分位并保留两位小数", () => {
    expect(formatMoney(0)).toBe("0.00");
    expect(formatMoney(25)).toBe("25.00");
    expect(formatMoney(1234.5)).toBe("1,234.50");
  });

  it("超过一万改用「万」缩写", () => {
    expect(formatMoney(10000)).toBe("1.00万");
    expect(formatMoney(12345)).toBe("1.23万");
  });

  it("超过一亿改用「亿」缩写", () => {
    expect(formatMoney(123456789)).toBe("1.23亿");
  });

  it("负数保留符号后再缩写", () => {
    expect(formatMoney(-12345)).toBe("-1.23万");
  });

  it("空值与非法值一律回退为 0.00", () => {
    expect(formatMoney(null)).toBe("0.00");
    expect(formatMoney(undefined)).toBe("0.00");
    expect(formatMoney(NaN)).toBe("0.00");
    expect(formatMoney(Infinity)).toBe("0.00");
  });
});

describe("newClientToken", () => {
  it("带前缀，且不超过服务端 64 字符上限", () => {
    const token = newClientToken("ai");
    expect(token.startsWith("ai-")).toBe(true);
    expect(token.length).toBeLessThanOrEqual(64);
    expect(token.length).toBeGreaterThan(8);
  });

  it("每次调用都不同（否则两次正常记账会被判成重复）", () => {
    const set = new Set(Array.from({ length: 50 }, () => newClientToken()));
    expect(set.size).toBe(50);
  });
});
