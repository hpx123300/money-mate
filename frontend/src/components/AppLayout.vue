<!-- 主框架：桌面端左侧菜单 + 顶部用户信息；移动端底部 tab 栏 -->

<script setup lang="ts">
import { onMounted } from "vue";
import { useRoute, useRouter } from "vue-router";
import { useAuthStore } from "../stores/auth";
import AiChatPanel from "./AiChatPanel.vue";

const auth = useAuthStore();
const router = useRouter();
const route = useRoute();

// 移动端底部导航：侧边栏在 768px 以下隐藏，否则内容区会被挤到只剩两百多像素
const TABS = [
  { path: "/dashboard", icon: "📊", label: "概览" },
  { path: "/transactions", icon: "🧾", label: "流水" },
  { path: "/budget", icon: "🎯", label: "预算" },
  { path: "/report", icon: "🗓️", label: "报告" },
];

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
    <el-aside width="212px" class="app-aside">
      <div class="glass sidebar-shell" style="height: calc(100vh - 28px); padding: 18px 6px; display: flex; flex-direction: column">
        <div class="sidebar-logo">
          <span class="logo-emoji">🎓</span>
          <span class="gradient-text logo-text">有数</span>
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
      <el-main class="app-main">
        <router-view />
      </el-main>
    </el-container>

    <!-- 移动端底部导航 -->
    <nav class="mobile-tabs">
      <router-link
        v-for="tab in TABS"
        :key="tab.path"
        :to="tab.path"
        :class="['mobile-tab', route.path === tab.path ? 'active' : '']"
      >
        <span class="mobile-tab-icon">{{ tab.icon }}</span>
        <span>{{ tab.label }}</span>
      </router-link>
    </nav>

    <AiChatPanel />
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

.mobile-tabs {
  display: none;
}

@media (max-width: 768px) {
  .app-aside {
    display: none;
  }
  .app-main {
    padding-bottom: 72px;
  }
  .mobile-tabs {
    position: fixed;
    left: 0;
    right: 0;
    bottom: 0;
    z-index: 20;
    display: flex;
    justify-content: space-around;
    padding: 8px 6px calc(8px + env(safe-area-inset-bottom));
    background: rgba(255, 255, 255, 0.92);
    backdrop-filter: blur(18px);
    border-top: 1px solid rgba(102, 126, 234, 0.14);
  }
  .mobile-tab {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 2px;
    font-size: 11.5px;
    color: var(--text-secondary);
    text-decoration: none;
    padding: 4px 12px;
    border-radius: 10px;
  }
  .mobile-tab.active {
    color: var(--accent);
    background: rgba(102, 126, 234, 0.08);
  }
  .mobile-tab-icon {
    font-size: 16px;
  }
}
</style>
