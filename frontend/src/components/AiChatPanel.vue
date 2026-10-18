<!--
  AI 对话入口：右下角悬浮球 + 抽屉。

  设计上的两个决定：
  1. 写操作只出草稿，卡片上必须点「确认」才真正入库——AI 判断错了，
     用户改一下的成本远低于记错一笔再回头找。
  2. 确认成功后广播 youshu:refresh 事件，各页面自己决定要不要重新拉数据，
     避免为了一个悬浮组件把全局状态改造成一套事件总线。
-->

<script setup lang="ts">
import { nextTick, ref } from "vue";
import { ElMessage } from "element-plus";
import api from "../api";

interface Draft {
  category_id: number;
  category: string;
  wallet_id: number | null;
  wallet: string | null;
  amount: number;
  type: "expense" | "income";
  note: string;
  occurred_at: string;
}

interface Action {
  kind: "transaction" | "budget";
  draft: Draft | { month: string; amount: number; previous: number | null };
}

interface ChatMsg {
  role: "user" | "assistant";
  content: string;
  actions?: Action[];
}

const open = ref(false);
const input = ref("");
const busy = ref(false);
const messages = ref<ChatMsg[]>([]);
const listRef = ref<HTMLElement | null>(null);

const QUICK = ["午饭花了 25", "这个月餐饮花了多少", "我还剩多少钱"];

async function scrollToBottom() {
  await nextTick();
  listRef.value?.scrollTo({ top: listRef.value.scrollHeight, behavior: "smooth" });
}

async function send(text?: string) {
  const content = (text ?? input.value).trim();
  if (!content || busy.value) return;
  input.value = "";
  messages.value.push({ role: "user", content });
  busy.value = true;
  await scrollToBottom();
  try {
    const { data } = await api.post("/chat", { message: content });
    messages.value.push({
      role: "assistant",
      content: data.reply || "…",
      actions: data.actions || [],
    });
  } catch (e: any) {
    const detail = e.response?.data?.detail || "AI 暂时不可用，稍后再试";
    messages.value.push({ role: "assistant", content: String(detail) });
  } finally {
    busy.value = false;
    await scrollToBottom();
  }
}

