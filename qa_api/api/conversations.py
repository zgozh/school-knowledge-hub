"""会话管理 API：列表/详情/删除。"""
from fastapi import APIRouter, HTTPException

from qa_api.conversations import (
    delete_conversation as _delete,
    get_conversation as _get,
    list_conversations as _list,
)
from shared.clients import get_mongo

router = APIRouter(prefix="/api/conversations", tags=["会话"])


@router.get("")
async def list_endpoint():
    return await _list(get_mongo())


@router.get("/{conversation_id}")
async def get_endpoint(conversation_id: str):
    conv = await _get(get_mongo(), conversation_id)
    if conv is None:
        raise HTTPException(status_code=404, detail="会话不存在")
    return conv


@router.delete("/{conversation_id}")
async def delete_endpoint(conversation_id: str):
    await _delete(get_mongo(), conversation_id)
    return {"deleted": True}
