# 校务知识中台 · 前端（双端）

面向校务管理的 AI 自动数据采集与知识管理中台的前端：**问答端**（`/`）与**管理端**（`/admin`）。

技术栈：Vue 3 + Vite + Element Plus + echarts + markstream-vue + vue-router。

## 启动

```bash
pnpm install    # 安装依赖
pnpm dev        # 开发服务器（默认 http://localhost:5173）
pnpm build      # 生产构建（输出 dist/）
pnpm vitest run # 单元测试（sseFetch 解析器）
```

## 双端入口

| 端 | 路由 | 功能 |
|----|------|------|
| 问答端 | `/` | 校务智能问答：专题域筛选、SSE 流式回答、来源引用卡片、示例问题 |
| 管理端 | `/admin/sources` | 采集源管理（增删/立即采集） |
| 管理端 | `/admin/tasks` | 采集任务监控（状态/失败详情/30s 自动刷新） |
| 管理端 | `/admin/knowledge` | 知识库管理（筛选/分页/上下架/到期检测） |
| 管理端 | `/admin/stats` | 资产全景（指标卡/分布图表/热门问题） |

## 后端对接（dev 代理）

开发环境通过 Vite proxy 同源转发，无需 CORS 配置：

| 前端路径前缀 | 转发目标 |
|--------------|----------|
| `/admin-api/*` | `http://localhost:8002`（collector 采集服务） |
| `/qa-api/*` | `http://localhost:8003`（qa_api 问答服务） |

启动后端：`uv run uvicorn collector.main:app --port 8002`、`uv run uvicorn qa_api.main:app --port 8003`（在项目根目录执行）。

## SSE 说明

问答接口为 POST + `text/event-stream`（浏览器 EventSource 不支持 POST），由 `src/api/sseFetch.js` 用 `fetch + ReadableStream` 手动解析，事件：`chunk` / `sources` / `done` / `empty` / `error`。单测见 `tests/sseFetch.test.js`。
