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
