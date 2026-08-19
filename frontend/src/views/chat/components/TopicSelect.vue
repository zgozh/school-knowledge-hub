<template>
  <el-select
    :model-value="modelValue"
    class="topic-select"
    :disabled="disabled"
    @update:model-value="$emit('update:modelValue', $event)"
  >
    <el-option label="全部专题" value="" />
    <el-option v-for="topic in TOPICS" :key="topic" :label="topic" :value="topic" />
  </el-select>
</template>

<script setup>
import { TOPICS } from '../../../utils/format'

defineProps({
  modelValue: { type: String, default: '' },
  disabled: { type: Boolean, default: false },
})
defineEmits(['update:modelValue'])
</script>

<style scoped>
.topic-select {
  width: 160px;
}
</style>
