/** fetch JSON 封装：非 2xx 抛出中文错误；isForm=true 时按 multipart 发送。 */
export async function request(path, { method = 'GET', body, isForm = false } = {}) {
  const resp = await fetch(path, {
    method,
    headers: body && !isForm ? { 'Content-Type': 'application/json' } : undefined,
    body: isForm ? body : body ? JSON.stringify(body) : undefined,
  })
  if (!resp.ok) {
    let msg = `请求失败（HTTP ${resp.status}）`
    try {
      const data = await resp.json()
      if (data?.detail) msg = typeof data.detail === 'string' ? data.detail : msg
      if (data?.error) msg = typeof data.error === 'string' ? data.error : msg
    } catch {
      /* 忽略非 JSON 错误体 */
    }
    throw new Error(msg)
  }
  return resp.json()
}
