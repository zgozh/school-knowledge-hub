/** 问答端 API（qa_api 服务，经 vite proxy 同源转发）。 */
import { request } from './request'
import { sseFetch } from './sseFetch'

/** 发起一次问答（SSE 流式）。callbacks 见 sseFetch。 */
export function askChat(query, topic, conversationId, callbacks) {
  return sseFetch('/qa-api/api/chat',
    { query, topic, conversation_id: conversationId ?? null }, callbacks)
}

/** 会话列表。 */
export function listConversations() {
  return request('/qa-api/api/conversations')
}

/** 会话详情（含 messages 全量）。 */
export function getConversation(id) {
  return request(`/qa-api/api/conversations/${id}`)
}

/** 删除会话。 */
export function deleteConversation(id) {
  return request(`/qa-api/api/conversations/${id}`, { method: 'DELETE' })
}
