# 采集页数控制器设计（多页采集 + 通用翻页接口）

> 状态：已确认（brainstorming 澄清完成）。本 spec 是「采集页数控制器」子功能的设计真相，实现前必读。
> 关联：spec `2026-08-18-school-knowledge-hub-design.md`（主 spec）、ADR-011（模型分工）、AGENTS.md（TDD/派活纪律）。

## 1. 背景与目标

当前一次采集只抓 `list_url` 指定的列表页**当前一页**（`engine.fetch_source` 不翻页）。实测 gzhu 通知公告共 85 条 9 页、gznews 头条关注共 10399 条 694 页——单页只采 10~15 条，远小于站点总量，用户补充知识时「每次只能采一页」不便。

本子功能补齐**采集程度控制器**：采集源可配置「采集页数」档位，默认 1 页（现状），可调高采集多页直至「全部」（内部封顶防爬爆）。核心原则：**翻页能力抽象为站点适配器的通用接口，引擎/档位/去重/入库全站点通用**；接入范围主要 gzhu 系网站，后续新增 gzhu 栏目/站点成本极低。

## 2. 需求（已确认澄清结果）

1. **档位单位**：按**页数**（非条数）。
2. **档位**：`1 页（默认）/ 3 页 / 5 页 / 10 页 / 全部`。
3. **「全部」档**：提供，但内部封顶 `MAX_PAGES_CAP = 50` 页（防 gznews 694 页爬爆 + WAF 封）；封顶在任务结果中记录提示。
4. **通用性**：翻页抽象为适配器通用接口，引擎/档位/`_seen` 去重/`doc_id` 幂等入库全站点通用；gzhu/gznews 的翻页实现下沉到「gzhu CMS 共享层」，不污染通用基类。
5. **新增站点**：继承 `GUZhuCMSAdapter` 写薄适配器（主要 `site`/`column` 差异）+ 注册 `ADAPTERS`，引擎/档位/前端 UI 零改动。
6. **交付范围**：后端 + 前端 + 测试 + 容器 rebuild 真跑验证（一次做完）。

## 3. 探索结论（分页格式实测）

| 源 | list_url | 总量 | 页数 | 每页 | 分页机制 |
|----|----------|------|------|------|---------|
| gzhu 通知公告 | `https://www.gzhu.edu.cn/z__l/tzgg.htm` | 85 条 | 9 页 | 10 条 | 底部「下页」链接 `tzgg/8.htm` |
| gznews 头条关注 | `https://news.gzhu.edu.cn/ttgd.htm` | 10399 条 | 694 页 | 15 条 | 底部「下页」链接 `ttgd/693.htm` |

- 两站同一套 gzhu CMS：列表页底部有「首页/上页/下页/尾页」，下页形如 `<a href="tzgg/8.htm" class="Next">下页</a>`；末页「下页」变为不可点 `<span class="NextDisabled">下页</span>`。
- 分页 href 是**相对路径**（如 `tzgg/8.htm`），须用 `urllib.parse.urljoin(base_url, href)` 拼绝对地址（不能用 gzhu 的 `_abs_url` override——它是为 `/info/xxx` 根路径文章链接设计的域名根拼接）。

## 4. 数据模型（SourceConfig 变更）

`collector/sources.py` 的 `SourceConfig` 加字段：

```python
max_pages: int = 1   # 1/3/5/10/0；0 = 「全部」（内部封顶 50 页）
```

- `from_dict` 缺省 `d.get("max_pages", 1)`（存量采集源无此字段向后兼容）。
- `collector/api/sources.py` 的 `create_source` 加 `max_pages=payload.get("max_pages", 1)`。

## 5. 后端设计

### 5.1 适配器分层（通用性核心）

```
SiteAdapter（通用基类，collector/crawler/base.py）
  └─ next_page_url(html, base_url) -> str | None   默认返回 None（= 不翻页），不写任何站点选择器
      └─ GUZhuCMSAdapter(SiteAdapter)（新增 collector/crawler/gzhu_cms.py）
           └─ next_page_url 实现：解析 a.Next 链接 + urljoin 拼绝对地址；末页（无 a.Next）返回 None
                ├─ GUZhuAdapter（gzhu.py 继承，保留 _abs_url/栏目/选择器差异）
                └─ GUNewsAdapter（gznews.py 继承，同上）
```

### 5.2 引擎翻页循环（`collector/crawler/engine.py`）

`fetch_source` 加 `max_pages` 参数，`MAX_PAGES_CAP = 50` 常量。循环：

```
page = 0; current_url = list_url
effective_max = max_pages if max_pages > 0 else MAX_PAGES_CAP
while True:
    抓 current_url → adapter.parse_list → 逐条抓详情（沿用 _seen URL/内容哈希去重，跨页生效）
    page += 1
    if page >= effective_max: break
    next_url = adapter.next_page_url(html, current_url)
    if next_url is None: break
    current_url = next_url
```

达到 `MAX_PAGES_CAP` 仍存在下一页时，在返回结果标记 `page_capped: true`（供任务记录提示）。

### 5.3 任务编排（`collector/tasks.py`）

`run_collection_task` 把 `source.max_pages` 透传给 `fetch_source`；`page_capped` 记入 `task_runs.failures` 或返回结果的提示字段。

## 6. 前端设计

- `frontend/src/views/admin/SourcesView.vue` 采集源表单加「采集页数」下拉：`1 页（默认）/ 3 页 / 5 页 / 10 页 / 全部`，映射值 `1/3/5/10/0`。
- `frontend/src/api/admin.js` 的 `createSource` payload 带 `max_pages`（无其他契约变化）。
- 列表展示可附加显示当前 `max_pages`（可选，非强制）。

## 7. 测试

- **后端**（pytest）：
  - `next_page_url`：有下页返回绝对 URL；末页（NextDisabled）返回 None；基类默认返回 None。
  - 引擎多页翻页：mock 分页站点（两页），`max_pages=2` 采到两页且 `_seen` 去重跨页生效；`max_pages=1` 只采一页；`max_pages=0` 到末页停。
  - `MAX_PAGES_CAP` 封顶：mock 超 50 页站点，`max_pages=0` 在 50 页停且标记 `page_capped`。
  - `SourceConfig.from_dict` 缺省 max_pages=1（向后兼容）；`create_source` 透传 max_pages。
- **前端**（vitest）：档位下拉渲染 5 档、选择后保存 payload 含 max_pages、默认选 1。

## 8. 范围外（YAGNI，一律不做）

按条数档位、配置化翻页规则（管理端填 URL 模板/CSS 选择器）、WAF 反爬增强、采集速率/并发调节、翻页去重策略改动、column 字段配置化（本期仍由适配器写死）、第三方非 gzhu 站点适配。

## 9. 验收标准

1. 后端全量 pytest 通过（含新增用例）；前端 vitest + build 通过。
2. 真跑（容器 rebuild collector + frontend 后）：建一个 `max_pages=3` 的 gzhu 源 → 采集 → 文档数 > 单页（≈ 3 页条数）且无重复 doc_id；`max_pages=1` 源仍只采一页；存量源（无 max_pages）行为不变。
3. 多页采集下同 URL 覆盖不重复（`doc_id` 幂等先删后插）。
