<!-- 记账流水：筛选 / 新增 / 编辑 / 删除 / 导出 CSV -->

<script setup lang="ts">
import { onMounted, reactive, ref, watch } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import api from "../api";
import type { Category, ImportResult, Transaction, Wallet } from "../types";

const cur = new Date();
const month = ref(`${cur.getFullYear()}-${String(cur.getMonth() + 1).padStart(2, "0")}`);
const typeFilter = ref("");
const keyword = ref("");
const transactions = ref<Transaction[]>([]);
const categories = ref<Category[]>([]);
const wallets = ref<Wallet[]>([]);
const loading = ref(false);
const page = ref(1);
const pageSize = ref(20);
const total = ref(0);

const dialogVisible = ref(false);
const importVisible = ref(false);
const importFile = ref<File | null>(null);
const importing = ref(false);
const importResult = ref<ImportResult | null>(null);
const editingId = ref<number | null>(null);
const suggesting = ref(false);
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
  const params: Record<string, string | number> = {
    month: month.value,
    page: page.value,
    page_size: pageSize.value,
  };
  if (typeFilter.value) params.type = typeFilter.value;
  if (keyword.value) params.keyword = keyword.value;
  try {
    const { data } = await api.get("/transactions", { params });
    transactions.value = data.items;
    total.value = data.total;
  } finally {
    loading.value = false;
  }
}

function onFilterChange() {
  page.value = 1;
  load();
}

