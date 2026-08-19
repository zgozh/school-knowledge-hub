// @vitest-environment jsdom
import { describe, it, expect, vi } from 'vitest'
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
  })
}

describe('ChatView 双端入口', () => {
  it('页头提供管理端入口链接，指向 /admin', async () => {
    const wrapper = mountView()
    await router.isReady()
    const link = wrapper.find('a[href="/admin"]')
    expect(link.exists()).toBe(true)
    expect(link.text()).toContain('管理端')
  })
})
