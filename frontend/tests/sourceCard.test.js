// @vitest-environment jsdom
import { describe, it, expect } from 'vitest'
import { mount } from '@vue/test-utils'
import ElementPlus from 'element-plus'
import SourceCard from '../src/views/chat/components/SourceCard.vue'

function mountCard(source) {
  return mount(SourceCard, {
    props: { source },
    global: { plugins: [ElementPlus] },
  })
}

describe('SourceCard', () => {
  it('真实 URL 渲染可点击链接', () => {
    const wrapper = mountCard({
      url: 'https://www.gzhu.edu.cn/info/1.htm', title: '通知', category: '教务',
      publish_date: '2026-08-10', expired: false,
    })
    const link = wrapper.find('a.source-title')
    expect(link.exists()).toBe(true)
    expect(link.attributes('href')).toBe('https://www.gzhu.edu.cn/info/1.htm')
    expect(wrapper.text()).not.toContain('模拟数据')
  })

  it('demo URL 不渲染链接，显示模拟数据标识', () => {
    const wrapper = mountCard({
      url: 'https://demo.gzhu.edu.cn/demo/01.htm', title: '演示', category: '教务',
      publish_date: '2026-08-10', expired: false,
    })
    expect(wrapper.find('a.source-title').exists()).toBe(false)
    expect(wrapper.text()).toContain('演示')
    expect(wrapper.text()).toContain('模拟数据')
  })

  it('manual:// URL 不渲染链接', () => {
    const wrapper = mountCard({
      url: 'manual://abc123', title: '手工', category: '教务',
      publish_date: '', expired: false,
    })
    expect(wrapper.find('a.source-title').exists()).toBe(false)
    expect(wrapper.text()).toContain('模拟数据')
  })

  it('真实 URL 仍显示过期标识', () => {
    const wrapper = mountCard({
      url: 'https://www.gzhu.edu.cn/info/2.htm', title: '通知', category: '教务',
      publish_date: '2026-08-01', expired: true,
    })
    expect(wrapper.find('a.source-title').exists()).toBe(true)
    expect(wrapper.text()).toContain('可能已过期')
  })
})
