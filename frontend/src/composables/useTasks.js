/** 采集任务列表加载 + 30s 定时自动刷新（组件卸载时自动清理定时器）。 */
import { onMounted, onUnmounted, ref } from 'vue'
import { adminApi } from '../api/admin'

const AUTO_REFRESH_MS = 30000

export function useTasks(limit = 50) {
  const tasks = ref([])
  const loading = ref(false)
  const error = ref(null)
  let timer = null

  /** 刷新列表；silent=true 为后台轮询（不触发 loading 闪烁）。成功返回 true，失败置 error 返回 false。 */
  async function refresh({ silent = false } = {}) {
    if (!silent) loading.value = true
    error.value = null
    try {
      const data = await adminApi.listTasks({ limit })
      tasks.value = data.items || []
      return true
    } catch (e) {
      error.value = e.message
      return false
    } finally {
      if (!silent) loading.value = false
    }
  }

  onMounted(() => {
    refresh()
    timer = setInterval(() => refresh({ silent: true }), AUTO_REFRESH_MS)
  })

  onUnmounted(() => clearInterval(timer))

  return { tasks, loading, error, refresh }
}
