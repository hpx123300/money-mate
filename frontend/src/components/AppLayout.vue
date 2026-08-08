<!-- 主框架：左侧菜单 + 顶部用户信息 -->

<script setup lang="ts">
import { onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useAuthStore } from "../stores/auth";

const auth = useAuthStore();
const router = useRouter();
const route = useRoute();

onMounted(() => {
  if (!auth.user) auth.fetchMe().catch(() => {});
});

function logout() {
  auth.logout();
  router.push("/login");
}
</script>

<template>
  <el-container style="min-height: 100vh">
    <el-aside width="200px" style="background: #fff; border-right: 1px solid #e4e7ed">
      <div style="padding: 20px; font-size: 20px; font-weight: 700">💰 MoneyMate</div>
      <el-menu :default-active="route.path" router>
        <el-menu-item index="/dashboard">📊 仪表盘</el-menu-item>
        <el-menu-item index="/transactions">🧾 记账流水</el-menu-item>
        <el-menu-item index="/budget">🎯 预算管理</el-menu-item>
        <el-menu-item index="/categories">🏷️ 分类管理</el-menu-item>
        <el-menu-item index="/report">🗓️ 年度报告</el-menu-item>
      </el-menu>
    </el-aside>

    <el-container>
      <el-header style="background: #fff; border-bottom: 1px solid #e4e7ed; display: flex; align-items: center; justify-content: flex-end; gap: 12px">
        <span>👋 {{ auth.user?.username || "加载中…" }}</span>
        <el-button size="small" @click="logout">退出登录</el-button>
      </el-header>
      <el-main>
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>
