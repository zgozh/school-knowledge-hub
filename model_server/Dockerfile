FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml ./
COPY shared ./shared
COPY model_server ./model_server
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple fastapi "uvicorn[standard]" FlagEmbedding pydantic python-dotenv
ENV BGE_M3_PATH=/models/bge-m3
ENV RERANKER_PATH=/models/bge-reranker-large
EXPOSE 8001
CMD ["uvicorn", "model_server.main:app", "--host", "0.0.0.0", "--port", "8001"]
