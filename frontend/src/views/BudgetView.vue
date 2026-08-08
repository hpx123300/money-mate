<!-- 预算管理：设置月度预算 + 进度展示 -->

<script setup lang="ts">
import { onMounted, reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import api from "../api";
import type { Budget } from "../types";

const cur = new Date();
const month = ref(`${cur.getFullYear()}-${String(cur.getMonth() + 1).padStart(2, "0")}`);
const budget = ref<Budget | null>(null);
const form = reactive({ amount: 0 });

async function load() {
  const { data } = await api.get(`/budget/${month.value}`);
  budget.value = data;
  form.amount = data.amount;
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
  </div>
</template>