async function confirmAction(action: Action) {
  try {
    if (action.kind === "transaction") {
      const d = action.draft as Draft;
      await api.post("/transactions", {
        category_id: d.category_id,
        wallet_id: d.wallet_id,
        amount: d.amount,
        type: d.type,
        note: d.note,
        occurred_at: d.occurred_at,
        client_token: `ai-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      });
      ElMessage.success("已记账");
    } else {
      const d = action.draft as { month: string; amount: number };
      await api.put(`/budget/${d.month}`, { month: d.month, amount: d.amount });
      ElMessage.success("预算已更新");
    }
    // 通知页面刷新：悬浮组件不该直接操作各页面的状态
    window.dispatchEvent(new CustomEvent("youshu:refresh"));
    messages.value.push({ role: "assistant", content: "好了，已经生效。" });
  } catch (e: any) {
    ElMessage.error(e.response?.data?.detail || "操作失败");
  }
}
</script>

<template>
  <div class="ai-fab" @click="open = true">
    <span class="ai-fab-icon">✦</span>
    <span class="ai-fab-text">问 AI</span>
  </div>

  <el-drawer v-model="open" direction="rtl" size="420px" :with-header="false" class="ai-drawer">
    <div class="ai-panel">
      <header class="ai-head">
        <div>
          <div class="ai-title">AI 花钱助手</div>
          <div class="ai-sub">记账、查花销、改预算，一句话就行</div>
        </div>
        <el-button text @click="open = false">关闭</el-button>
      </header>

      <div ref="listRef" class="ai-list">
        <div v-if="!messages.length" class="ai-empty">
          <div class="ai-empty-title">试试这样说</div>
          <div class="ai-quick">
            <button v-for="q in QUICK" :key="q" class="ai-chip" @click="send(q)">{{ q }}</button>
          </div>
        </div>

        <div v-for="(m, i) in messages" :key="i" :class="['ai-row', m.role]">
          <div class="ai-bubble">{{ m.content }}</div>

          <div v-for="(a, j) in m.actions || []" :key="j" class="ai-action">
            <template v-if="a.kind === 'transaction'">
              <div class="ai-action-title">待确认的记账</div>
              <div class="ai-action-line">
                {{ (a.draft as Draft).category }} ·
                {{ (a.draft as Draft).type === "expense" ? "支出" : "收入" }} ·
                ¥{{ (a.draft as Draft).amount }}
              </div>
              <div class="ai-action-line muted">
                {{ (a.draft as Draft).occurred_at }} · {{ (a.draft as Draft).wallet || "默认钱包" }} ·
                {{ (a.draft as Draft).note }}
              </div>
            </template>
            <template v-else>
              <div class="ai-action-title">待确认的预算</div>
              <div class="ai-action-line">
                {{ (a.draft as { month: string }).month }} 预算改为
                ¥{{ (a.draft as { amount: number }).amount }}
              </div>
              <div v-if="(a.draft as { previous: number | null }).previous" class="ai-action-line muted">
                当前是 ¥{{ (a.draft as { previous: number }).previous }}
              </div>
            </template>
            <el-button type="primary" size="small" style="margin-top: 8px" @click="confirmAction(a)">
              确认
            </el-button>
          </div>
        </div>

        <div v-if="busy" class="ai-typing">正在处理…</div>
      </div>

      <footer class="ai-input">
        <el-input
          v-model="input"
          placeholder="比如：午饭花了 25"
          maxlength="200"
          @keyup.enter="send()"
        />
        <el-button type="primary" :loading="busy" @click="send()">发送</el-button>
      </footer>
    </div>
  </el-drawer>
</template>

<style scoped>
.ai-fab {
  position: fixed;
  right: 26px;
  bottom: 26px;
  z-index: 30;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 11px 16px;
  border-radius: 999px;
  background: var(--accent, #4f46e5);
  color: #fff;
  font-size: 13.5px;
  cursor: pointer;
  box-shadow: 0 10px 26px rgba(102, 126, 234, 0.35);
  transition: transform 0.15s ease;
}
.ai-fab:hover {
  transform: translateY(-2px);
}
.ai-fab-icon {
  font-size: 14px;
}

.ai-panel {
  display: flex;
  flex-direction: column;
  height: 100%;
}
.ai-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  padding: 4px 2px 12px;
  border-bottom: 1px solid rgba(102, 126, 234, 0.12);
}
.ai-title {
  font-size: 15px;
  color: var(--text-primary, #1f2430);
}
.ai-sub {
  font-size: 12px;
  color: var(--text-secondary, #7b8494);
  margin-top: 2px;
}

.ai-list {
  flex: 1;
  overflow-y: auto;
  padding: 14px 2px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.ai-empty-title {
  font-size: 13px;
  color: var(--text-secondary, #7b8494);
  margin-bottom: 8px;
}
.ai-quick {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}
.ai-chip {
  border: 1px solid rgba(102, 126, 234, 0.22);
  background: rgba(102, 126, 234, 0.06);
  color: var(--text-primary, #1f2430);
  border-radius: 999px;
  padding: 6px 12px;
  font-size: 12.5px;
  cursor: pointer;
}
.ai-chip:hover {
  border-color: var(--accent, #4f46e5);
}

.ai-row {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.ai-row.user {
  align-items: flex-end;
}
.ai-bubble {
  max-width: 88%;
  padding: 10px 13px;
  border-radius: 14px;
  font-size: 13.5px;
  line-height: 1.6;
  white-space: pre-wrap;
  background: #fff;
  border: 1px solid rgba(102, 126, 234, 0.14);
  color: var(--text-primary, #1f2430);
}
.ai-row.user .ai-bubble {
  background: var(--accent, #4f46e5);
  border-color: transparent;
  color: #fff;
}

.ai-action {
  max-width: 92%;
  padding: 12px;
  border-radius: 12px;
  background: rgba(102, 126, 234, 0.06);
  border: 1px solid rgba(102, 126, 234, 0.18);
}
.ai-action-title {
  font-size: 12px;
  color: var(--text-secondary, #7b8494);
  margin-bottom: 4px;
}
.ai-action-line {
  font-size: 13.5px;
  color: var(--text-primary, #1f2430);
  line-height: 1.6;
}
.ai-action-line.muted {
  font-size: 12px;
  color: var(--text-secondary, #7b8494);
}

.ai-typing {
  font-size: 12px;
  color: var(--text-secondary, #7b8494);
}

.ai-input {
  display: flex;
  gap: 8px;
  padding-top: 12px;
  border-top: 1px solid rgba(102, 126, 234, 0.12);
}

@media (max-width: 768px) {
  .ai-fab {
    right: 16px;
    bottom: 76px;
    padding: 10px 14px;
  }
}
</style>
