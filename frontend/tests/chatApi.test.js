// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { listConversations, getConversation, deleteConversation } from '../src/api/chat'

describe('会话 API 层', () => {
  beforeEach(() => { global.fetch = vi.fn() })
  afterEach(() => { vi.restoreAllMocks() })

  it('listConversations 调 GET /qa-api/api/conversations', async () => {
    global.fetch.mockResolvedValue({ ok: true, json: async () => [{ conversation_id: 'c1' }] })
    const out = await listConversations()
    expect(out[0].conversation_id).toBe('c1')
    expect(global.fetch).toHaveBeenCalledWith('/qa-api/api/conversations',
      expect.objectContaining({ method: 'GET' }))
  })

  it('getConversation 调 GET 详情', async () => {
    global.fetch.mockResolvedValue({ ok: true, json: async () => ({ conversation_id: 'c1', messages: [] }) })
    await getConversation('c1')
    expect(global.fetch).toHaveBeenCalledWith('/qa-api/api/conversations/c1', expect.any(Object))
  })

  it('deleteConversation 调 DELETE', async () => {
    global.fetch.mockResolvedValue({ ok: true, json: async () => ({ deleted: true }) })
    await deleteConversation('c1')
    expect(global.fetch).toHaveBeenCalledWith('/qa-api/api/conversations/c1',
      expect.objectContaining({ method: 'DELETE' }))
  })
})
