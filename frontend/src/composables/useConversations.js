/** 会话状态：列表 / 当前会话 / 新建 / 切换 / 删除 / 加载。 */
import { ref } from 'vue'
import { listConversations, getConversation, deleteConversation } from '../api/chat'

export function useConversations() {
  const list = ref([])
  const currentId = ref(null)
  const messages = ref([])
  const loading = ref(false)

  async function loadList() {
    list.value = await listConversations()
  }

  function newConversation() {
    currentId.value = null
    messages.value = []
  }

  async function openConversation(id) {
    loading.value = true
    try {
      const conv = await getConversation(id)
      currentId.value = id
      messages.value = conv.messages || []
    } finally {
      loading.value = false
    }
  }

  async function removeConversation(id) {
    await deleteConversation(id)
    if (currentId.value === id) newConversation()
    await loadList()
  }

  return { list, currentId, messages, loading, loadList, newConversation, openConversation, removeConversation }
}
