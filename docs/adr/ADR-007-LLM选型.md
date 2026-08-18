# ADR-007: LLM 选型（DeepSeek 主 + DashScope 降级）

- 日期：2026-08-18
- 状态：已接受

## 背景
问答生成需要 LLM；采集兜底提取与专题域打标也需要 LLM。用户已有 DeepSeek 与 DashScope 两个 API key。

## 决策
DeepSeek 为主 LLM（生成/兜底提取/批量打标），DashScope（通义千问）为降级备选。统一走 OpenAI 兼容接口封装，切换只改 base_url/key/model。

## 备选
- 单用 DashScope：可用但 DeepSeek 成本更低。
- 本地 LLM：无 GPU 资源，推理慢——否决。
- OpenAI/Claude：访问与费用不适合——否决。

## 后果
- 正面：降级链保证主链路永远可用（spec 第 8 节）；OpenAI 兼容封装让未来换供应商零成本。
- 硬约束关联：单机可复现（key 走 .env）；成本可控。
- 重新评估触发：若 DeepSeek 频繁限流，主备互换或引入重试队列。

## 人工资源依赖
- DeepSeek API key：已在用户环境变量（代码支持环境变量直读 + .env 写入）。
- DashScope API key：写入 .env。
- `.env` 不进 git，`.env.example` 进 git。
