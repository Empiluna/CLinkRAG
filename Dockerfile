FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 PYTHONUTF8=1 PIP_NO_CACHE_DIR=1 \
    HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1 \
    RERANKER_DEVICE=cpu RERANKER_FP16=false RERANKER_OFFLINE=true \
    RERANKER_MODEL=/opt/models/bge-reranker-v2-m3 \
    CLINKRAG_PUBLIC_ORIGIN=https://clinkrag.hifuu.space \
    CLINKRAG_RUNS_ROOT=/mnt/r2/web-runs \
    CLINKRAG_CONFIG_PATH=/mnt/r2/config.local.yaml

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl fuse3 && rm -rf /var/lib/apt/lists/*

ARG TIGRISFS_VERSION=1.2.1
RUN curl -fL "https://github.com/tigrisdata/tigrisfs/releases/download/v${TIGRISFS_VERSION}/tigrisfs_${TIGRISFS_VERSION}_linux_amd64.tar.gz" \
    -o /tmp/tigrisfs.tar.gz && tar -xzf /tmp/tigrisfs.tar.gz -C /usr/local/bin/ \
    && rm /tmp/tigrisfs.tar.gz

WORKDIR /app
COPY requirements-cloudflare.txt ./
RUN python -m pip install --upgrade pip && \
    python -m pip install torch==2.8.0 --index-url https://download.pytorch.org/whl/cpu && \
    python -m pip install -r requirements-cloudflare.txt && \
    HF_HUB_OFFLINE=0 python -c "from huggingface_hub import snapshot_download; snapshot_download('BAAI/bge-reranker-v2-m3', local_dir='/opt/models/bge-reranker-v2-m3')"

COPY . .
RUN chmod +x /app/deploy/cloudflare/start.sh
EXPOSE 8080
CMD ["/app/deploy/cloudflare/start.sh"]