function onSizeChange() {
  page.value = 1;
  load();
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

async function suggestCategory() {
  if (!form.note.trim()) {
    ElMessage.warning("先填个备注，比如「食堂午饭」");
    return;
  }
  suggesting.value = true;
  try {
    const { data } = await api.post("/ai/suggest-category", { note: form.note });
    form.type = data.type;
    form.category_id = data.category_id;
    ElMessage.success(`AI 推荐分类：${data.category}`);
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "AI 推荐失败，请稍后再试");
  } finally {
    suggesting.value = false;
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

function onImportFile(file: any) {
  importFile.value = file.raw;
  importResult.value = null;
}

async function doImport() {
  if (!importFile.value) {
    ElMessage.warning("请先选择 CSV 文件");
    return;
  }
  importing.value = true;
  try {
    const form = new FormData();
    form.append("file", importFile.value);
    const { data } = await api.post("/transactions/import", form);
    importResult.value = data;
    ElMessage.success(`导入完成：新增 ${data.imported} 条，跳过重复 ${data.skipped_duplicates} 条`);
    load();
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "导入失败");
  } finally {
    importing.value = false;
  }
}

async function downloadTemplate() {
  const res = await api.get("/transactions/import-template", { responseType: "blob" });
  const url = URL.createObjectURL(res.data);
  const a = document.createElement("a");
  a.href = url;
  a.download = "moneymate_template.csv";
  a.click();
  URL.revokeObjectURL(url);
}

// 类型切换时清空分类选择
watch(() => form.type, () => { form.category_id = undefined; });
watch(month, onFilterChange);
onMounted(() => { load(); loadCategories(); loadWallets(); });
</script>

<template>
  <div class="page">
    <div class="toolbar">
      <el-date-picker v-model="month" type="month" value-format="YYYY-MM" />
      <el-select v-model="typeFilter" placeholder="全部类型" clearable style="width: 140px" @change="onFilterChange">
        <el-option label="支出" value="expense" />
        <el-option label="收入" value="income" />
      </el-select>
      <el-input
        v-model="keyword"
        placeholder="搜索备注关键词"
        clearable
        style="width: 200px"
        @keyup.enter="onFilterChange"
        @clear="onFilterChange"
      />
      <el-button @click="onFilterChange">搜索</el-button>
      <span class="spacer" />
      <el-button class="btn-import" @click="importVisible = true">
        <span class="btn-icon">📥</span> 导入账单
      </el-button>
      <el-button class="btn-export" @click="exportCsv">
        <span class="btn-icon">📤</span> 导出 CSV
      </el-button>
      <el-button type="primary" @click="openCreate">✏️ 记一笔</el-button>
    </div>

    <el-card>
      <el-table v-loading="loading" :data="transactions" stripe empty-text="本月还没有记账记录，点右上角「记一笔」开始">
        <el-table-column prop="occurred_at" label="日期" width="110" />
        <el-table-column label="类型" width="90">
          <template #default="{ row }">
            <span class="type-badge" :class="row.type === 'income' ? 'type-income' : 'type-expense'">
              {{ row.type === "income" ? "↑ 收入" : "↓ 支出" }}
            </span>
          </template>
        </el-table-column>
        <el-table-column prop="category_name" label="分类" width="120" />
        <el-table-column prop="wallet_name" label="钱包" width="100" />
        <el-table-column label="金额" width="140">
          <template #default="{ row }">
            <span class="amount-cell" :class="row.type === 'income' ? 'amount-income' : 'amount-expense'">
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
      <div style="margin-top: 12px; display: flex; justify-content: flex-end">
        <el-pagination
          v-model:current-page="page"
          v-model:page-size="pageSize"
          :total="total"
          :page-sizes="[10, 20, 50]"
          layout="total, sizes, prev, pager, next"
          @current-change="load"
          @size-change="onSizeChange"
        />
      </div>
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
          <div style="display: flex; gap: 8px; width: 100%">
            <el-input v-model="form.note" placeholder="选填" maxlength="200" />
            <el-button :loading="suggesting" @click="suggestCategory">✨ AI 推荐</el-button>
          </div>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="save">保存</el-button>
      </template>
    </el-dialog>

    <el-dialog v-model="importVisible" title="导入账单" width="460px">
      <div style="font-size: 13px; color: var(--text-secondary); margin-bottom: 12px; line-height: 1.7">
        支持支付宝/微信导出的 CSV（自动识别列名），也可以使用我们的模板。
        重复流水会自动跳过，分类自动匹配。
      </div>
      <div style="margin-bottom: 12px">
        <el-button size="small" @click="downloadTemplate">⬇️ 下载导入模板</el-button>
      </div>
      <el-upload
        drag
        :auto-upload="false"
        :limit="1"
        accept=".csv"
        :on-change="onImportFile"
        style="width: 100%"
      >
        <div style="padding: 20px 0; font-size: 14px">把 CSV 文件拖到这里，或点击选择</div>
      </el-upload>
      <div v-if="importResult" style="margin-top: 12px; font-size: 13px; line-height: 1.8">
        共读取 {{ importResult.total_rows }} 行：
        <span style="color: var(--success)">新增 {{ importResult.imported }}</span> ·
        <span style="color: var(--warn)">跳过重复 {{ importResult.skipped_duplicates }}</span> ·
        <span v-if="importResult.failed" style="color: var(--danger)">失败 {{ importResult.failed }}</span>
        <div v-for="(e, i) in importResult.errors" :key="i" style="color: var(--danger); font-size: 12px">{{ e }}</div>
      </div>
      <template #footer>
        <el-button @click="importVisible = false">关闭</el-button>
        <el-button type="primary" :loading="importing" @click="doImport">开始导入</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<style scoped>
/* ---------- 导入/导出按钮：更突出 ---------- */
.btn-import,
.btn-export {
  font-weight: 600 !important;
  border: 1px solid rgba(102, 126, 234, 0.3) !important;
  background: rgba(102, 126, 234, 0.06) !important;
  color: var(--accent) !important;
}
.btn-import:hover,
.btn-export:hover {
  background: rgba(102, 126, 234, 0.12) !important;
  border-color: var(--accent) !important;
  color: var(--accent) !important;
  transform: translateY(-1px);
}
.btn-icon {
  margin-right: 2px;
}

/* ---------- 类型徽章 ---------- */
.type-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 10px;
  border-radius: 999px;
  font-size: 12px;
  font-weight: 600;
  line-height: 1.6;
}
.type-income {
  background: rgba(0, 184, 148, 0.12);
  color: var(--income-color);
  border: 1px solid rgba(0, 184, 148, 0.25);
}
.type-expense {
  background: rgba(225, 112, 85, 0.12);
  color: var(--expense-color);
  border: 1px solid rgba(225, 112, 85, 0.25);
}

/* ---------- 金额单元格 ---------- */
.amount-cell {
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  font-feature-settings: "tnum" 1;
}
.amount-income {
  color: var(--income-color);
}
.amount-expense {
  color: var(--expense-color);
}

/* ---------- 表格行 hover ---------- */
:deep(.el-table__row) {
  transition: background 0.2s ease;
}
:deep(.el-table__body tr:hover > td.el-table__cell) {
  background: rgba(102, 126, 234, 0.06) !important;
}
:deep(.el-table th.el-table__cell) {
  background: rgba(102, 126, 234, 0.04) !important;
}
</style>
