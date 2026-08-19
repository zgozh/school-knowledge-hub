/** 管理端 API 函数集（collector 服务，经 vite proxy 同源转发）。 */
import { request } from './request'

export const adminApi = {
  // 采集源
  listSources: () => request('/admin-api/api/admin/sources'),
  createSource: (payload) => request('/admin-api/api/admin/sources', { method: 'POST', body: payload }),
  deleteSource: (id) => request(`/admin-api/api/admin/sources/${id}`, { method: 'DELETE' }),
  // 采集任务
  runTask: (sourceId) => request(`/admin-api/api/admin/tasks/${sourceId}/run`, { method: 'POST' }),
  listTasks: (params = {}) => {
    const q = new URLSearchParams(Object.entries(params).filter(([, v]) => v != null && v !== '')).toString()
    return request(`/admin-api/api/admin/tasks${q ? `?${q}` : ''}`)
  },
  // 知识库
  listKnowledge: (params = {}) => {
    const q = new URLSearchParams(Object.entries(params).filter(([, v]) => v != null && v !== '')).toString()
    return request(`/admin-api/api/admin/knowledge${q ? `?${q}` : ''}`)
  },
  setDocStatus: (docId, status) =>
    request(`/admin-api/api/admin/knowledge/${docId}/status`, { method: 'POST', body: { status } }),
  getKnowledgeDetail: (docId) => request(`/admin-api/api/admin/knowledge/${docId}`),
  // 统计与治理
  stats: () => request('/admin-api/api/admin/stats'),
  expiryCheck: () => request('/admin-api/api/admin/expiry-check', { method: 'POST' }),
  // 人工数据入库
  parseFile: (file) => {
    const fd = new FormData()
    fd.append('file', file)
    return request('/admin-api/api/admin/manual/parse-file', { method: 'POST', body: fd, isForm: true })
  },
  createDocument: (payload) => request('/admin-api/api/admin/manual/documents', { method: 'POST', body: payload }),
  updateDocument: (docId, payload) => request(`/admin-api/api/admin/manual/documents/${docId}`, { method: 'PUT', body: payload }),
  removeDocument: (docId) => request(`/admin-api/api/admin/manual/documents/${docId}`, { method: 'DELETE' }),
}
