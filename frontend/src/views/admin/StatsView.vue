<template>
  <el-card v-loading="loading">
    <template #header>
      <div class="card-header">
        <span>资产全景</span>
        <el-button type="primary" plain :loading="loading" @click="load">刷新</el-button>
      </div>
    </template>

    <!-- 指标卡 -->
    <el-row :gutter="16" class="metric-row">
      <el-col v-for="m in metrics" :key="m.label" :span="6">
        <el-card shadow="hover" class="metric-card">
          <div class="metric-value" :style="{ color: m.color }">{{ m.value }}</div>
          <div class="metric-label">{{ m.label }}</div>
        </el-card>
      </el-col>
    </el-row>

    <el-row :gutter="16">
      <!-- 图表区 -->
      <el-col :span="16">
        <el-row :gutter="16">
          <el-col :span="12">
            <el-card shadow="never" class="panel-card">
              <template #header>分类分布</template>
              <div v-if="hasCategory" ref="categoryEl" class="chart"></div>
              <div v-else class="chart-empty">暂无数据</div>
            </el-card>
          </el-col>
          <el-col :span="12">
            <el-card shadow="never" class="panel-card">
              <template #header>状态分布</template>
              <div v-if="hasStatus" ref="statusEl" class="chart"></div>
              <div v-else class="chart-empty">暂无数据</div>
            </el-card>
          </el-col>
          <el-col :span="24">
            <el-card shadow="never" class="panel-card">
              <template #header>专题域分布</template>
              <div v-if="hasTopic" ref="topicEl" class="chart chart-bar"></div>
              <div v-else class="chart-empty">暂无数据</div>
            </el-card>
          </el-col>
        </el-row>
      </el-col>

      <!-- 右栏 -->
      <el-col :span="8">
        <el-card shadow="never" class="panel-card">
          <template #header>最近采集任务</template>
          <el-table :data="recentTasks" size="small" empty-text="暂无采集任务">
            <el-table-column prop="task_id" label="任务 ID" min-width="90" show-overflow-tooltip />
            <el-table-column label="状态" width="90" align="center">
              <template #default="{ row }">
                <el-tag :type="STATUS_TYPE[row.status] || 'info'" size="small">
                  {{ STATUS_TEXT[row.status] || row.status }}
                </el-tag>
              </template>
            </el-table-column>
            <el-table-column prop="succeeded" label="成功" width="60" align="center" />
            <el-table-column prop="failed" label="失败" width="60" align="center" />
            <el-table-column label="开始时间" width="140">
              <template #default="{ row }">{{ formatDate(row.started_at) }}</template>
            </el-table-column>
          </el-table>
        </el-card>

        <el-card shadow="never" class="panel-card">
          <template #header>热门问题 TOP5</template>
          <ul v-if="hotQueries.length" class="hot-list">
            <li v-for="(q, i) in hotQueries" :key="i">
              <span class="hot-rank" :class="{ top: i < 3 }">{{ i + 1 }}</span>
              <span class="hot-query" :title="q.query">{{ q.query }}</span>
              <el-tag size="small" type="info">{{ q.count }} 次</el-tag>
            </li>
          </ul>
          <div v-else class="side-empty">暂无热门问题</div>
        </el-card>
      </el-col>
    </el-row>
  </el-card>
</template>

