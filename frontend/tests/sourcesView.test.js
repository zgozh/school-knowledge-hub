// @vitest-environment jsdom
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { mount, flushPromises } from '@vue/test-utils'
import ElementPlus, { ElSelect } from 'element-plus'

const mocks = vi.hoisted(() => ({
  listSources: vi.fn(),
  createSource: vi.fn(),
  deleteSource: vi.fn(),
  runTask: vi.fn(),
}))

vi.mock('../src/api/admin', () => ({ adminApi: mocks }))

import SourcesView from '../src/views/admin/SourcesView.vue'

function mountView() {
  return mount(SourcesView, { global: { plugins: [ElementPlus] }, attachTo: document.body })
}

function setNativeInput(el, value) {
  el.value = value
  el.dispatchEvent(new Event('input', { bubbles: true }))
}

async function openCreate(wrapper) {
  const btn = Array.from(wrapper.findAll('button')).find((b) => b.text().includes('新增采集源'))
  await btn.trigger('click')
  await flushPromises()
}

/** 当前可见（aria-hidden=false）下拉里的 option 文本列表。 */
function visibleOptionTexts() {
  return Array.from(document.body.querySelectorAll('.el-popper'))
    .filter((p) => p.getAttribute('aria-hidden') === 'false')
    .flatMap((p) => Array.from(p.querySelectorAll('.el-select-dropdown__item')))
    .map((o) => o.textContent.trim())
}

describe('SourcesView 采集页数控制器', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.listSources.mockResolvedValue({ items: [] })
    mocks.createSource.mockResolvedValue({ id: 's1' })
  })
  afterEach(() => { document.body.innerHTML = '' })

  it('新增弹窗渲染「采集页数」下拉 5 档，默认 1 页', async () => {
    const wrapper = mountView()
    await flushPromises()
    await openCreate(wrapper)
    expect(document.body.textContent).toContain('采集页数')
    // 第 1 个 select = 适配器，第 2 个 = 采集页数；点开第 2 个读选项
    const selects = wrapper.findAllComponents(ElSelect)
    await selects[1].find('.el-select__wrapper').trigger('click')
    await flushPromises()
    expect(visibleOptionTexts()).toEqual(['1 页（默认）', '3 页', '5 页', '10 页', '全部'])
    expect(document.body.textContent).toContain('1 页（默认）')
  })

  it('设置 3 页后提交，createSource payload 含 max_pages=3', async () => {
    const wrapper = mountView()
    await flushPromises()
    await openCreate(wrapper)
    setNativeInput(document.body.querySelector('input[placeholder="如：广州大学教务处"]'), '测试源')
    setNativeInput(document.body.querySelector('input[placeholder="https://..."]'), 'https://www.gzhu.edu.cn/z__l/tzgg.htm')
    const selects = wrapper.findAllComponents(ElSelect)
    await selects[0].vm.$emit('update:modelValue', 'gzhu') // 适配器
    await selects[1].vm.$emit('update:modelValue', 3)       // 采集页数
    await flushPromises()
    const saveBtn = Array.from(document.body.querySelectorAll('button')).find((b) => b.textContent.includes('确定'))
    saveBtn.click()
    await flushPromises()
    expect(mocks.createSource).toHaveBeenCalled()
    expect(mocks.createSource.mock.calls[0][0].max_pages).toBe(3)
    expect(mocks.createSource.mock.calls[0][0].adapter).toBe('gzhu')
  })
})
