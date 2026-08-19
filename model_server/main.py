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
        {"dense": [float(x) for x in d], "sparse": {int(k): float(v) for k, v in s.items()}}
        for d, s in zip(out["dense_vecs"], out["lexical_weights"])
    ]
    return {"embeddings": embeddings}


@app.post("/rerank")
async def rerank(req: RerankRequest):
    """手写交叉编码推理（tokenize→前向→sigmoid），绕开 FlagEmbedding 与 transformers 版本接口漂移。"""
    import torch

    model = get_reranker()
    pairs = [[req.query, doc] for doc in req.documents]
    with torch.no_grad():
        inputs = model.tokenizer(
            [p[0] for p in pairs], [p[1] for p in pairs],
            padding=True, truncation=True, max_length=512, return_tensors="pt")
        logits = model.model(**inputs, return_dict=True).logits
        scores = torch.sigmoid(logits.view(-1).float()).tolist()
    order = sorted(range(len(scores)), key=lambda i: -scores[i])
    return {"scores": scores, "order": order}
