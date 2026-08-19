<template>
  <div class="chat-view">
    <header class="chat-header">
      <h2 class="chat-title">校务智能问答</h2>
      <TopicSelect v-model="topic" :disabled="sending" />
      <router-link class="admin-entry" to="/admin">管理端</router-link>
    </header>

    <main class="chat-body">
      <div v-if="!messages.length" class="welcome">
        <h2>你好，我是校务智能助手</h2>
        <p class="welcome-tip">基于广州大学校务知识库作答，回答附来源。可以从这些示例开始：</p>
        <div class="examples">
          <el-button v-for="q in EXAMPLES" :key="q" round @click="send(q)">{{ q }}</el-button>
        </div>
      </div>
      <MessageList v-else :messages="messages" />
    </main>

    <footer class="chat-input">
      <el-input
        v-model="input"
        type="textarea"
        :autosize="{ minRows: 1, maxRows: 6 }"
        placeholder="输入你的校务问题（Enter 发送，Shift+Enter 换行）"
        :disabled="sending"
        @keydown.enter.exact.prevent="send(input)"
      />
      <el-button type="primary" :loading="sending" :disabled="!input.trim() || sending" @click="send(input)">
        发送
      </el-button>
    </footer>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { askChat } from '../../api/chat'
import MessageList from './components/MessageList.vue'
import TopicSelect from './components/TopicSelect.vue'

const EXAMPLES = [
  '2026年新生报到需要带什么材料？',
  '港澳生如何申请校内宿舍？',
  '奖学金评定需要满足哪些条件？',
]

const topic = ref('')
const input = ref('')
const sending = ref(false)
const messages = ref([])

function send(text) {
  const query = String(text || '').trim()
  if (!query || sending.value) return
  input.value = ''

  // 会话历史：内存数组，仅携带已成功作答的轮次
  const history = messages.value
    .filter((m) => m.role === 'user' || (m.role === 'assistant' && !m.error && !m.empty && m.content))
    .map((m) => ({ role: m.role, content: m.content }))

  messages.value.push({ role: 'user', content: query })
  const assistant = reactive({ role: 'assistant', content: '', sources: [], loading: true, error: false, empty: false })
  messages.value.push(assistant)
  sending.value = true

  askChat(query, topic.value || null, history, {
    onChunk(delta) {
      assistant.content += delta
    },
    onSources(sources) {
      assistant.sources = sources
      assistant.loading = false
    },
    onDone() {
      assistant.loading = false
      sending.value = false
    },
    onEmpty(message) {
      assistant.content = message
      assistant.empty = true
      assistant.loading = false
      sending.value = false
    },
    onError(message) {
      assistant.content = message
      assistant.error = true
      assistant.loading = false
      sending.value = false
    },
  }).finally(() => {
    // 兜底：流异常中断（未收到 done/empty/error）时复位状态
    assistant.loading = false
    sending.value = false
  })
}
</script>

<style scoped>
.chat-view {
  display: flex;
  flex-direction: column;
  height: 100svh;
  text-align: left;
  background: #fff;
}
.chat-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  padding: 12px 24px;
  border-bottom: 1px solid #e4e7ed;
}
.chat-title {
  margin: 0;
  font-size: 18px;
  color: #303133;
}
.chat-body {
  flex: 1;
  min-height: 0;
  display: flex;
  flex-direction: column;
}
.welcome {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  padding: 24px;
  text-align: center;
}
.welcome h2 {
  margin: 0;
  color: #303133;
}
.welcome-tip {
  margin: 0;
  color: #909399;
  font-size: 14px;
}
.examples {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: 10px;
  margin-top: 8px;
}
.examples .el-button + .el-button {
  margin-left: 0;
}
.chat-input {
  display: flex;
  align-items: flex-end;
  gap: 12px;
  padding: 14px 24px;
  border-top: 1px solid #e4e7ed;
}
.chat-input .el-input {
  flex: 1;
}
.admin-entry {
  font-size: 14px;
  color: #409eff;
  text-decoration: none;
  white-space: nowrap;
}
</style>
