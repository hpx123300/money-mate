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
      <div class="glass sidebar-shell" style="height: calc(100vh - 28px); padding: 18px 6px; display: flex; flex-direction: column">
        <div class="sidebar-logo">
          <span class="logo-emoji">🎓</span>
          <span class="gradient-text logo-text">大学生记账助手</span>
        </div>
        <el-menu :default-active="route.path" router>
          <el-menu-item index="/dashboard">📊 仪表盘</el-menu-item>
          <el-menu-item index="/transactions">🧾 记账流水</el-menu-item>
          <el-menu-item index="/budget">🎯 预算管理</el-menu-item>
          <el-menu-item index="/categories">🏷️ 分类管理</el-menu-item>
          <el-menu-item index="/report">🗓️ 年度报告</el-menu-item>
        </el-menu>
        <div style="flex: 1"></div>
        <div class="version-badge">
          <span class="version-dot"></span>
          v1.0 · 个人全栈项目
        </div>
      </div>
    </el-aside>

    <el-container>
      <el-header class="app-header">
        <span class="header-user">👋 {{ auth.user?.username || "加载中…" }}</span>
        <el-button size="small" @click="logout">退出登录</el-button>
      </el-header>
      <el-main style="padding: 0">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<style scoped>
.sidebar-shell {
  overflow: hidden;
}

.sidebar-logo {
  padding: 0 12px 16px;
  display: flex;
  align-items: center;
  gap: 8px;
  line-height: 1.3;
}
.logo-emoji {
  font-size: 22px;
  flex-shrink: 0;
}
.logo-text {
  font-size: 17px;
  letter-spacing: -0.01em;
}

.version-badge {
  margin: 0 12px;
  padding: 6px 10px;
  font-size: 11.5px;
  color: var(--text-secondary);
  background: rgba(102, 126, 234, 0.06);
  border: 1px solid rgba(102, 126, 234, 0.15);
  border-radius: 999px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  width: fit-content;
}
.version-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--accent);
  box-shadow: 0 0 6px rgba(102, 126, 234, 0.6);
}

.app-header {
  height: 52px;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 12px;
  padding: 0 20px;
  background: var(--glass-bg);
  backdrop-filter: blur(24px) saturate(180%);
  -webkit-backdrop-filter: blur(24px) saturate(180%);
  border-bottom: 1px solid rgba(102, 126, 234, 0.1);
  box-shadow: 0 1px 0 rgba(102, 126, 234, 0.04);
  position: sticky;
  top: 0;
  z-index: 10;
}
.header-user {
  font-size: 13.5px;
  color: var(--text-secondary);
  font-weight: 500;
}
</style>
