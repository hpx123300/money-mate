<!-- 分类管理：查看 / 新增 / 编辑 / 删除 收支分类 -->

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from "vue";
import { ElMessage, ElMessageBox } from "element-plus";
import api from "../api";
import type { Category } from "../types";

const categories = ref<Category[]>([]);
const loading = ref(false);
const activeType = ref<"expense" | "income">("expense");

const dialogVisible = ref(false);
const editingId = ref<number | null>(null);
const form = reactive({
  name: "",
  type: "expense" as "expense" | "income",
});

const filtered = computed(() =>
  categories.value.filter((c) => c.type === activeType.value)
);

async function load() {
  loading.value = true;
  try {
    const { data } = await api.get("/categories");
    categories.value = data;
  } finally {
    loading.value = false;
  }
}

function openCreate() {
  editingId.value = null;
  Object.assign(form, { name: "", type: activeType.value });
  dialogVisible.value = true;
}

function openEdit(category: Category) {
  editingId.value = category.id;
  Object.assign(form, { name: category.name, type: category.type });
  dialogVisible.value = true;
}

async function save() {
  if (!form.name.trim()) {
    ElMessage.warning("请输入分类名称");
    return;
  }
  const body = { name: form.name.trim(), type: form.type };
  try {
    if (editingId.value) {
      await api.put(`/categories/${editingId.value}`, body);
      ElMessage.success("分类已更新");
    } else {
      await api.post("/categories", body);
      ElMessage.success("分类已创建");
    }
    dialogVisible.value = false;
    load();
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "操作失败");
  }
}

async function remove(category: Category) {
  await ElMessageBox.confirm(
    `确定删除分类「${category.name}」吗？分类下有流水时无法删除。`,
    "提示",
    { type: "warning" }
  );
  try {
    await api.delete(`/categories/${category.id}`);
    ElMessage.success("已删除");
    load();
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "删除失败");
  }
}

onMounted(load);
</script>

<template>
  <div class="page">
    <div class="toolbar">
      <el-radio-group v-model="activeType">
        <el-radio-button value="expense">支出分类</el-radio-button>
        <el-radio-button value="income">收入分类</el-radio-button>
      </el-radio-group>
      <span class="spacer" />
      <el-button type="primary" @click="openCreate">新增分类</el-button>
    </div>

    <el-card>
      <el-table v-loading="loading" :data="filtered" stripe empty-text="还没有分类，点右上角新增">
        <el-table-column prop="name" label="分类名称" />
        <el-table-column label="类型">
          <template #default="{ row }">
            <el-tag :type="row.type === 'income' ? 'success' : 'danger'" size="small">
              {{ row.type === "income" ? "收入" : "支出" }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="160">
          <template #default="{ row }">
            <el-button size="small" @click="openEdit(row)">编辑</el-button>
            <el-button size="small" type="danger" @click="remove(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>
    </el-card>

    <el-dialog v-model="dialogVisible" :title="editingId ? '编辑分类' : '新增分类'" width="360px">
      <el-form label-width="70px">
        <el-form-item label="名称">
          <el-input v-model="form.name" placeholder="如：宠物、房租" maxlength="20" />
        </el-form-item>
        <el-form-item label="类型">
          <el-radio-group v-model="form.type">
            <el-radio-button value="expense">支出</el-radio-button>
            <el-radio-button value="income">收入</el-radio-button>
          </el-radio-group>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" @click="save">保存</el-button>
      </template>
    </el-dialog>
  </div>
</template>
