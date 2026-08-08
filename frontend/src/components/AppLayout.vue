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
    <el-aside width="212px" style="padding: 14px 0 14px 14px">
      <div class="glass" style="height: calc(100vh - 28px); padding: 18px 6px; display: flex; flex-direction: column">
        <div style="padding: 0 12px 16px; font-size: 19px; font-weight: 700; letter-spacing: -0.01em">
          💰 记账小助手
        </div>
        <el-menu :default-active="route.path" router>
          <el-menu-item index="/dashboard">📊 仪表盘</el-menu-item>
          <el-menu-item index="/transactions">🧾 记账流水</el-menu-item>
          <el-menu-item index="/budget">🎯 预算管理</el-menu-item>
          <el-menu-item index="/categories">🏷️ 分类管理</el-menu-item>
          <el-menu-item index="/report">🗓️ 年度报告</el-menu-item>
        </el-menu>
        <div style="flex: 1"></div>
        <div style="padding: 12px; font-size: 11.5px; color: var(--text-secondary)">
          v1.0 · 个人全栈项目
        </div>
      </div>
    </el-aside>

    <el-container>
      <el-header style="height: 52px; display: flex; align-items: center; justify-content: flex-end; gap: 12px; padding: 0 20px">
        <span style="font-size: 13.5px; color: var(--text-secondary)">👋 {{ auth.user?.username || "加载中…" }}</span>
        <el-button size="small" @click="logout">退出登录</el-button>
      </el-header>
      <el-main style="padding: 0">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>
