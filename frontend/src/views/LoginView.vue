<!-- 登录 / 注册页 · 分屏式产品落地页 -->

<script setup lang="ts">
import { reactive, ref } from "vue";
import { ElMessage } from "element-plus";
import { useRouter } from "vue-router";
import { useAuthStore } from "../stores/auth";

const auth = useAuthStore();
const router = useRouter();

const mode = ref<"login" | "register">("login");
const loading = ref(false);

const form = reactive({
  username: "",
  email: "",
  password: "",
});

async function submit() {
  if (!form.username || !form.password) {
    ElMessage.warning("请填写用户名和密码");
    return;
  }
  loading.value = true;
  try {
    if (mode.value === "login") {
      await auth.login(form.username, form.password);
      ElMessage.success("登录成功");
      router.push("/dashboard");
    } else {
      await auth.register(form.username, form.email, form.password);
      ElMessage.success("注册成功，正在登录…");
      await auth.login(form.username, form.password);
      router.push("/dashboard");
    }
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "操作失败，请检查输入");
  } finally {
    loading.value = false;
  }
}

async function demoLogin() {
  form.username = "demo";
  form.password = "demo123456";
  mode.value = "login";
  loading.value = true;
  try {
    await auth.login(form.username, form.password);
    ElMessage.success("已进入演示账号");
    router.push("/dashboard");
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "演示账号登录失败");
  } finally {
    loading.value = false;
  }
}
</script>

<template>
  <div class="login-wrap">
    <!-- 左侧：品牌展示区 -->
    <aside class="brand-panel">
      <div class="brand-inner">
        <div class="brand-logo">
          <span class="brand-emoji">🎓</span>
          <span class="brand-name gradient-text-on-dark">MoneyMate</span>
        </div>
        <h1 class="brand-title">大学生记账助手</h1>
        <p class="brand-tagline">生活费不超支，钱花在哪一目了然</p>

        <ul class="feature-list">
          <li>
            <span class="feature-icon">✨</span>
            <div>
              <div class="feature-title">AI 智能记账</div>
              <div class="feature-desc">说一句话就能记一笔，自动识别分类与金额</div>
            </div>
          </li>
          <li>
            <span class="feature-icon">📊</span>
            <div>
              <div class="feature-title">可视化图表</div>
              <div class="feature-desc">收支趋势、分类占比，数据一目了然</div>
            </div>
          </li>
          <li>
            <span class="feature-icon">🎯</span>
            <div>
              <div class="feature-title">预算管理</div>
              <div class="feature-desc">设定每月生活费，实时提醒剩余可用</div>
            </div>
          </li>
          <li>
            <span class="feature-icon">🗓️</span>
            <div>
              <div class="feature-title">年度报告</div>
              <div class="feature-desc">一键生成年度账单，回顾消费习惯</div>
            </div>
          </li>
        </ul>

        <div class="brand-footer">
          <span class="brand-dot"></span>
          已服务 1,000+ 大学生的记账需求
        </div>
      </div>
    </aside>

    <!-- 右侧：登录/注册表单 -->
    <main class="form-panel">
      <div class="glass login-card">
        <div class="card-header">
          <h2 class="card-title">{{ mode === "login" ? "欢迎回来 👋" : "创建账号 ✨" }}</h2>
          <p class="card-subtitle">{{ mode === "login" ? "登录开始今天的记账" : "注册即可立即体验" }}</p>
        </div>

        <el-tabs v-model="mode" stretch>
          <el-tab-pane label="登录" name="login" />
          <el-tab-pane label="注册" name="register" />
        </el-tabs>

        <el-form label-position="top" @submit.prevent="submit">
          <el-form-item label="用户名">
            <el-input v-model="form.username" placeholder="3-32 个字符" />
          </el-form-item>
          <el-form-item v-if="mode === 'register'" label="邮箱">
            <el-input v-model="form.email" placeholder="you@example.com" />
          </el-form-item>
          <el-form-item label="密码">
            <el-input v-model="form.password" type="password" show-password placeholder="至少 6 位" @keyup.enter="submit" />
          </el-form-item>
          <el-button type="primary" class="submit-btn" :loading="loading" @click="submit">
            {{ mode === "login" ? "登录" : "注册并登录" }}
          </el-button>
        </el-form>

        <div class="divider">
          <span>或</span>
        </div>

        <el-button class="demo-btn" :loading="loading" @click="demoLogin">
          🎬 体验演示账号
        </el-button>
      </div>
    </main>
  </div>
