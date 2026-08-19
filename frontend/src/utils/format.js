/** 展示格式化与状态映射（纯函数，供各页面共用）。 */

export function formatDate(iso) {
  if (!iso) return '-'
  return String(iso).replace('T', ' ').slice(0, 16)
}

export const STATUS_TEXT = {
  pending: '待执行',
  running: '执行中',
  success: '成功',
  partial: '部分失败',
  failed: '失败',
  active: '在用',
  archived: '已下架',
  expired: '已过期',
}

export const STATUS_TYPE = {
  pending: 'info',
  running: 'primary',
  success: 'success',
  partial: 'warning',
  failed: 'danger',
  active: 'success',
  archived: 'info',
  expired: 'warning',
}

export const CATEGORIES = ['通知公告', '办事指南', '规章制度', '新闻动态']

export const TOPICS = ['新生入学', '港澳生服务', '教务学籍', '后勤生活', '就业创业', '科研学术']

export const ADAPTERS = {
  gzhu: '广州大学主站',
  gznews: '广州大学新闻网',
}
