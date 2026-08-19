// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount } from '@vue/test-utils'
import { createRouter, createMemoryHistory } from 'vue-router'
import ElementPlus from 'element-plus'
import ChatView from '../src/views/chat/ChatView.vue'

vi.mock('../src/api/chat', () => ({
  askChat: vi.fn(),
  listConversations: vi.fn().mockResolvedValue([]),
  getConversation: vi.fn(),
  deleteConversation: vi.fn(),
}))

import { askChat, listConversations } from '../src/api/chat'

const router = createRouter({
  history: createMemoryHistory(),
  routes: [
    { path: '/', component: { template: '<div>chat</div>' } },
    { path: '/admin', component: { template: '<div>admin</div>' } },
  ],
})

function mountView() {
  return mount(ChatView, {
    global: {
      plugins: [ElementPlus, router],
      stubs: { TopicSelect: true, MessageList: true, Sidebar: true },
    },
    attachTo: document.body,
  })
}

describe('ChatView 会话集成', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('挂载时加载会话列表', async () => {
    listConversations.mockResolvedValue([{ conversation_id: 'c1', title: 't', updated_at: '', message_count: 1 }])
    mountView()
    await router.isReady()
    await new Promise((r) => setTimeout(r, 0))
    expect(listConversations).toHaveBeenCalled()
  })

  it('新会话发消息传 conversation_id=null 并在 done 记新 id', async () => {
    const wrapper = mountView()
    await router.isReady()
    askChat.mockImplementation((q, topic, cid, cb) => {
      cb.onDone?.({ conversation_id: 'new123' })
      return Promise.resolve()
    })
    await wrapper.find('textarea').setValue('新生报到')
    await wrapper.find('button.el-button--primary').trigger('click')
    expect(askChat).toHaveBeenCalledWith('新生报到', null, null, expect.any(Object))
  })
})
