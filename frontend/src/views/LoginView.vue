<!-- 登录 / 注册页 -->

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
</script>

<template>
  <div class="login-wrap">
    <el-card class="login-card">
      <h1 style="text-align: center; margin-bottom: 4px">💰 MoneyMate</h1>
      <p style="text-align: center; color: #909399; margin-bottom: 20px">你的私人记账本</p>

      <el-tabs v-model="mode">
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
        <el-button type="primary" style="width: 100%" :loading="loading" @click="submit">
          {{ mode === "login" ? "登录" : "注册并登录" }}
        </el-button>
      </el-form>
    </el-card>
  </div>
</template>

<style scoped>
.login-wrap {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
}
.login-card {
  width: 380px;
  border-radius: 12px;
}
</style>