<script setup>
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts/core'
import { BarChart, PieChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { adminApi } from '../../api/admin'
import { STATUS_TEXT, STATUS_TYPE, formatDate } from '../../utils/format'

echarts.use([PieChart, BarChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const loading = ref(false)
const stats = ref(null)
const categoryEl = ref(null)
const statusEl = ref(null)
const topicEl = ref(null)
let chartInstances = []

const byCategory = computed(() => stats.value?.by_category || {})
const byStatus = computed(() => stats.value?.by_status || {})
// 后端对无专题文档的聚合键为 "None"（str(None)），展示时过滤
const byTopic = computed(() =>
  Object.fromEntries(Object.entries(stats.value?.by_topic || {}).filter(([k]) => k && k !== 'None')),
)
const hasCategory = computed(() => Object.keys(byCategory.value).length > 0)
const hasStatus = computed(() => Object.keys(byStatus.value).length > 0)
const hasTopic = computed(() => Object.keys(byTopic.value).length > 0)

const metrics = computed(() => [
  { label: '文档总量', value: stats.value?.total_docs ?? '-', color: '#409eff' },
  { label: '在用', value: stats.value?.by_status?.active ?? '-', color: '#67c23a' },
  { label: '已过期', value: stats.value?.by_status?.expired ?? '-', color: '#e6a23c' },
  { label: '问答总量', value: stats.value?.qa_total ?? '-', color: '#909399' },
])
const recentTasks = computed(() => stats.value?.recent_tasks || [])
const hotQueries = computed(() => stats.value?.hot_queries || [])

function disposeCharts() {
  chartInstances.forEach((c) => c.dispose())
  chartInstances = []
}

function mountChart(el, option) {
  if (!el) return
  const inst = echarts.init(el)
  inst.setOption(option)
  chartInstances.push(inst)
}

function pieSeries(data, radius) {
  return {
    tooltip: { trigger: 'item' },
    legend: { bottom: 0 },
    series: [{
      type: 'pie',
      radius,
      center: ['50%', '45%'],
      data,
      label: { formatter: '{b}: {c}' },
    }],
  }
}

function renderCharts() {
  disposeCharts()
  if (hasCategory.value) {
    mountChart(categoryEl.value, pieSeries(
      Object.entries(byCategory.value).map(([k, v]) => ({ name: k, value: v })),
      '60%',
    ))
  }
  if (hasStatus.value) {
    mountChart(statusEl.value, pieSeries(
      Object.entries(byStatus.value).map(([k, v]) => ({ name: STATUS_TEXT[k] || k, value: v })),
      ['40%', '65%'], // 环形
    ))
  }
  if (hasTopic.value) {
    const entries = Object.entries(byTopic.value)
    mountChart(topicEl.value, {
      tooltip: { trigger: 'axis' },
      grid: { left: 50, right: 20, top: 20, bottom: 30 },
      xAxis: { type: 'category', data: entries.map(([k]) => k), axisLabel: { interval: 0 } },
      yAxis: { type: 'value', minInterval: 1 },
      series: [{ type: 'bar', data: entries.map(([, v]) => v), barMaxWidth: 48, itemStyle: { color: '#409eff' } }],
    })
  }
}

async function load() {
  loading.value = true
  try {
    stats.value = await adminApi.stats()
    await nextTick() // 等 v-if 的图表容器渲染后再初始化 echarts
    renderCharts()
  } catch (e) {
    ElMessage.error(e.message || '加载统计数据失败')
  } finally {
    loading.value = false
  }
}

onMounted(load)
onUnmounted(disposeCharts)
</script>

<style scoped>
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.metric-row {
  margin-bottom: 16px;
}
.metric-card {
  text-align: center;
}
.metric-value {
  font-size: 28px;
  font-weight: 600;
  line-height: 1.4;
}
.metric-label {
  color: #909399;
  font-size: 13px;
  margin-top: 4px;
}
.panel-card {
  margin-bottom: 16px;
}
.chart {
  height: 280px;
}
.chart-bar {
  height: 300px;
}
.chart-empty {
  height: 280px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #909399;
}
.hot-list {
  margin: 0;
  padding: 0;
  list-style: none;
}
.hot-list li {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 0;
  border-bottom: 1px solid #f0f0f0;
}
.hot-list li:last-child {
  border-bottom: none;
}
.hot-rank {
  flex: none;
  width: 20px;
  height: 20px;
  line-height: 20px;
  text-align: center;
  border-radius: 4px;
  background: #f0f2f5;
  color: #909399;
  font-size: 12px;
}
.hot-rank.top {
  background: #ecf5ff;
  color: #409eff;
  font-weight: 600;
}
.hot-query {
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  color: #303133;
}
.side-empty {
  color: #909399;
  text-align: center;
  padding: 24px 0;
}
</style>
