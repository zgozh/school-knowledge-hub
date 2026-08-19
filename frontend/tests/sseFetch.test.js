import { describe, it, expect, vi, afterEach } from 'vitest'
import { sseFetch } from '../src/api/sseFetch.js'

/** 把若干字符串块组装成一个 ReadableStream（模拟网络分块） */
function streamFromChunks(chunks) {
  const encoder = new TextEncoder()
  return new ReadableStream({
    start(controller) {
      for (const c of chunks) controller.enqueue(encoder.encode(c))
      controller.close()
    },
  })
}

function mockFetch(chunks, { ok = true, status = 200 } = {}) {
  return vi.fn().mockResolvedValue({ ok, status, body: streamFromChunks(chunks) })
}

function makeCallbacks() {
  return {
    onChunk: vi.fn(),
    onSources: vi.fn(),
    onDone: vi.fn(),
    onEmpty: vi.fn(),
    onError: vi.fn(),
  }
}

const realFetch = globalThis.fetch
afterEach(() => {
  globalThis.fetch = realFetch
})

describe('sseFetch', () => {
  it('按序分发 chunk / sources / done 事件', async () => {
    const sse = [
      'event: chunk\ndata: {"delta":"你好"}\n\n',
      'event: chunk\ndata: {"delta":"，世界"}\n\n',
      'event: sources\ndata: {"sources":[{"doc_id":"d1","title":"通知","url":"http://x","publish_date":"2026-08-01","category":"通知公告","expired":false}]}\n\n',
      'event: done\ndata: {"query_id":"q1","elapsed_ms":120,"answer_len":5}\n\n',
    ]
    globalThis.fetch = mockFetch(sse)
    const cb = makeCallbacks()

    await sseFetch('/qa-api/api/chat', { query: 'hi', topic: null, history: [] }, cb)

    expect(globalThis.fetch).toHaveBeenCalledWith(
      '/qa-api/api/chat',
      expect.objectContaining({ method: 'POST' }),
    )
    expect(cb.onChunk).toHaveBeenCalledTimes(2)
    expect(cb.onChunk).toHaveBeenNthCalledWith(1, '你好')
    expect(cb.onChunk).toHaveBeenNthCalledWith(2, '，世界')
    expect(cb.onSources).toHaveBeenCalledTimes(1)
    expect(cb.onSources.mock.calls[0][0]).toHaveLength(1)
    expect(cb.onSources.mock.calls[0][0][0].doc_id).toBe('d1')
    expect(cb.onDone).toHaveBeenCalledTimes(1)
    expect(cb.onDone).toHaveBeenCalledWith(
      expect.objectContaining({ query_id: 'q1', elapsed_ms: 120 }),
    )
    expect(cb.onEmpty).not.toHaveBeenCalled()
    expect(cb.onError).not.toHaveBeenCalled()
  })

  it('SSE 事件被拆到多个网络分块时仍能正确解析', async () => {
    const full =
      'event: chunk\ndata: {"delta":"完整的一句话"}\n\n' +
      'event: done\ndata: {"query_id":"q2","elapsed_ms":1,"answer_len":7}\n\n'
    const chunks = []
    for (let i = 0; i < full.length; i += 3) chunks.push(full.slice(i, i + 3))
    globalThis.fetch = mockFetch(chunks)
    const cb = makeCallbacks()

    await sseFetch('/qa-api/api/chat', {}, cb)

    expect(cb.onChunk).toHaveBeenCalledTimes(1)
    expect(cb.onChunk).toHaveBeenCalledWith('完整的一句话')
    expect(cb.onDone).toHaveBeenCalledTimes(1)
  })

  it('empty 事件触发 onEmpty 并携带 message', async () => {
    globalThis.fetch = mockFetch(['event: empty\ndata: {"message":"未找到相关校务信息"}\n\n'])
    const cb = makeCallbacks()

    await sseFetch('/qa-api/api/chat', {}, cb)

    expect(cb.onEmpty).toHaveBeenCalledTimes(1)
    expect(cb.onEmpty).toHaveBeenCalledWith('未找到相关校务信息')
    expect(cb.onError).not.toHaveBeenCalled()
  })

  it('error 事件触发 onError 并携带 message', async () => {
    globalThis.fetch = mockFetch(['event: error\ndata: {"message":"模型服务不可用"}\n\n'])
    const cb = makeCallbacks()

    await sseFetch('/qa-api/api/chat', {}, cb)

    expect(cb.onError).toHaveBeenCalledTimes(1)
    expect(cb.onError).toHaveBeenCalledWith('模型服务不可用')
  })

  it('空流（服务端未发送任何事件）兜底触发 onEmpty', async () => {
    globalThis.fetch = mockFetch([])
    const cb = makeCallbacks()

    await sseFetch('/qa-api/api/chat', {}, cb)

    expect(cb.onEmpty).toHaveBeenCalledTimes(1)
    expect(cb.onChunk).not.toHaveBeenCalled()
    expect(cb.onDone).not.toHaveBeenCalled()
    expect(cb.onError).not.toHaveBeenCalled()
  })

  it('非 2xx 响应触发 onError（含 HTTP 状态码）', async () => {
    globalThis.fetch = mockFetch([''], { ok: false, status: 500 })
    const cb = makeCallbacks()

    await sseFetch('/qa-api/api/chat', {}, cb)

    expect(cb.onError).toHaveBeenCalledTimes(1)
    expect(cb.onError.mock.calls[0][0]).toContain('500')
  })

  it('fetch 抛异常（网络错误）触发 onError', async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new Error('Failed to fetch'))
    const cb = makeCallbacks()

    await sseFetch('/qa-api/api/chat', {}, cb)

    expect(cb.onError).toHaveBeenCalledTimes(1)
  })
})
