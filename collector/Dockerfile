FROM python:3.11-slim
WORKDIR /app
COPY pyproject.toml ./
COPY shared ./shared
COPY collector ./collector
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple fastapi "uvicorn[standard]" httpx selectolax trafilatura apscheduler motor pymilvus minio openai pydantic python-dotenv simhash
ENV EMBED_SERVICE_URL=http://model-server:8001
EXPOSE 8002
CMD ["uvicorn", "collector.main:app", "--host", "0.0.0.0", "--port", "8002"]
