<!-- 仪表盘：月度汇总 + 分类占比饼图 + 趋势折线图 -->

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import type { EChartsOption } from "echarts";
import api from "../api";
import EChart from "../components/EChart.vue";
import { formatMoney } from "../utils";
import type { Allowance, Category, MonthSummary, TrendPoint, Wallet } from "../types";

const cur = new Date();
const month = ref(`${cur.getFullYear()}-${String(cur.getMonth() + 1).padStart(2, "0")}`);
const summary = ref<MonthSummary | null>(null);
const trend = ref<TrendPoint[]>([]);
const wallets = ref<Wallet[]>([]);
const categories = ref<Category[]>([]);
const monthlyText = ref("");
const allowance = ref<Allowance | null>(null);
const aiText = ref("");
const aiParsing = ref(false);
const aiDraftVisible = ref(false);
const aiDraft = reactive({
  type: "expense" as "income" | "expense",
  category_id: undefined as number | undefined,
  wallet_id: undefined as number | undefined,
  amount: undefined as number | undefined,
  occurred_at: "",
  note: "",
});
const aiSummary = ref("");
const aiSummaryLoading = ref(false);

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

async function loadCategories() {
  const { data } = await api.get("/categories");
  categories.value = data;
}

async function loadMonthlySummary() {
  try {
    const { data } = await api.get(`/stats/monthly-summary?month=${month.value}`);
    monthlyText.value = data.text;
  } catch {
    monthlyText.value = "";
  }
}

async function loadAllowance() {
  try {
    const { data } = await api.get("/allowance");
    allowance.value = data;
  } catch {
    allowance.value = null;
  }
}

async function aiParse() {
  const text = aiText.value.trim();
  if (!text) {
    ElMessage.warning("先输入一句话，比如「今天午饭花了 25」");
    return;
  }
  aiParsing.value = true;
  try {
    const { data } = await api.post("/ai/parse-transaction", { text });
    Object.assign(aiDraft, {
      type: data.type,
      category_id: data.category_id,
      wallet_id: data.wallet_id,
      amount: data.amount,
      occurred_at: data.occurred_at,
      note: data.note,
    });
    aiDraftVisible.value = true;
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "AI 解析失败，请稍后再试");
  } finally {
    aiParsing.value = false;
  }
}

async function aiSave() {
  if (!aiDraft.category_id || !aiDraft.amount) {
    ElMessage.warning("请确认分类和金额");
    return;
  }
  try {
    await api.post("/transactions", { ...aiDraft });
    ElMessage.success("AI 记账成功 ✨");
    aiDraftVisible.value = false;
    aiText.value = "";
    load();
    loadWallets();
    loadMonthlySummary();
    loadAllowance();
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "保存失败");
  }
}

async function aiAnalyze() {
  aiSummaryLoading.value = true;
  aiSummary.value = "";
  try {
    const { data } = await api.get(`/ai/monthly-summary?month=${month.value}`);
    aiSummary.value = data.summary;
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "AI 分析失败，请稍后再试");
  } finally {
    aiSummaryLoading.value = false;
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
  loadCategories();
  loadMonthlySummary();
  loadAllowance();
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

    <el-card style="margin-bottom: 12px">
      <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap">
        <span style="font-weight: 600">✨ AI 记账小助手</span>
        <el-input
          v-model="aiText"
          placeholder="说一句话就能记账，比如「今天午饭花了 25」"
          style="max-width: 430px"
          clearable
          @keyup.enter="aiParse"
        />
        <el-button type="primary" :loading="aiParsing" @click="aiParse">AI 记一笔</el-button>
      </div>
    </el-card>

    <el-card v-if="allowance && allowance.amount > 0" style="margin-bottom: 12px">
      <div style="display: flex; align-items: center; flex-wrap: wrap; gap: 20px">
        <div>
          <div class="stat-label">🎓 本月生活费</div>
          <div class="stat-num">¥ {{ formatMoney(allowance.amount) }}</div>
        </div>
        <div>
          <div class="stat-label">已花</div>
          <div class="stat-num" style="color: var(--danger)">¥ {{ formatMoney(allowance.spent) }}</div>
        </div>
        <div>
          <div class="stat-label">剩余</div>
          <div class="stat-num" style="color: var(--success)">¥ {{ formatMoney(allowance.remaining) }}</div>
        </div>
        <div>
          <div class="stat-label">日均可用（剩 {{ allowance.days_left }} 天）</div>
          <div class="stat-num">¥ {{ formatMoney(allowance.daily_budget) }}</div>
        </div>
        <div style="flex: 1"></div>
        <el-button link type="primary" @click="$router.push('/budget')">管理生活费 →</el-button>
      </div>
    </el-card>
    <el-card v-else style="margin-bottom: 12px; border-style: dashed">
      <div style="display: flex; align-items: center; gap: 12px">
        <span>🎓 还没设置每月生活费？设置后帮你算「钱还能撑几天」</span>
        <el-button size="small" type="primary" @click="$router.push('/budget')">去设置</el-button>
      </div>
    </el-card>

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

    <el-card v-if="monthlyText || aiSummary" style="margin-bottom: 12px">
      <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px">
        <h3 style="margin: 0">📝 本月总结</h3>
        <el-button size="small" :loading="aiSummaryLoading" @click="aiAnalyze">✨ AI 深度分析</el-button>
      </div>
      <p v-if="monthlyText" style="white-space: pre-wrap; font-size: 13.5px; line-height: 1.8; margin: 0">{{ monthlyText }}</p>
      <p
        v-if="aiSummary"
        style="white-space: pre-wrap; font-size: 13.5px; line-height: 1.8; margin: 8px 0 0; border-top: 1px dashed var(--border-color); padding-top: 8px"
      >
        {{ aiSummary }}
      </p>
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

    <el-dialog v-model="aiDraftVisible" title="AI 识别结果，确认一下" width="420px">
      <el-form label-width="70px">
        <el-form-item label="类型">
          <el-radio-group v-model="aiDraft.type" @change="aiDraft.category_id = undefined">
            <el-radio-button value="expense">支出</el-radio-button>
            <el-radio-button value="income">收入</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="分类">
          <el-select v-model="aiDraft.category_id" placeholder="选择分类" style="width: 100%">
            <el-option
              v-for="c in categories.filter((c) => c.type === aiDraft.type)"
              :key="c.id"
              :label="c.name"
              :value="c.id"
            />
          </el-select>
        </el-form-item>
        <el-form-item label="钱包">
          <el-select v-model="aiDraft.wallet_id" placeholder="选择钱包" style="width: 100%">
            <el-option v-for="w in wallets" :key="w.id" :label="w.name" :value="w.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="金额">
          <el-input-number v-model="aiDraft.amount" :min="0.01" :precision="2" style="width: 100%" />
        </el-form-item>
        <el-form-item label="日期">
          <el-date-picker v-model="aiDraft.occurred_at" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="aiDraft.note" maxlength="200" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="aiDraftVisible = false">取消</el-button>
        <el-button type="primary" @click="aiSave">确认记账</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
.stat-label { color: #909399; font-size: 13px; }
.stat-num { font-size: 26px; font-weight: 700; margin-top: 6px; }
</style>
