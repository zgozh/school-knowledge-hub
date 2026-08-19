/** 问答端 API（qa_api 服务，经 vite proxy 同源转发）。 */
import { sseFetch } from './sseFetch'

/** 发起一次问答（SSE 流式）。callbacks 见 sseFetch。 */
export function askChat(query, topic, history, callbacks) {
  return sseFetch('/qa-api/api/chat', { query, topic, history }, callbacks)
}
