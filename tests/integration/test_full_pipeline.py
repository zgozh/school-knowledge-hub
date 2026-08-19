# tests/integration/test_full_pipeline.py
"""全链路集成测试（真存储真跑）：mock 站点 → 采集 → 解析打标 → 三写入库 → 混合检索 → 问答来源。

前置：Milvus/Mongo/MinIO 在线 + model_server:8001 在线；LLM 问答段无 DEEPSEEK_API_KEY 时跳过。
运行：uv run pytest tests/integration -v
"""
import httpx
import pytest

from collector import tasks as tasks_mod
from collector.crawler.engine import CrawlEngine
from collector.ingest.writer import doc_id_of
from collector.sources import SourceConfig
from qa_api.retriever.hybrid import hybrid_search
from shared.clients import get_milvus, get_minio, get_mongo
from shared.config import settings

pytestmark = pytest.mark.integration

COLLECTION = "school_docs_it"
SOURCE_ID = "it-src"
PREFIX = "https://demo.it/"

# 5 篇 mock 站点文章：标题含分类/专题关键词（D2 规则兜底出专题，不依赖 LLM）
DETAILS = {
    "https://demo.it/info/1.htm": ("关于新生入学宿舍申请的通知", "2026-08-10",
                                   "新生入学宿舍申请流程：学生登录公寓系统提交申请，经辅导员审核、公寓管理中心审批后安排入住。新生报到期间可现场办理。"),
    "https://demo.it/info/2.htm": ("学生转专业申请办理指南", "2026-08-08",
                                   "学生转专业申请办理流程：每学年第二学期开学初提交申请，经转入学院考核、教务处审批后公示，结果在教务系统公布。"),
    "https://demo.it/info/3.htm": ("关于2026年度校级科研项目申报的通知", "2026-08-04",
                                   "2026年度校级科研项目申报现已启动，项目类别包括重点项目、一般项目与青年项目，申请人须于9月30日前通过科研管理系统提交申报书。"),
    "https://demo.it/info/4.htm": ("校园卡补办办理须知", "2026-08-06",
                                   "校园卡遗失后请及时挂失并补办。补办流程：登录校园卡服务大厅挂失，持身份证到卡务中心缴费补卡，补卡后余额自动转入新卡。"),
    "https://demo.it/info/5.htm": ("2026届毕业生秋季校园招聘会安排通知", "2026-08-13",
                                   "学校定于9月20日举办2026届毕业生秋季校园招聘会，参会企业200余家。毕业生请提前登录就业信息网完善简历，凭学生证入场。"),
}


def mock_site_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/list.htm":
        items = "".join(
            f'<li><a href="/info/{i}.htm" title="{title}"><span>{date}</span></a></li>'
            for i, (url, (title, date, _)) in enumerate(DETAILS.items(), 1))
        return httpx.Response(200, text=f"<html><body><ul>{items}</ul></body></html>")
    for url, (title, date, content) in DETAILS.items():
        if request.url.path in url:
            return httpx.Response(200, text=(
                f"<html><head><title>{title}</title></head><body><h1>{title}</h1>"
                f"<p class='date'>发布时间：{date}</p><div class='content'>{content}</div></body></html>"))
    return httpx.Response(404, text="not found")


def make_source() -> SourceConfig:
    return SourceConfig(id=SOURCE_ID, name="集成测试源", list_url=f"{PREFIX}list.htm",
                        adapter="gzhu", enabled=True, interval_minutes=60)


def make_engine() -> CrawlEngine:
    return CrawlEngine(http_client=httpx.AsyncClient(transport=httpx.MockTransport(mock_site_handler)))


@pytest.fixture(autouse=True)
async def isolated_storage(monkeypatch):
    # 每个测试跑在独立的函数级事件循环里（pytest-asyncio），而 get_mongo 是进程级 lru_cache 单例：
    # 跨循环复用同一 motor 客户端在 Windows Proactor 下会报 "Event loop is closed"。清理缓存，
    # 让每个测试在自己的循环内新建客户端（生产单进程单循环不受影响）。
    get_mongo.cache_clear()
    monkeypatch.setattr(settings, "milvus_collection", COLLECTION)
    milvus = get_milvus()
    if milvus.has_collection(COLLECTION):
        milvus.drop_collection(COLLECTION)
    yield
    # 清理：Milvus 集合 / Mongo 测试文档与任务 / MinIO 测试快照
    if milvus.has_collection(COLLECTION):
        milvus.drop_collection(COLLECTION)
    db = get_mongo()
    await db["documents"].delete_many({"url": {"$regex": "^https://demo.it/"}})
    await db["task_runs"].delete_many({"source_id": SOURCE_ID})
    try:
        keys = [f"snapshots/{doc_id_of(u)}.html" for u in DETAILS]
        list(get_minio().remove_objects(settings.minio_bucket, keys))
    except Exception:
        pass  # 桶不存在或快照缺省（降级路径）时忽略


async def test_full_pipeline_collect_retrieve_answer(monkeypatch):
    """mock 站点 5 篇 → 真实采集入库 → 真实混合检索 → 来源引用 → (有 key 时)真实 LLM 问答。"""
    monkeypatch.setattr(tasks_mod, "CrawlEngine", lambda: make_engine())
    result = await tasks_mod.run_collection_task(make_source())
    assert result["status"] == "success" and result["succeeded"] == len(DETAILS)

    db = get_mongo()
    docs = [d async for d in db["documents"].find({"url": {"$regex": "^https://demo.it/"}})]
    assert len(docs) == len(DETAILS)
    assert all(d["topics"] for d in docs)  # D2 规则兜底：专题非空

    chunks = await hybrid_search("新生宿舍怎么申请", topics=["新生入学"], top_k=3)
    assert chunks
    doc = await db["documents"].find_one({"doc_id": chunks[0].doc_id})
    assert doc and doc["url"].startswith(PREFIX)  # 来源引用元数据可达

    if settings.deepseek_api_key:
        from qa_api.generator.llm import stream_answer
        from qa_api.generator.prompts import build_context

        answer = "".join([d async for d in stream_answer("新生宿舍怎么申请？", build_context(chunks))])
        assert answer
    else:
        pytest.skip("DEEPSEEK_API_KEY 未设置，跳过真实 LLM 问答段（检索/来源段已验证）")


async def test_second_run_is_idempotent(monkeypatch):
    """同一采集源跑两遍：Mongo 文档数与 Milvus 行数均不重复（幂等铁律）。"""
    async def run_once():
        monkeypatch.setattr(tasks_mod, "CrawlEngine", lambda: make_engine())
        return await tasks_mod.run_collection_task(make_source())

    r1, r2 = await run_once(), await run_once()
    assert r1["status"] == "success" and r2["status"] == "success"

    db = get_mongo()
    docs = [d async for d in db["documents"].find({"url": {"$regex": "^https://demo.it/"}})]
    assert len(docs) == len(DETAILS)
    rows = get_milvus().query(COLLECTION, filter="", output_fields=["id"], limit=1000)
    assert len(rows) == len(DETAILS)  # 每篇 1 个 chunk，两遍后仍 5 行
