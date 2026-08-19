<template>
  <div ref="scrollRef" class="message-list">
    <div v-for="(msg, index) in messages" :key="index" class="message-row" :class="msg.role">
      <div class="bubble">
        <template v-if="msg.role === 'user'">{{ msg.content }}</template>
        <template v-else>
          <div v-if="msg.loading && !msg.content" class="generating">
            <span class="spinner" />正在生成回答…
          </div>
          <div v-else-if="msg.error" class="error-text">{{ msg.content }}</div>
          <div v-else-if="msg.empty" class="empty-text">{{ msg.content }}</div>
          <MarkdownRender v-else :content="msg.content" :final="!msg.loading" />
          <div v-if="msg.sources?.length" class="sources">
            <div class="sources-title">参考来源</div>
            <SourceCard v-for="s in msg.sources" :key="s.doc_id" :source="s" />
          </div>
        </template>
      </div>
    </div>
  </div>
</template>

<script setup>
import { nextTick, ref, watch } from 'vue'
import MarkdownRender from 'markstream-vue'
import 'markstream-vue/index.css'
import SourceCard from './SourceCard.vue'

const props = defineProps({
  messages: { type: Array, required: true },
})

const scrollRef = ref(null)
watch(
  () => props.messages,
  async () => {
    await nextTick()
    const el = scrollRef.value
    if (el) el.scrollTop = el.scrollHeight
  },
  { deep: true },
)
</script>

<style scoped>
.message-list {
  flex: 1;
  overflow-y: auto;
  padding: 20px 24px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}
.message-row {
  display: flex;
}
.message-row.user {
  justify-content: flex-end;
}
.message-row.assistant {
  justify-content: flex-start;
}
.bubble {
  max-width: 78%;
  padding: 10px 14px;
  border-radius: 10px;
  font-size: 15px;
  line-height: 1.6;
  text-align: left;
  word-break: break-word;
}
.message-row.user .bubble {
  background: #ecf5ff;
  color: #303133;
  border: 1px solid #d9ecff;
  white-space: pre-wrap;
}
.message-row.assistant .bubble {
  background: #f4f4f5;
  color: #303133;
  border: 1px solid #e9e9eb;
}
.generating {
  display: flex;
  align-items: center;
  gap: 8px;
  color: #909399;
}
.spinner {
  width: 14px;
  height: 14px;
  border: 2px solid #dcdfe6;
  border-top-color: #409eff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
.error-text {
  color: #f56c6c;
  white-space: pre-wrap;
}
.empty-text {
  color: #909399;
  white-space: pre-wrap;
}
.sources {
  margin-top: 10px;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.sources-title {
  font-size: 12px;
  color: #909399;
}
.bubble :deep(.markdown-body) :first-child {
  margin-top: 0;
}
.bubble :deep(.markdown-body) :last-child {
  margin-bottom: 0;
}
</style>
