/** 金额格式化：千分位 + 大数缩写，避免超长数字溢出卡片 */
export function formatMoney(value: number | undefined | null): string {
  if (value === undefined || value === null || !isFinite(value)) {
    return "0.00";
  }
  const abs = Math.abs(value);
  if (abs >= 1e8) {
    return `${(value / 1e8).toFixed(2)}亿`;
  }
  if (abs >= 1e4) {
    return `${(value / 1e4).toFixed(2)}万`;
  }
  return value.toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
}

/**
 * 幂等键：同一次「提交意图」必须复用同一个值。
 *
 * 服务端按 client_token 查重，重复提交直接返回已有记录。所以 token 要在
 * 用户点提交之前就定下来（打开表单 / 解析出草稿时生成），而不是在提交瞬间生成——
 * 后者双击一次就是两个不同的 token，仍然会记成两笔。
 */
export function newClientToken(prefix = "tx"): string {
  const rand =
    typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
      ? crypto.randomUUID()
      : `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 10)}`;
  // 服务端 ClientToken 限制 64 字符
  return `${prefix}-${rand}`.slice(0, 64);
}
