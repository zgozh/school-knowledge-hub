"""问答服务入口：FastAPI + CORS（前端 dev 跨域）。"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from qa_api.api import chat, conversations

app = FastAPI(title="校务中台·问答服务")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(chat.router)
app.include_router(conversations.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
