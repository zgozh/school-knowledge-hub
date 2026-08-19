<template>
  <section class="knowledge-page">
    <div class="page-heading">
      <div>
        <h2>知识库管理</h2>
        <p>查看、筛选并治理采集后的校务知识资产。</p>
      </div>
      <el-button type="primary" plain :loading="checking" @click="onExpiryCheck">到期检测</el-button>
    </div>

    <el-card class="filter-card" shadow="never">
      <el-form :inline="true" :model="filters" @submit.prevent="onSearch">
        <el-form-item label="关键词">
          <el-input v-model="filters.keyword" clearable placeholder="搜索当前结果标题" @keyup.enter="onSearch" />
        </el-form-item>
        <el-form-item label="状态">
          <el-select v-model="filters.status" clearable placeholder="全部状态" class="filter-select">
            <el-option label="在用" value="active" />
            <el-option label="已下架" value="archived" />
            <el-option label="已过期" value="expired" />
          </el-select>
        </el-form-item>
        <el-form-item label="分类">
          <el-select v-model="filters.category" clearable placeholder="全部分类" class="filter-select">
            <el-option v-for="category in CATEGORIES" :key="category" :label="category" :value="category" />
          </el-select>
        </el-form-item>
        <el-form-item label="专题域">
          <el-select v-model="filters.topic" clearable placeholder="全部专题" class="filter-select">
            <el-option v-for="topic in TOPICS" :key="topic" :label="topic" :value="topic" />
          </el-select>
        </el-form-item>
        <el-form-item>
          <el-button type="primary" @click="onSearch">查询</el-button>
          <el-button @click="onReset">重置</el-button>
        </el-form-item>
      </el-form>
    </el-card>

    <el-card shadow="never">
      <el-table v-loading="loading" :data="visibleItems" row-key="doc_id" empty-text="暂无符合条件的知识资产">
        <el-table-column label="标题" min-width="250" show-overflow-tooltip>
          <template #default="{ row }">
            <el-button link type="primary" class="title-btn" @click="openDetail(row)">{{ row.title || '未命名文档' }}</el-button>
          </template>
        </el-table-column>
        <el-table-column label="分类" width="110">
          <template #default="{ row }"><el-tag size="small">{{ row.category || '-' }}</el-tag></template>
        </el-table-column>
        <el-table-column label="专题域" min-width="180">
          <template #default="{ row }">
            <el-space wrap>
              <el-tag v-for="topic in row.topics || []" :key="topic" size="small" type="info">{{ topic }}</el-tag>
              <span v-if="!row.topics?.length" class="muted">-</span>
            </el-space>
          </template>
        </el-table-column>
        <el-table-column prop="department" label="发布部门" width="130" show-overflow-tooltip />
        <el-table-column label="发布日期" width="120"><template #default="{ row }">{{ formatDate(row.publish_date) }}</template></el-table-column>
        <el-table-column label="有效期至" width="120"><template #default="{ row }">{{ row.expire_at || '-' }}</template></el-table-column>
        <el-table-column label="状态" width="95" align="center">
          <template #default="{ row }"><el-tag :type="STATUS_TYPE[row.status] || 'info'">{{ STATUS_TEXT[row.status] || row.status }}</el-tag></template>
        </el-table-column>
        <el-table-column label="操作" width="110" fixed="right">
          <template #default="{ row }">
            <el-popconfirm
              :title="row.status === 'active' ? '确认下架该文档？' : '确认上架该文档？'"
              :confirm-button-text="row.status === 'active' ? '下架' : '上架'"
              cancel-button-text="取消"
              @confirm="onToggle(row)"
            >
              <template #reference>
                <el-button link type="primary">{{ row.status === 'active' ? '下架' : '上架' }}</el-button>
              </template>
            </el-popconfirm>
          </template>
        </el-table-column>
      </el-table>
      <div class="pagination-row">
        <span class="muted">共 {{ total }} 条</span>
        <el-pagination v-model:current-page="page" v-model:page-size="pageSize" :total="total" background layout="sizes, prev, pager, next" :page-sizes="[10, 20, 50]" @current-change="loadPage" @size-change="onSizeChange" />
      </div>
    </el-card>

    <el-drawer v-model="detailVisible" :title="detail?.title || '文档详情'" size="48%">
      <div v-loading="detailLoading" class="detail-body">
        <template v-if="detail">
          <el-descriptions :column="2" border>
            <el-descriptions-item label="分类">{{ detail.category || '-' }}</el-descriptions-item>
            <el-descriptions-item label="专题域">{{ (detail.topics || []).join('、') || '-' }}</el-descriptions-item>
            <el-descriptions-item label="发布部门">{{ detail.department || '-' }}</el-descriptions-item>
            <el-descriptions-item label="发布日期">{{ formatDate(detail.publish_date) }}</el-descriptions-item>
            <el-descriptions-item label="有效期至">{{ detail.expire_at || '-' }}</el-descriptions-item>
            <el-descriptions-item label="状态">{{ STATUS_TEXT[detail.status] || detail.status }}</el-descriptions-item>
            <el-descriptions-item label="来源站点">{{ detail.source_site || '-' }}</el-descriptions-item>
            <el-descriptions-item label="栏目">{{ detail.column || '-' }}</el-descriptions-item>
          </el-descriptions>
          <el-divider content-position="left">正文</el-divider>
          <p class="detail-content">{{ detail.content || '（正文读取失败或缺失）' }}</p>
          <div class="detail-actions">
            <el-button v-if="!isDemoUrl(detail.url)" type="primary" plain @click="openOrigin(detail.url)">打开原文</el-button>
            <el-tag v-else type="info">模拟数据（无外部原文）</el-tag>
          </div>
        </template>
      </div>
    </el-drawer>
  </section>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useKnowledge } from '../../composables/useKnowledge'
