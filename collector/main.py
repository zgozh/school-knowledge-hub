"""采集服务入口：FastAPI + 调度器生命周期。"""
from contextlib import asynccontextmanager

from fastapi import FastAPI

from collector.api import knowledge as knowledge_api
from collector.api import manual as manual_api
from collector.api import sources as sources_api
from collector.api import tasks as tasks_api
from collector.scheduler import start_scheduler, stop_scheduler
from shared.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    await start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title="校务中台·采集服务", lifespan=lifespan)
app.include_router(sources_api.router)
app.include_router(tasks_api.router)
app.include_router(knowledge_api.router)
app.include_router(manual_api.router)


@app.get("/api/health")
async def health():
    return {"status": "ok"}
