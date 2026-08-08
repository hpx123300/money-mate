<!-- 年度账单报告：像支付宝年度账单那样的数据叙事 -->

<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { ElMessage } from "element-plus";
import type { EChartsOption } from "echarts";
import api from "../api";
import EChart from "../components/EChart.vue";
import { formatMoney } from "../utils";
import type { AnnualReport } from "../types";

const year = ref(String(new Date().getFullYear()));
const report = ref<AnnualReport | null>(null);
const loading = ref(false);

async function load() {
  loading.value = true;
  try {
    const { data } = await api.get(`/stats/annual-report?year=${year.value}`);
    report.value = data;
  } catch {
    ElMessage.error("年度报告加载失败");
  } finally {
    loading.value = false;
  }
}

const monthlyOption = computed<EChartsOption>(() => ({
  title: { text: "每月收支", left: "center" },
  tooltip: { trigger: "axis" },
  legend: { data: ["收入", "支出"], bottom: 0 },
  xAxis: {
    type: "category",
    data: (report.value?.monthly || []).map((m) => m.month.slice(5)),
  },
  yAxis: { type: "value" },
  series: [
    {
      name: "收入",
      type: "bar",
      data: (report.value?.monthly || []).map((m) => m.income),
      itemStyle: { color: "#67c23a" },
    },
    {
      name: "支出",
      type: "bar",
      data: (report.value?.monthly || []).map((m) => m.expense),
      itemStyle: { color: "#f56c6c" },
    },
  ],
}));

const categoryOption = computed<EChartsOption>(() => ({
  title: { text: "支出分类排行", left: "center" },
  tooltip: { trigger: "item", formatter: "{b}: ¥{c} ({d}%)" },
  series: [
    {
      type: "pie",
      radius: "60%",
      data: (report.value?.expense_by_category || []).map((c) => ({
        name: c.category_name,
        value: c.total,
      })),
    },
  ],
}));

onMounted(load);
</script>

<template>
  <div class="page" v-loading="loading">
    <div class="toolbar">
      <h2 style="margin: 0">🗓️ {{ year }} 年度账单</h2>
      <span class="spacer" />
      <el-date-picker v-model="year" type="year" value-format="YYYY" @change="load" />
    </div>

    <el-row :gutter="16" style="margin-bottom: 16px">
      <el-col :xs="24" :sm="12" :md="8">
        <el-card><div class="stat-label">全年收入</div><div class="stat-num" style="color: #67c23a">¥ {{ formatMoney(report?.total_income) }}</div></el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :md="8">
        <el-card><div class="stat-label">全年支出</div><div class="stat-num" style="color: #f56c6c">¥ {{ formatMoney(report?.total_expense) }}</div></el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :md="8">
        <el-card><div class="stat-label">全年结余</div><div class="stat-num">¥ {{ formatMoney(report?.balance) }}</div></el-card>
      </el-col>
    </el-row>

    <el-card v-if="report?.summary" style="margin-bottom: 16px">
      <h3 style="margin-bottom: 6px">📝 年度总结</h3>
      <p style="font-size: 15px">{{ report.summary }}</p>
    </el-card>

    <el-row :gutter="16" style="margin-bottom: 16px">
      <el-col :xs="24" :md="14"><el-card><EChart :option="monthlyOption" /></el-card></el-col>
      <el-col :xs="24" :md="10"><el-card><EChart :option="categoryOption" /></el-card></el-col>
    </el-row>

    <el-row :gutter="16">
      <el-col :xs="24" :md="10">
        <el-card>
          <h3 style="margin-bottom: 10px">💡 年度之最</h3>
          <p style="font-size: 14px">最大单笔：{{ report?.biggest_expense || "暂无支出" }}</p>
          <p style="font-size: 14px">最喜欢在{{ report?.busiest_weekday || "—" }}花钱</p>
        </el-card>
      </el-col>
      <el-col :xs="24" :md="14">
        <el-card>
          <h3 style="margin-bottom: 10px">🎉 年度彩蛋</h3>
          <ul class="list" style="margin: 0">
            <li v-for="(f, i) in report?.fun_facts || []" :key="i">{{ f }}</li>
            <li v-if="!(report?.fun_facts || []).length">记几笔账，明年这里就会有彩蛋 🐣</li>
          </ul>
        </el-card>
      </el-col>
    </el-row>
  </div>
</template>

<style scoped>
.stat-label { color: #909399; font-size: 13px; }
.stat-num { font-size: 26px; font-weight: 700; margin-top: 6px; }
</style>
