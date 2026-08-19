// @vitest-environment jsdom
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import Sidebar from '../src/views/chat/components/Sidebar.vue'

const conversations = [
  { conversation_id: 'c1', title: '新生报到', updated_at: '2026-08-20 10:00:00', message_count: 2 },
  { conversation_id: 'c2', title: '奖学金评定', updated_at: '2026-08-19 09:00:00', message_count: 4 },
]

function mountSidebar(props = {}) {
  return mount(Sidebar, {
    props: { conversations, currentId: 'c1', ...props },
    global: { plugins: [ElementPlus] },
    attachTo: document.body,
  })
}

describe('Sidebar', () => {
  it('渲染会话列表与新会话按钮', () => {
    const wrapper = mountSidebar()
    expect(wrapper.text()).toContain('新会话')
    expect(wrapper.text()).toContain('新生报到')
    expect(wrapper.text()).toContain('奖学金评定')
  })

  it('点新会话触发 new 事件', async () => {
    const wrapper = mountSidebar()
    await wrapper.find('.new-btn').trigger('click')
    expect(wrapper.emitted('new')).toBeTruthy()
  })

  it('点会话触发 select 事件带 id', async () => {
    const wrapper = mountSidebar()
    await wrapper.findAll('.conv-item')[1].trigger('click')
    expect(wrapper.emitted('select')[0]).toEqual(['c2'])
  })

  it('删除确认后触发 remove 事件带 id', async () => {
    const wrapper = mountSidebar()
    wrapper.findComponent({ name: 'ElPopconfirm' }).vm.$emit('confirm')
    await wrapper.vm.$nextTick()
    expect(wrapper.emitted('remove')[0]).toEqual(['c1'])
  })

  it('空列表显示空态', () => {
    const wrapper = mountSidebar({ conversations: [] })
    expect(wrapper.text()).toContain('暂无历史会话')
  })
})
