"""人工数据入库 API（录入/上传/编辑/删除）。"""
from fastapi import APIRouter, HTTPException, UploadFile

from collector import manual

router = APIRouter(prefix="/api/admin/manual", tags=["人工入库"])

MAX_FILE_BYTES = 10 * 1024 * 1024


@router.post("/parse-file")
async def parse_file(file: UploadFile):
    from collector.parser.file_parser import parse_file as do_parse

    data = await file.read()
    if len(data) > MAX_FILE_BYTES:
        raise HTTPException(status_code=400, detail="文件过大（上限 10MB）")
    try:
        return do_parse(file.filename or "未命名.txt", data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/documents")
async def create_document(payload: dict):
    if not (payload.get("title") and payload.get("content")):
        raise HTTPException(status_code=400, detail="标题与正文必填")
    return {"doc_id": await manual.create_document(payload)}


@router.put("/documents/{doc_id}")
async def update_document(doc_id: str, payload: dict):
    if not (payload.get("title") and payload.get("content")):
        raise HTTPException(status_code=400, detail="标题与正文必填")
    result = await manual.update_document(doc_id, payload)
    if result is None:
        raise HTTPException(status_code=404, detail="文档不存在")
    return {"doc_id": result}


@router.delete("/documents/{doc_id}")
async def delete_document(doc_id: str):
    await manual.delete_document(doc_id)
    return {"deleted": True}