import { CATEGORIES, TOPICS, STATUS_TEXT, STATUS_TYPE, formatDate } from '../../utils/format'

const { items, total, loading, error, load, setStatus, expiryCheck, getDetail } = useKnowledge()
const page = ref(1)
const pageSize = ref(20)
const checking = ref(false)
const detailVisible = ref(false)
const detailLoading = ref(false)
const detail = ref(null)
const filters = reactive({ keyword: '', status: '', category: '', topic: '' })
const visibleItems = computed(() => {
  const keyword = filters.keyword.trim().toLowerCase()
  if (!keyword) return items.value
  return items.value.filter((item) => String(item.title || '').toLowerCase().includes(keyword))
})

async function loadPage() {
  const ok = await load({ status: filters.status || undefined, category: filters.category || undefined, topic: filters.topic || undefined, page: page.value, page_size: pageSize.value })
  if (!ok) ElMessage.error(error.value || '知识库加载失败')
}
function onSearch() { page.value = 1; loadPage() }
function onReset() { Object.assign(filters, { keyword: '', status: '', category: '', topic: '' }); page.value = 1; loadPage() }
function onSizeChange(size) { pageSize.value = size; page.value = 1; loadPage() }
async function onToggle(row) {
  try {
    await setStatus(row.doc_id, row.status === 'active' ? 'archived' : 'active')
    ElMessage.success('状态已更新')
    await loadPage()
  } catch (e) { ElMessage.error(e.message) }
}
async function onExpiryCheck() {
  checking.value = true
  try {
    const result = await expiryCheck()
    ElMessage.success(`已将 ${result.expired_count || 0} 篇文档标记为过期`)
    await loadPage()
  } catch (e) { ElMessage.error(e.message) } finally { checking.value = false }
}
function isDemoUrl(url) {
  return (url || '').startsWith('https://demo.gzhu.edu.cn/')
}
async function openDetail(row) {
  detailVisible.value = true
  detailLoading.value = true
  detail.value = null
  try {
    detail.value = await getDetail(row.doc_id)
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    detailLoading.value = false
  }
}
function openOrigin(url) {
  window.open(url, '_blank')
}
onMounted(loadPage)
</script>

<style scoped>
.knowledge-page { display: flex; flex-direction: column; gap: 16px; }
.page-heading, .card-header, .pagination-row { display: flex; align-items: center; justify-content: space-between; gap: 16px; }
.page-heading h2 { margin: 0 0 4px; color: #1f2937; font-size: 22px; }
.page-heading p { margin: 0; color: #64748b; font-size: 14px; }
.filter-card :deep(.el-form-item) { margin-bottom: 0; }
.filter-select { width: 150px; }
.pagination-row { padding-top: 16px; }
.muted { color: #94a3b8; font-size: 13px; }
.title-btn { padding: 0; }
.detail-body { min-height: 200px; }
.detail-content { white-space: pre-wrap; color: #334155; line-height: 1.8; }
.detail-actions { margin-top: 16px; }
@media (max-width: 900px) { .filter-card :deep(.el-form) { display: flex; flex-wrap: wrap; } .filter-select { width: 130px; } }
</style>