</template>

<style scoped>
.login-wrap {
  min-height: 100vh;
  display: flex;
}

/* ---------- 左侧品牌面板 ---------- */
.brand-panel {
  flex: 1;
  position: relative;
  overflow: hidden;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 48px;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
  color: #fff;
}

/* 装饰光晕 */
.brand-panel::before {
  content: "";
  position: absolute;
  top: -15%;
  left: -10%;
  width: 480px;
  height: 480px;
  background: radial-gradient(circle, rgba(255, 255, 255, 0.22) 0%, transparent 65%);
  border-radius: 50%;
  pointer-events: none;
}
.brand-panel::after {
  content: "";
  position: absolute;
  bottom: -20%;
  right: -10%;
  width: 520px;
  height: 520px;
  background: radial-gradient(circle, rgba(0, 184, 148, 0.18) 0%, transparent 65%);
  border-radius: 50%;
  pointer-events: none;
}

.brand-inner {
  position: relative;
  z-index: 1;
  max-width: 420px;
  width: 100%;
}

.brand-logo {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 36px;
}
.brand-emoji {
  font-size: 36px;
}
.brand-name {
  font-size: 26px;
  font-weight: 700;
  letter-spacing: -0.02em;
}
.gradient-text-on-dark {
  background: linear-gradient(135deg, #ffffff 0%, #e0e7ff 100%);
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
  color: transparent;
}

.brand-title {
  font-size: 38px;
  font-weight: 800;
  letter-spacing: -0.02em;
  line-height: 1.2;
  margin-bottom: 12px;
}
.brand-tagline {
  font-size: 16px;
  opacity: 0.85;
  line-height: 1.6;
  margin-bottom: 40px;
}

.feature-list {
  list-style: none;
  padding: 0;
  margin: 0 0 40px 0;
}
.feature-list li {
  display: flex;
  align-items: flex-start;
  gap: 14px;
  padding: 12px 0;
}
.feature-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 40px;
  height: 40px;
  background: rgba(255, 255, 255, 0.15);
  backdrop-filter: blur(8px);
  border: 1px solid rgba(255, 255, 255, 0.2);
  border-radius: 12px;
  font-size: 20px;
  flex-shrink: 0;
}
.feature-title {
  font-size: 15px;
  font-weight: 600;
  margin-bottom: 2px;
}
.feature-desc {
  font-size: 13px;
  opacity: 0.78;
  line-height: 1.5;
}

.brand-footer {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  opacity: 0.7;
}
.brand-dot {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #00b894;
  box-shadow: 0 0 8px rgba(0, 184, 148, 0.8);
}

/* ---------- 右侧表单面板 ---------- */
.form-panel {
  flex: 1;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 32px;
}
.login-card {
  width: 100%;
  max-width: 400px;
  padding: 36px 36px 32px;
}

.card-header {
  margin-bottom: 8px;
}
.card-title {
  font-size: 24px;
  font-weight: 700;
  letter-spacing: -0.02em;
  margin-bottom: 6px;
}
.card-subtitle {
  color: var(--text-secondary);
  font-size: 13.5px;
}

.submit-btn {
  width: 100%;
  height: 42px;
  font-size: 14.5px;
  font-weight: 600;
  margin-top: 4px;
}

.divider {
  display: flex;
  align-items: center;
  text-align: center;
  margin: 18px 0;
  color: var(--text-secondary);
  font-size: 12px;
}
.divider::before,
.divider::after {
  content: "";
  flex: 1;
  height: 1px;
  background: rgba(0, 0, 0, 0.08);
}
.divider span {
  padding: 0 12px;
}

.demo-btn {
  width: 100%;
  height: 40px;
  font-size: 14px;
  font-weight: 600;
  background: rgba(102, 126, 234, 0.08);
  border: 1px dashed rgba(102, 126, 234, 0.4);
  color: var(--accent);
}
.demo-btn:hover {
  background: rgba(102, 126, 234, 0.14);
  border-color: var(--accent);
  color: var(--accent);
}

/* ---------- 移动端：隐藏左侧品牌面板 ---------- */
@media (max-width: 768px) {
  .login-wrap {
    flex-direction: column;
  }
  .brand-panel {
    display: none;
  }
  .form-panel {
    padding: 20px;
  }
}
</style>
