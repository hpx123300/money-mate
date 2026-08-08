<!-- 记账流水：筛选 / 新增 / 编辑 / 删除 / 导出 CSV -->

<script setup lang="ts">
import { onMounted, reactive, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import api from "../api";
import type { Category, Transaction, Wallet } from "../types";

const cur = new Date();
const month = ref(`${cur.getFullYear()}-${String(cur.getMonth() + 1).padStart(2, "0")}`);
const typeFilter = ref("");
const keyword = ref("");
const transactions = ref<Transaction[]>([]);
const categories = ref<Category[]>([]);
const wallets = ref<Wallet[]>([]);
const loading = ref(false);

const dialogVisible = ref(false);
const editingId = ref<number | null>(null);
const form = reactive({
  type: "expense" as "income" | "expense",
  category_id: undefined as number | undefined,
  wallet_id: undefined as number | undefined,
  amount: undefined as number | undefined,
  occurred_at: `${cur.getFullYear()}-${String(cur.getMonth() + 1).padStart(2, "0")}-01`,
  note: "",
});

async function load() {
  loading.value = true;
  const params: Record<string, string> = { month: month.value };
  if (typeFilter.value) params.type = typeFilter.value;
  if (keyword.value) params.keyword = keyword.value;
  try {
    const { data } = await api.get("/transactions", { params });
    transactions.value = data;
  } finally {
    loading.value = false;
  }
}

async function loadCategories() {
  const { data } = await api.get("/categories");
  categories.value = data;
}

async function loadWallets() {
  const { data } = await api.get("/wallets");
  wallets.value = data;
  if (!form.wallet_id && wallets.value.length) {
    form.wallet_id = wallets.value[0].id;
  }
}

const typeCategories = () => categories.value.filter((c) => c.type === form.type);

function openCreate() {
  editingId.value = null;
  Object.assign(form, {
    type: "expense",
    category_id: undefined,
    wallet_id: wallets.value[0]?.id,
    amount: undefined,
    note: "",
    occurred_at: `${month.value}-01`,
  });
  dialogVisible.value = true;
}

function openEdit(row: Transaction) {
  editingId.value = row.id;
  Object.assign(form, {
    type: row.type,
    category_id: row.category_id,
    wallet_id: row.wallet_id ?? wallets.value[0]?.id,
    amount: row.amount,
    occurred_at: row.occurred_at,
    note: row.note,
  });
  dialogVisible.value = true;
}

async function save() {
  if (!form.category_id || !form.amount) {
    ElMessage.warning("请选择分类并填写金额");
    return;
  }
  const body = { ...form };
  if (editingId.value) {
    await api.put(`/transactions/${editingId.value}`, body);
  } else {
    await api.post("/transactions", body);
  }
  ElMessage.success("保存成功");
  dialogVisible.value = false;
  load();
}

async function remove(row: Transaction) {
  await ElMessageBox.confirm("确定删除这笔记录吗？", "提示", { type: "warning" });
  await api.delete(`/transactions/${row.id}`);
  ElMessage.success("已删除");
  load();
}

async function exportCsv() {
  const res = await api.get("/transactions/export", { params: { month: month.value }, responseType: "blob" });
  const url = URL.createObjectURL(res.data);
  const a = document.createElement("a");
  a.href = url;
  a.download = `moneymate_${month.value}.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

// 类型切换时清空分类选择
watch(() => form.type, () => { form.category_id = undefined; });
watch(month, load);
onMounted(() => { load(); loadCategories(); loadWallets(); });
</script>

<template>
  <div class="page">
    <div class="toolbar">
      <el-date-picker v-model="month" type="month" value-format="YYYY-MM" />
      <el-select v-model="typeFilter" placeholder="全部类型" clearable style="width: 140px" @change="load">
        <el-option label="支出" value="expense" />
        <el-option label="收入" value="income" />
      </el-select>
      <el-input
        v-model="keyword"
        placeholder="搜索备注关键词"
        clearable
        style="width: 200px"
        @keyup.enter="load"
        @clear="load"
      />
      <el-button @click="load">搜索</el-button>
      <span class="spacer" />
      <el-button @click="exportCsv">导出 CSV</el-button>
      <el-button type="primary" @click="openCreate">记一笔</el-button>
    </div>

    <el-card>
      <el-table v-loading="loading" :data="transactions" stripe empty-text="本月还没有记账记录，点右上角「记一笔」开始">
        <el-table-column prop="occurred_at" label="日期" width="110" />
        <el-table-column label="类型" width="80">
          <template #default="{ row }">
            <el-tag :type="row.type === 'income' ? 'success' : 'danger'" size="small">
              {{ row.type === "income" ? "收入" : "支出" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="category_name" label="分类" width="120" />
        <el-table-column prop="wallet_name" label="钱包" width="100" />
        <el-table-column label="金额" width="140">
          <template #default="{ row }">
            <span :style="{ color: row.type === 'income' ? '#67c23a' : '#f56c6c', fontWeight: 600 }">
              {{ row.type === "income" ? "+" : "-" }}¥{{ row.amount.toFixed(2) }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="note" label="备注" />
        <el-table-column label="操作" width="140">
          <template #default="{ row }">
            <el-button size="small" @click="openEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑流水' : '记一笔'" width="420px">
      <el-form label-width="70px">
        <el-form-item label="类型">
          <el-radio-group v-model="form.type">
            <el-radio-button value="expense">支出</el-radio-button>
            <el-radio-button value="income">收入</el-radio-button>
          </el-radio-group>
        </el-form-item>
        <el-form-item label="分类">
          <el-select v-model="form.category_id" placeholder="选择分类" style="width: 100%">
            <el-option v-for="c in typeCategories()" :key="c.id" :label="c.name" :value="c.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="钱包">
          <el-select v-model="form.wallet_id" placeholder="选择钱包" style="width: 100%">
            <el-option v-for="w in wallets" :key="w.id" :label="w.name" :value="w.id" />
          </el-select>
        </el-form-item>
        <el-form-item label="金额">
          <el-input-number v-model="form.amount" :min="0.01" :precision="2" :step="10" style="width: 100%" />
        </el-form-item>
        <el-form-item label="日期">
          <el-date-picker v-model="form.occurred_at" type="date" value-format="YYYY-MM-DD" style="width: 100%" />
        </el-form-item>
        <el-form-item label="备注">
          <el-input v-model="form.note" placeholder="选填" maxlength="200" />
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>
