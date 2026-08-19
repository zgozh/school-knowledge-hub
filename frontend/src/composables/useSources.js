/** 采集源列表加载与操作（新增/删除/触发采集）。状态与错误内聚，消息提示由视图层负责。 */
import { ref } from 'vue'
import { adminApi } from '../api/admin'

export function useSources() {
  const sources = ref([])
  const loading = ref(false)
  const error = ref(null)

  /** 加载列表；成功返回 true，失败置 error 并返回 false（不抛出，便于静默刷新）。 */
  async function load() {
    loading.value = true
    error.value = null
    try {
      const data = await adminApi.listSources()
      sources.value = data.items || []
      return true
    } catch (e) {
      error.value = e.message
      return false
    } finally {
      loading.value = false
    }
  }

  /** 新增采集源后刷新列表；失败抛出（视图层提示）。 */
  async function create(payload) {
    await adminApi.createSource(payload)
    await load()
  }

  /** 删除采集源后刷新列表；失败抛出（视图层提示）。 */
  async function remove(id) {
    await adminApi.deleteSource(id)
    await load()
  }

  /** 触发一次采集；失败抛出（视图层提示）。 */
  async function run(id) {
    await adminApi.runTask(id)
  }

  return { sources, loading, error, load, create, remove, run }
}
