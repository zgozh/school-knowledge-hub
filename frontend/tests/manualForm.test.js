// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus from 'element-plus'

const mocks = vi.hoisted(() => ({
  listKnowledge: vi.fn(),
  getKnowledgeDetail: vi.fn(),
  setDocStatus: vi.fn(),
  expiryCheck: vi.fn(),
  createDocument: vi.fn(),
  updateDocument: vi.fn(),
  removeDocument: vi.fn(),
  parseFile: vi.fn(),
}))

vi.mock('../src/api/admin', () => ({ adminApi: mocks }))

import KnowledgeView from '../src/views/admin/KnowledgeView.vue'

function mountView() {
  return mount(KnowledgeView, { global: { plugins: [ElementPlus] }, attachTo: document.body })
}

function setNativeInput(el, value) {
  el.value = value
  el.dispatchEvent(new Event('input', { bubbles: true }))
}

describe('KnowledgeView 人工数据入库', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.listKnowledge.mockResolvedValue({ items: [], total: 0 })
    mocks.createDocument.mockResolvedValue({ doc_id: 'm1' })
  })

  afterEach(() => {
    document.body.innerHTML = ''
  })

  it('页头有「新增知识」按钮，点击打开表单', async () => {
    const wrapper = mountView()
    await flushPromises()
    const btn = wrapper.findAll('button').find((b) => b.text().includes('新增知识'))
    expect(btn).toBeTruthy()
    await btn.trigger('click')
    await flushPromises()
    expect(document.body.textContent).toContain('正文来源')
  })

  it('填表提交调用 createDocument 且标题正文正确', async () => {
    const wrapper = mountView()
    await flushPromises()
    await wrapper.findAll('button').find((b) => b.text().includes('新增知识')).trigger('click')
    await flushPromises()
    const titleInput = document.body.querySelector('input[placeholder="文档标题"]')
    setNativeInput(titleInput, '标题X')
    const textarea = document.body.querySelector('textarea')
    setNativeInput(textarea, '正文Y')
    await flushPromises()
    const saveBtn = Array.from(document.body.querySelectorAll('button')).find((b) => b.textContent.includes('保存'))
    saveBtn.click()
    await flushPromises()
    expect(mocks.createDocument).toHaveBeenCalled()
    const payload = mocks.createDocument.mock.calls[0][0]
    expect(payload.title).toBe('标题X')
    expect(payload.content).toBe('正文Y')
  })
})
