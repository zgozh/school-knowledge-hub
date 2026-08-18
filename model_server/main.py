"""本地模型服务：BGE-M3 双向量 + bge-reranker-large 重排。"""
from fastapi import FastAPI
from pydantic import BaseModel

from model_server.models import get_bge_m3, get_reranker
from shared.logging import get_logger

logger = get_logger("model_server")
app = FastAPI(title="校务中台·本地模型服务")


class EmbedRequest(BaseModel):
    texts: list[str]


class RerankRequest(BaseModel):
    query: str
    documents: list[str]


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/embed")
async def embed(req: EmbedRequest):
    model = get_bge_m3()
    out = model.encode(req.texts, return_dense=True, return_sparse=True)
    embeddings = [
        {"dense": list(d), "sparse": {int(k): float(v) for k, v in s.items()}}
        for d, s in zip(out["dense_vecs"], out["lexical_weights"])
    ]
    return {"embeddings": embeddings}


@app.post("/rerank")
async def rerank(req: RerankRequest):
    model = get_reranker()
    pairs = [[req.query, doc] for doc in req.documents]
    scores = model.compute_score(pairs, normalize=True)
    if isinstance(scores, float):
        scores = [scores]
    order = sorted(range(len(scores)), key=lambda i: -scores[i])
    return {"scores": [float(s) for s in scores], "order": order}
