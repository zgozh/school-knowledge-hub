FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml ./
COPY shared ./shared
COPY qa_api ./qa_api
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple fastapi "uvicorn[standard]" sse-starlette httpx pymilvus motor minio openai pydantic python-dotenv
ENV EMBED_SERVICE_URL=http://model-server:8001
ENV RERANK_SERVICE_URL=http://model-server:8001
EXPOSE 8003
CMD ["uvicorn", "qa_api.main:app", "--host", "0.0.0.0", "--port", "8003"]
