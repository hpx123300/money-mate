<!-- 仪表盘：月度汇总 + 分类占比饼图 + 趋势折线图 -->

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import api from "../api";
import EChart from "../components/EChart.vue";
import type { MonthSummary, TrendPoint } from "../types";

const cur = new Date();
const month = ref(`${cur.getFullYear()}-${String(cur.getMonth() + 1).padStart(2, "0")}`);
const summary = ref<MonthSummary | null>(null);
const trend = ref<TrendPoint[]>([]);

async function load() {
  try {
    const [s, t] = await Promise.all([
      api.get(`/stats/summary?month=${month.value}`),
      api.get("/stats/trend?months=6"),
    ]);
    summary.value = s.data;
    trend.value = t.data.points;
  } catch {
    ElMessage.error("统计数据加载失败");
  }
}

const pieOption = computed(() => ({
  title: { text: "支出分类占比", left: "center" },
  tooltip: { trigger: "item", formatter: "{b}: ¥{c} ({d}%)" },
  series: [
    {
      type: "pie",
      radius: "60%",
      data: (summary.value?.expense_by_category || []).map((c) => ({
        name: c.category_name,
        value: c.total,
      })),
    },
  ],
}));

const lineOption = computed(() => ({
  title: { text: "近 6 个月收支趋势", left: "center" },
  tooltip: { trigger: "axis" },
  legend: { data: ["收入", "支出"], bottom: 0 },
  xAxis: { type: "category", data: trend.value.map((p) => p.month) },
  yAxis: { type: "value" },
  series: [
    { name: "收入", type: "line", smooth: true, data: trend.value.map((p) => p.income), areaStyle: {} },
    { name: "支出", type: "line", smooth: true, data: trend.value.map((p) => p.expense), areaStyle: {} },
  ],
}));

onMounted(load);
</script>

<template>
  <div class="page">
    <div class="toolbar">
      <el-date-picker v-model="month" type="month" value-format="YYYY-MM" @change="load" />
      <span class="spacer" />
      <el-button @click="load">刷新</el-button>
    </div>

    <el-row :gutter="16" style="margin-bottom: 16px">
      <el-col :span="8">
        <el-card><div class="stat-label">本月收入</div><div class="stat-num" style="color: #67c23a">¥ {{ summary?.total_income.toFixed(2) ?? "-" }}</div></el-card>
      </el-col>
      <el-col :span="8">
        <el-card><div class="stat-label">本月支出</div><div class="stat-num" style="color: #f56c6c">¥ {{ summary?.total_expense.toFixed(2) ?? "-" }}</div></el-card>
      </el-col>
      <el-col :span="8">
        <el-card><div class="stat-label">本月结余</div><div class="stat-num">¥ {{ summary?.balance.toFixed(2) ?? "-" }}</div></el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <el-col :span="12">
        <el-card><EChart :option="pieOption" /></el-card>
      </el-col>
      <el-col :span="12">
        <el-card><EChart :option="lineOption" /></el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.stat-label { color: #909399; font-size: 13px; }
.stat-num { font-size: 26px; font-weight: 700; margin-top: 6px; }
</style>

