FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PYTHONUTF8=1 PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/.cache/huggingface TORCH_HOME=/app/.cache/torch \
    RERANKER_DEVICE=cpu RERANKER_FP16=false RERANKER_OFFLINE=false \
    CLINKRAG_CONFIG_PATH=/data/private/config.local.yaml \
    CLINKRAG_RUNS_ROOT=/data/runs \
    CLINKRAG_PUBLIC_ORIGIN=https://clinkrag.hifuu.space

RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates libgomp1 \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements-server.txt ./
RUN python -m pip install torch==2.8.0 --index-url https://download.pytorch.org/whl/cpu \
    && python -m pip install -r requirements-server.txt
COPY . .
EXPOSE 8765
CMD ["python", "debug_ui/server.py", "--host", "0.0.0.0", "--port", "8765"]
