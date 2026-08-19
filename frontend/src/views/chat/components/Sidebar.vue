<template>
  <aside class="sidebar">
    <button class="new-btn" type="button" @click="$emit('new')">+ 新会话</button>
    <ul class="conv-list">
      <li v-for="c in conversations" :key="c.conversation_id" class="conv-item"
          :class="{ active: c.conversation_id === currentId }"
          @click="$emit('select', c.conversation_id)">
        <span class="title" :title="c.title">{{ c.title }}</span>
        <el-popconfirm title="删除该会话？" width="180" @confirm="$emit('remove', c.conversation_id)">
          <template #reference>
            <span class="del" @click.stop>×</span>
          </template>
        </el-popconfirm>
      </li>
    </ul>
    <p v-if="!conversations.length" class="empty">暂无历史会话</p>
  </aside>
</template>

<script setup>
defineProps({
  conversations: { type: Array, default: () => [] },
  currentId: { type: String, default: null },
})
defineEmits(['new', 'select', 'remove'])
</script>

<style scoped>
.sidebar {
  width: 240px;
  border-right: 1px solid #e4e7ed;
  display: flex;
  flex-direction: column;
  background: #fafafa;
}
.new-btn {
  margin: 12px;
  padding: 8px 12px;
  border: 1px solid #d9ecff;
  border-radius: 8px;
  background: #ecf5ff;
  color: #409eff;
  cursor: pointer;
  font-size: 14px;
}
.conv-list {
  flex: 1;
  overflow-y: auto;
  list-style: none;
  margin: 0;
  padding: 0 8px;
}
.conv-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 8px 10px;
  border-radius: 8px;
  cursor: pointer;
  color: #303133;
}
.conv-item:hover { background: #f0f2f5; }
.conv-item.active { background: #e6f4ff; }
.title {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  font-size: 14px;
}
.del { color: #c0c4cc; margin-left: 8px; }
.del:hover { color: #f56c6c; }
.empty { padding: 16px; color: #909399; font-size: 13px; }
</style>
