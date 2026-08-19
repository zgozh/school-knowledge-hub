/**
 * POST + SSE 解析器：fetch + ReadableStream 手动解析 text/event-stream。
 * callbacks: { onChunk(delta), onSources(sources), onDone(info), onEmpty(message), onError(message) }
 * 兜底：空流（无任何事件）→ onEmpty；非 2xx → onError；网络异常 → onError。
 */
export async function sseFetch(url, body, callbacks) {
  let resp
  try {
    resp = await fetch(url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    })
  } catch (e) {
    callbacks.onError?.(`网络请求失败：${e.message}`)
    return
  }
  if (!resp.ok) {
    callbacks.onError?.(`服务异常（HTTP ${resp.status}），请稍后重试`)
    return
  }

  const reader = resp.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let receivedAny = false

  const dispatch = (block) => {
    if (!block.trim()) return
    receivedAny = true
    parseBlock(block, callbacks)
  }

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    buffer += decoder.decode(value, { stream: true })
    let idx
    while ((idx = buffer.indexOf('\n\n')) !== -1) {
      const block = buffer.slice(0, idx)
      buffer = buffer.slice(idx + 2)
      dispatch(block)
    }
  }
  if (buffer.trim()) dispatch(buffer)
  if (!receivedAny) {
    callbacks.onEmpty?.('服务暂未返回任何内容，请稍后重试')
  }
}

/** 解析单个 SSE 事件块（event: / data: 行），导出供单测。 */
export function parseBlock(block, callbacks) {
  let event = 'message'
  const dataLines = []
  for (const line of block.split('\n')) {
    if (line.startsWith('event:')) event = line.slice(6).trim()
    else if (line.startsWith('data:')) dataLines.push(line.slice(5).trim())
  }
  if (!dataLines.length) return
  let payload
  try {
    payload = JSON.parse(dataLines.join('\n'))
  } catch {
    return
  }
  switch (event) {
    case 'chunk':
      callbacks.onChunk?.(payload.delta ?? '')
      break
    case 'sources':
      callbacks.onSources?.(payload.sources ?? [])
      break
    case 'done':
      callbacks.onDone?.(payload)
      break
    case 'empty':
      callbacks.onEmpty?.(payload.message ?? '')
      break
    case 'error':
      callbacks.onError?.(payload.message ?? '服务异常')
      break
  }
}
