<!-- 仪表盘：月度汇总 + 分类占比饼图 + 趋势折线图 -->

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import type { EChartsOption } from "echarts";
import api from "../api";
import EChart from "../components/EChart.vue";
import { formatMoney } from "../utils";
import type { MonthSummary, TrendPoint, Wallet } from "../types";

const cur = new Date();
const month = ref(`${cur.getFullYear()}-${String(cur.getMonth() + 1).padStart(2, "0")}`);
const summary = ref<MonthSummary | null>(null);
const trend = ref<TrendPoint[]>([]);
const wallets = ref<Wallet[]>([]);
const monthlyText = ref("");

const walletDialog = ref(false);
const walletForm = reactive({ name: "", balance: 0 });

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

async function loadWallets() {
  try {
    const { data } = await api.get("/wallets");
    wallets.value = data;
  } catch {
    ElMessage.error("钱包加载失败");
  }
}

async function loadMonthlySummary() {
  try {
    const { data } = await api.get(`/stats/monthly-summary?month=${month.value}`);
    monthlyText.value = data.text;
  } catch {
    monthlyText.value = "";
  }
}

async function addWallet() {
  if (!walletForm.name.trim()) {
    ElMessage.warning("请填写钱包名称");
    return;
  }
  try {
    await api.post("/wallets", {
      name: walletForm.name.trim(),
      balance: walletForm.balance || 0,
    });
    ElMessage.success("钱包已创建");
    walletDialog.value = false;
    walletForm.name = "";
    walletForm.balance = 0;
    loadWallets();
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "创建失败");
  }
}

const pieOption = computed<EChartsOption>(() => ({
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

const lineOption = computed<EChartsOption>(() => ({
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

onMounted(() => {
  load();
  loadWallets();
  loadMonthlySummary();
});
</script>

<template>
  <div class="page">
    <div class="toolbar">
      <el-date-picker v-model="month" type="month" value-format="YYYY-MM" @change="load" />
      <span class="spacer" />
      <el-button @click="$router.push('/report')">🗓️ 年度报告</el-button>
      <el-button @click="load">刷新</el-button>
    </div>

    <h3 style="margin-bottom: 10px">💰 钱包总览</h3>
    <el-row :gutter="12" style="margin-bottom: 12px">
      <el-col v-for="w in wallets" :key="w.id" :xs="12" :sm="12" :md="6">
        <el-card shadow="hover">
          <div class="stat-label">{{ w.name }}</div>
          <div class="stat-num">¥ {{ formatMoney(w.balance) }}</div>
          <div class="stat-label">{{ w.transaction_count }} 笔流水</div>
        </el-card>
      </el-col>
      <el-col :xs="12" :sm="12" :md="6">
        <el-card shadow="never" style="border-style: dashed; text-align: center; cursor: pointer" @click="walletDialog = true">
          <div style="color: #909399; font-size: 28px; line-height: 1.4">＋</div>
          <div style="color: #909399; font-size: 13px">添加钱包</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="12" style="margin-bottom: 12px">
      <el-col :xs="24" :sm="12" :md="8">
        <el-card><div class="stat-label">本月收入</div><div class="stat-num" style="color: #67c23a">¥ {{ formatMoney(summary?.total_income) }}</div></el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :md="8">
        <el-card><div class="stat-label">本月支出</div><div class="stat-num" style="color: #f56c6c">¥ {{ formatMoney(summary?.total_expense) }}</div></el-card>
      </el-col>
      <el-col :xs="24" :sm="12" :md="8">
        <el-card><div class="stat-label">本月结余</div><div class="stat-num">¥ {{ formatMoney(summary?.balance) }}</div></el-card>
      </el-col>
    </el-row>

    <el-card v-if="monthlyText" style="margin-bottom: 12px">
      <h3 style="margin-bottom: 6px">📝 本月总结</h3>
      <p style="white-space: pre-wrap; font-size: 13.5px; line-height: 1.8">{{ monthlyText }}</p>
    </el-card>

    <el-row :gutter="12">
      <el-col :xs="24" :md="12">
        <el-card><EChart :option="pieOption" /></el-card>
      </el-col>
      <el-col :xs="24" :md="12">
        <el-card><EChart :option="lineOption" /></el-card>
      </el-col>
    </el-row>

    <el-dialog v-model="walletDialog" title="添加钱包" width="360px">
      <el-form label-width="70px">
        <el-form-item label="名称">
          <el-input v-model="walletForm.name" placeholder="如：微信、支付宝、现金" maxlength="20" />
        </el-form-item>
        <el-form-item label="初始余额">
          <el-input-number v-model="walletForm.balance" :min="0" :precision="2" style="width: 100%" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="walletDialog = false">取消</el-button>
        <el-button type="primary" @click="addWallet">创建</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.stat-label { color: #909399; font-size: 13px; }
.stat-num { font-size: 26px; font-weight: 700; margin-top: 6px; }
</style>
