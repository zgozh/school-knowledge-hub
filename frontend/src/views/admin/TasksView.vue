<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span>采集任务</span>
        <el-button type="primary" plain :loading="loading" @click="onRefresh">刷新</el-button>
      </div>
    </template>

    <el-table v-loading="loading" :data="tasks" row-key="task_id" empty-text="暂无采集任务">
      <el-table-column type="expand">
        <template #default="{ row }">
          <div class="failures">
            <template v-if="row.failures && row.failures.length">
              <div class="failures-title">失败详情（{{ row.failures.length }} 条）</div>
              <ul class="failures-list">
                <li v-for="(f, i) in row.failures" :key="i">
                  <el-tag v-if="f.stage" size="small" type="warning" class="fail-stage">{{ f.stage }}</el-tag>
                  <span class="fail-url">{{ f.url }}</span>
                  <span class="fail-error">{{ f.error }}</span>
                </li>
              </ul>
            </template>
            <span v-else class="no-failures">无失败记录</span>
          </div>
        </template>
      </el-table-column>
      <el-table-column prop="task_id" label="任务 ID" min-width="210" show-overflow-tooltip />
      <el-table-column label="采集源" min-width="140" show-overflow-tooltip>
        <template #default="{ row }">{{ sourceName(row.source_id) }}</template>
      </el-table-column>
      <el-table-column label="状态" width="100" align="center">
        <template #default="{ row }">
          <el-tag :type="STATUS_TYPE[row.status] || 'info'">{{ STATUS_TEXT[row.status] || row.status }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="succeeded" label="成功" width="80" align="center" />
      <el-table-column prop="failed" label="失败" width="80" align="center" />
      <el-table-column label="开始时间" width="150">
        <template #default="{ row }">{{ formatDate(row.started_at) }}</template>
      </el-table-column>
      <el-table-column label="结束时间" width="150">
        <template #default="{ row }">{{ formatDate(row.finished_at) }}</template>
      </el-table-column>
    </el-table>
  </el-card>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { useTasks } from '../../composables/useTasks'
import { useSources } from '../../composables/useSources'
import { STATUS_TEXT, STATUS_TYPE, formatDate } from '../../utils/format'

// 任务列表（含 30s 自动刷新，卸载自动清理）
const { tasks, loading, error, refresh } = useTasks()
// 采集源 id → 名称映射（source_id 为 12 位 hex，需映射为人类可读名称）
const { sources, load: loadSources } = useSources()

const nameMap = computed(() => Object.fromEntries(sources.value.map((s) => [s.id, s.name])))
const sourceName = (id) => nameMap.value[id] || id

onMounted(loadSources) // 名称映射为增强展示，失败时静默回退为显示 id

async function onRefresh() {
  if (!(await refresh())) ElMessage.error(error.value)
}
</script>

<style scoped>
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.failures {
  padding: 4px 16px;
}
.failures-title {
  font-weight: 600;
  margin-bottom: 6px;
}
.failures-list {
  margin: 0;
  padding-left: 18px;
}
.failures-list li {
  margin-bottom: 4px;
  line-height: 1.6;
}
.fail-stage {
  margin-right: 6px;
}
.fail-url {
  color: #606266;
  margin-right: 8px;
  word-break: break-all;
}
.fail-error {
  color: #f56c6c;
}
.no-failures {
  color: #909399;
}
</style>
