// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { useConversations } from '../src/composables/useConversations'
import * as chatApi from '../src/api/chat'

vi.mock('../src/api/chat', () => ({
  listConversations: vi.fn(),
  getConversation: vi.fn(),
  deleteConversation: vi.fn(),
}))

describe('useConversations', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('loadList 拉列表', async () => {
    chatApi.listConversations.mockResolvedValue([{ conversation_id: 'c1', title: 't' }])
    const c = useConversations()
    await c.loadList()
    expect(c.list.value[0].conversation_id).toBe('c1')
  })

  it('newConversation 清空当前会话', async () => {
    const c = useConversations()
    c.currentId.value = 'c1'
    c.messages.value = [{ role: 'user', content: 'x' }]
    c.newConversation()
    expect(c.currentId.value).toBe(null)
    expect(c.messages.value).toEqual([])
  })

  it('openConversation 加载历史 messages', async () => {
    chatApi.getConversation.mockResolvedValue({
      conversation_id: 'c1', messages: [{ role: 'user', content: 'x' }],
    })
    const c = useConversations()
    await c.openConversation('c1')
    expect(c.currentId.value).toBe('c1')
    expect(c.messages.value[0].role).toBe('user')
    expect(c.loading.value).toBe(false)
  })

  it('removeConversation 删除后刷新列表', async () => {
    chatApi.deleteConversation.mockResolvedValue({ deleted: true })
    chatApi.listConversations.mockResolvedValue([])
    const c = useConversations()
    await c.removeConversation('c1')
    expect(chatApi.deleteConversation).toHaveBeenCalledWith('c1')
    expect(c.list.value).toEqual([])
  })

  it('removeConversation 删当前会话则回新会话态', async () => {
    chatApi.deleteConversation.mockResolvedValue({ deleted: true })
    chatApi.listConversations.mockResolvedValue([])
    const c = useConversations()
    c.currentId.value = 'c1'
    c.messages.value = [{ role: 'user', content: 'x' }]
    await c.removeConversation('c1')
    expect(c.currentId.value).toBe(null)
    expect(c.messages.value).toEqual([])
  })
})
