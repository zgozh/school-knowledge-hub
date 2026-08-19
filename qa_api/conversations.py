"""会话存储/查询业务函数（依赖注入 db，供 API 与 /chat 共用）。"""
import time
import uuid


def _now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


async def list_conversations(db) -> list[dict]:
    docs = await db["conversations"].find({}).sort("updated_at", -1).to_list(None)
    return [
        {
            "conversation_id": d["conversation_id"],
            "title": d.get("title", ""),
            "updated_at": d.get("updated_at", ""),
            "message_count": len(d.get("messages", [])),
        }
        for d in docs
    ]


async def get_conversation(db, conversation_id: str) -> dict | None:
    conv = await db["conversations"].find_one({"conversation_id": conversation_id})
    if conv and "_id" in conv:
        conv["_id"] = str(conv["_id"])  # ObjectId 转 str，避免 FastAPI JSON 序列化 500
    return conv


async def delete_conversation(db, conversation_id: str) -> bool:
    await db["conversations"].delete_many({"conversation_id": conversation_id})
    return True


async def append_or_create(db, conversation_id: str | None, query: str, answer: str, sources: list) -> str:
    now = _now()
    user_msg = {"role": "user", "content": query, "created_at": now}
    assistant_msg = {"role": "assistant", "content": answer, "sources": sources, "created_at": now}
    if conversation_id:
        existing = await db["conversations"].find_one({"conversation_id": conversation_id})
        if existing:
            await db["conversations"].update_one(
                {"conversation_id": conversation_id},
                {"$push": {"messages": {"$each": [user_msg, assistant_msg]}},
                 "$set": {"updated_at": now}},
            )
            return conversation_id
    new_id = uuid.uuid4().hex[:16]
    await db["conversations"].insert_one({
        "conversation_id": new_id,
        "title": query[:20] + ("…" if len(query) > 20 else ""),
        "messages": [user_msg, assistant_msg],
        "created_at": now,
        "updated_at": now,
    })
    return new_id
