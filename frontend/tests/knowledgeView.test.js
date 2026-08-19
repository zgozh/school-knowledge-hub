// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'

const mocks = vi.hoisted(() => ({
  listKnowledge: vi.fn(),
  getKnowledgeDetail: vi.fn(),
  setDocStatus: vi.fn(),
  expiryCheck: vi.fn(),
}))

vi.mock('../src/api/admin', () => ({ adminApi: mocks }))

import KnowledgeView from '../src/views/admin/KnowledgeView.vue'

function mountView() {
  return mount(KnowledgeView, { global: { plugins: [ElementPlus] } })
}

describe('KnowledgeView 文档详情', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.listKnowledge.mockResolvedValue({
      items: [{ doc_id: 'd1', url: 'https://demo.gzhu.edu.cn/demo/01.htm', title: '新生报到通知', topics: [], status: 'active' }],
      total: 1,
    })
    mocks.getKnowledgeDetail.mockResolvedValue({
      doc_id: 'd1', url: 'https://demo.gzhu.edu.cn/demo/01.htm', title: '新生报到通知', content: '正文内容', topics: [], status: 'active',
    })
  })

  it('标题不再跳转到虚构的 demo 外部 URL', async () => {
    const wrapper = mountView()
    await flushPromises()
    expect(wrapper.find('a[href^="https://demo"]').exists()).toBe(false)
  })

  it('点击标题打开详情并拉取正文', async () => {
    const wrapper = mountView()
    await flushPromises()
    const titleBtn = wrapper.findAll('button').find((b) => b.text().includes('新生报到通知'))
    expect(titleBtn).toBeTruthy()
    await titleBtn.trigger('click')
    await flushPromises()
    expect(mocks.getKnowledgeDetail).toHaveBeenCalledWith('d1')
  })
})
