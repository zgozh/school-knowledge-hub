# collector/api/knowledge.py
"""知识库管理 API。"""
from fastapi import APIRouter, HTTPException

from collector import knowledge

router = APIRouter(prefix="/api/admin", tags=["知识库"])


@router.get("/knowledge")
async def list_knowledge(status: str | None = None, category: str | None = None, topic: str | None = None,
                         page: int = 1, page_size: int = 20):
    return await knowledge.query_documents(status, category, topic, page, page_size)


@router.get("/knowledge/{doc_id}")
async def get_document(doc_id: str):
    doc = await knowledge.get_document_detail(doc_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="文档不存在")
    return doc


@router.post("/knowledge/{doc_id}/status")
async def change_status(doc_id: str, payload: dict):
    return {"updated": await knowledge.set_doc_status(doc_id, payload["status"])}


@router.get("/stats")
async def stats():
    return await knowledge.asset_stats()


@router.post("/expiry-check")
async def expiry_check():
    return {"expired_count": await knowledge.check_expiry()}
