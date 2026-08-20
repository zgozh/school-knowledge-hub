<template>
  <el-card>
    <template #header>
      <div class="card-header">
        <span>采集源管理</span>
        <el-button type="primary" @click="openCreate">新增采集源</el-button>
      </div>
    </template>

    <el-table v-loading="loading" :data="sources" row-key="id" empty-text="暂无采集源">
      <el-table-column prop="name" label="名称" min-width="150" show-overflow-tooltip />
      <el-table-column prop="list_url" label="列表 URL" min-width="280" show-overflow-tooltip />
      <el-table-column label="适配器" width="160">
        <template #default="{ row }">{{ ADAPTERS[row.adapter] || row.adapter }}</template>
      </el-table-column>
      <el-table-column prop="interval_minutes" label="间隔（分钟）" width="110" align="center" />
      <el-table-column label="状态" width="90" align="center">
        <template #default="{ row }">
          <el-tag :type="row.enabled ? 'success' : 'info'">{{ row.enabled ? '启用' : '停用' }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="190" fixed="right">
        <template #default="{ row }">
          <el-button size="small" type="primary" :loading="runningId === row.id" @click="onRun(row)">
            立即采集
          </el-button>
          <el-popconfirm
            title="确认删除该采集源？"
            confirm-button-text="删除"
            confirm-button-type="danger"
            cancel-button-text="取消"
            width="200"
            @confirm="onDelete(row)"
          >
            <template #reference>
              <el-button size="small" type="danger">删除</el-button>
            </template>
          </el-popconfirm>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dialogVisible" title="新增采集源" width="480px" :close-on-click-modal="false">
      <el-form ref="formRef" :model="form" :rules="rules" label-width="100px">
        <el-form-item label="名称" prop="name">
          <el-input v-model="form.name" placeholder="如：广州大学教务处" />
        </el-form-item>
        <el-form-item label="列表 URL" prop="list_url">
          <el-input v-model="form.list_url" placeholder="https://..." />
        </el-form-item>
        <el-form-item label="适配器" prop="adapter">
          <el-select v-model="form.adapter" placeholder="选择站点适配器" style="width: 100%">
            <el-option v-for="(label, value) in ADAPTERS" :key="value" :label="`${label}（${value}）`" :value="value" />
          </el-select>
        </el-form-item>
        <el-form-item label="启用">
          <el-switch v-model="form.enabled" />
        </el-form-item>
        <el-form-item label="采集间隔" prop="interval_minutes">
          <el-input-number v-model="form.interval_minutes" :min="1" :max="1440" />
          <span class="unit">分钟</span>
        </el-form-item>
        <el-form-item label="采集页数" prop="max_pages">
          <el-select v-model="form.max_pages" style="width: 100%">
            <el-option v-for="opt in PAGE_OPTIONS" :key="opt.value" :label="opt.label" :value="opt.value" />
          </el-select>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="dialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="creating" @click="onCreate">确定</el-button>
      </template>
    </el-dialog>
  </el-card>
</template>

<script setup>
import { onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { useSources } from '../../composables/useSources'
import { ADAPTERS } from '../../utils/format'

const { sources, loading, error, load, create, remove, run } = useSources()

const dialogVisible = ref(false)
const creating = ref(false)
const runningId = ref('')
const formRef = ref()
const PAGE_OPTIONS = [
  { label: '1 页（默认）', value: 1 },
  { label: '3 页', value: 3 },
  { label: '5 页', value: 5 },
  { label: '10 页', value: 10 },
  { label: '全部', value: 0 },
]
const defaultForm = { name: '', list_url: '', adapter: '', enabled: true, interval_minutes: 360, max_pages: 1 }
const form = reactive({ ...defaultForm })

const rules = {
  name: [{ required: true, message: '请输入名称', trigger: 'blur' }],
  list_url: [{ required: true, message: '请输入列表 URL', trigger: 'blur' }],
  adapter: [{ required: true, message: '请选择适配器', trigger: 'change' }],
  interval_minutes: [{ required: true, message: '请设置采集间隔', trigger: 'blur' }],
}

onMounted(async () => {
  if (!(await load())) ElMessage.error(error.value)
})

function openCreate() {
  Object.assign(form, defaultForm)
  dialogVisible.value = true
}

async function onCreate() {
  try {
    await formRef.value.validate()
  } catch {
    return // 校验未通过，停留在弹窗
  }
  creating.value = true
  try {
    await create({ ...form })
    dialogVisible.value = false
    ElMessage.success('采集源已创建')
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    creating.value = false
  }
}

async function onDelete(row) {
  try {
    await remove(row.id)
    ElMessage.success('已删除')
  } catch (e) {
    ElMessage.error(e.message)
  }
}

async function onRun(row) {
  runningId.value = row.id
  try {
    await run(row.id)
    ElMessage.success('已触发采集')
  } catch (e) {
    ElMessage.error(e.message)
  } finally {
    runningId.value = ''
  }
}
</script>

<style scoped>
.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
}
.unit {
  margin-left: 8px;
  color: #909399;
}
</style>
