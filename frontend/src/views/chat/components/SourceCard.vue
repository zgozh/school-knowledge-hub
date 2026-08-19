<template>
  <div class="source-card">
    <el-link :href="source.url" target="_blank" type="primary" class="source-title">
      {{ source.title || '未命名文档' }}
    </el-link>
    <div class="source-meta">
      <span>{{ source.category || '未分类' }}</span>
      <span class="dot">·</span>
      <span>{{ formatDate(source.publish_date) }}</span>
      <el-tag v-if="source.expired" type="warning" size="small" class="expired-tag">可能已过期</el-tag>
    </div>
  </div>
</template>

<script setup>
import { formatDate } from '../../../utils/format'

defineProps({
  source: { type: Object, required: true },
})
</script>

<style scoped>
.source-card {
  padding: 8px 12px;
  border: 1px solid #e4e7ed;
  border-radius: 8px;
  background: #fafafa;
}
.source-title {
  font-size: 14px;
  line-height: 1.4;
  justify-content: flex-start;
  text-align: left;
}
.source-meta {
  margin-top: 4px;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 12px;
  color: #909399;
}
.expired-tag {
  margin-left: 2px;
}
</style>
