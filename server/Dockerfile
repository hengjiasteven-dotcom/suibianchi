FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

COPY server/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY server/app ./app
COPY server/scripts ./scripts
COPY output/heat_index/app/app_heat_index.jsonl ./heat_index.jsonl

ENV SHIJI_DATA_DIR=/data \
    SHIJI_HEAT_INDEX=/app/heat_index.jsonl

VOLUME ["/data"]
EXPOSE 8000

# 对话会话存在进程内存里，固定 1 个 worker；多 worker 会把会话拆散
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]
