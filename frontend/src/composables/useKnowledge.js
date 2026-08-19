import { ref } from 'vue'
import { adminApi } from '../api/admin'

export function useKnowledge() {
  const items = ref([])
  const total = ref(0)
  const loading = ref(false)
  const error = ref(null)

  async function load(params = {}) {
    loading.value = true
    error.value = null
    try {
      const data = await adminApi.listKnowledge(params)
      items.value = data.items || []
      total.value = data.total || 0
      return true
    } catch (e) {
      error.value = e.message
      return false
    } finally {
      loading.value = false
    }
  }

  async function setStatus(docId, status) {
    await adminApi.setDocStatus(docId, status)
  }

  async function expiryCheck() {
    return adminApi.expiryCheck()
  }

  async function getDetail(docId) {
    return adminApi.getKnowledgeDetail(docId)
  }

  return { items, total, loading, error, load, setStatus, expiryCheck, getDetail }
}
