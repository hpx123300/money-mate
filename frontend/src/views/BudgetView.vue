<!-- 预算管理：设置月度预算 + 进度展示 -->

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import api from "../api";
import type { Allowance, Budget } from "../types";

const cur = new Date();
const month = ref(`${cur.getFullYear()}-${String(cur.getMonth() + 1).padStart(2, "0")}`);
const budget = ref<Budget | null>(null);
const form = reactive({ amount: 0 });
const allowance = ref<Allowance | null>(null);
const allowanceForm = reactive({ amount: 1000, day_of_month: 1 });

async function load() {
  const [b, a] = await Promise.all([
    api.get(`/budget/${month.value}`),
    api.get("/allowance"),
  ]);
  budget.value = b.data;
  form.amount = b.data.amount;
  allowance.value = a.data;
  if (a.data.amount > 0) {
    allowanceForm.amount = a.data.amount;
    allowanceForm.day_of_month = a.data.day_of_month;
  }
}

async function save() {
  if (!form.amount || form.amount <= 0) {
    ElMessage.warning("预算金额必须大于 0");
    return;
  }
  await api.put(`/budget/${month.value}`, { month: month.value, amount: form.amount });
  ElMessage.success("预算已保存");
  load();
}

async function saveAllowance() {
  if (!allowanceForm.amount || allowanceForm.amount <= 0) {
    ElMessage.warning("生活费金额必须大于 0");
    return;
  }
  await api.put("/allowance", {
    amount: allowanceForm.amount,
    day_of_month: allowanceForm.day_of_month,
  });
  ElMessage.success("生活费设置已保存");
  load();
}

const percent = () => {
  if (!budget.value || budget.value.amount <= 0) return 0;
  return Math.min(100, Math.round((budget.value.spent / budget.value.amount) * 100));
};

const overBudget = () => budget.value && budget.value.amount > 0 && budget.value.spent > budget.value.amount;

onMounted(load);
</script>

<template>
  <div class="page">
    <div class="toolbar">
      <el-date-picker v-model="month" type="month" value-format="YYYY-MM" @change="load" />
      <span class="spacer" />
    </div>

    <el-row :gutter="16">
      <el-col :span="12">
        <el-card>
          <h3>本月预算</h3>
          <el-input-number v-model="form.amount" :min="0" :precision="2" :step="100" style="width: 100%; margin: 12px 0" />
          <el-button type="primary" style="width: 100%" @click="save">保存预算</el-button>
        </el-card>
      </el-col>
      <el-col :span="12">
        <el-card>
          <h3>支出进度</h3>
          <div style="font-size: 15px; margin: 12px 0">
            已支出 <b style="color: #f56c6c">¥{{ budget?.spent.toFixed(2) ?? "0.00" }}</b>
            / 预算 ¥{{ budget?.amount.toFixed(2) ?? "0.00" }}
          </div>
          <el-progress :percentage="percent()" :color="overBudget() ? '#f56c6c' : '#67c23a'" :stroke-width="18" />
          <el-alert
            v-if="overBudget()"
            type="error"
            style="margin-top: 12px"
            :closable="false"
            :title="`已超支 ¥${((budget?.spent ?? 0) - (budget?.amount ?? 0)).toFixed(2)}，注意控制消费！`"
          />
          <el-alert v-else type="success" style="margin-top: 12px" :closable="false" title="预算内，继续加油 💪" />
        </el-card>
      </el-col>
    </el-row>

    <el-card style="margin-top: 16px">
      <h3 style="margin-bottom: 12px">🎓 生活费规划</h3>
      <el-row :gutter="24" align="middle">
        <el-col :xs="24" :md="8">
          <el-form label-width="90px">
            <el-form-item label="每月生活费">
              <el-input-number v-model="allowanceForm.amount" :min="0" :precision="2" :step="100" style="width: 100%" />
            </el-form-item>
            <el-form-item label="每月到账日">
              <el-input-number v-model="allowanceForm.day_of_month" :min="1" :max="28" style="width: 100%" />
            </el-form-item>
            <el-button type="primary" @click="saveAllowance">保存生活费设置</el-button>
          </el-form>
        </el-col>
        <el-col :xs="24" :md="16">
          <template v-if="allowance && allowance.amount > 0">
            <el-row :gutter="12">
              <el-col :xs="12" :md="6">
                <div class="stat-label">本月生活费</div>
                <div class="stat-num">¥ {{ allowance.amount.toFixed(2) }}</div>
              </el-col>
              <el-col :xs="12" :md="6">
                <div class="stat-label">已花</div>
                <div class="stat-num" style="color: var(--danger)">¥ {{ allowance.spent.toFixed(2) }}</div>
              </el-col>
              <el-col :xs="12" :md="6">
                <div class="stat-label">剩余</div>
                <div class="stat-num" style="color: var(--success)">¥ {{ allowance.remaining.toFixed(2) }}</div>
              </el-col>
              <el-col :xs="12" :md="6">
                <div class="stat-label">日均可用（剩 {{ allowance.days_left }} 天）</div>
                <div class="stat-num">¥ {{ allowance.daily_budget.toFixed(2) }}</div>
              </el-col>
            </el-row>
            <el-alert
              :type="allowance.remaining < 0 ? 'error' : 'success'"
              :closable="false"
              style="margin-top: 12px"
              :title="allowance.remaining < 0
                ? `生活费已超支 ¥${Math.abs(allowance.remaining).toFixed(2)}，距离下月到账还有 ${allowance.days_left} 天 😱`
                : `距离下月生活费到账还有 ${allowance.days_left} 天，每天最多可花 ¥${allowance.daily_budget.toFixed(2)}`"
            />
          </template>
          <el-alert v-else type="info" :closable="false" title="还没有设置生活费，设置后这里会自动帮你算「还能撑几天」" />
        </el-col>
      </el-row>
    </el-card>
  </div>
</template>
