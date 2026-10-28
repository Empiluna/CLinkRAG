#!/bin/sh
set -eu

: "${R2_ACCOUNT_ID:?R2_ACCOUNT_ID is required}"
: "${R2_BUCKET_NAME:?R2_BUCKET_NAME is required}"
: "${AWS_ACCESS_KEY_ID:?AWS_ACCESS_KEY_ID is required}"
: "${AWS_SECRET_ACCESS_KEY:?AWS_SECRET_ACCESS_KEY is required}"

mkdir -p /mnt/r2
/usr/local/bin/tigrisfs \
  --endpoint "https://${R2_ACCOUNT_ID}.r2.cloudflarestorage.com" \
  --region auto -f "$R2_BUCKET_NAME" /mnt/r2 &
fuse_pid=$!

attempt=0
until mountpoint -q /mnt/r2; do
  if ! kill -0 "$fuse_pid" 2>/dev/null; then
    echo 'R2 filesystem process exited before mounting' >&2
    exit 1
  fi
  attempt=$((attempt + 1))
  if [ "$attempt" -ge 30 ]; then
    echo 'Timed out mounting R2' >&2
    exit 1
  fi
  sleep 1
done

mkdir -p "$CLINKRAG_RUNS_ROOT"
python - <<'PY'
import os
from pathlib import Path
import tempfile

root = Path(os.environ['CLINKRAG_RUNS_ROOT'])
with tempfile.TemporaryDirectory(prefix='.storage-check-', dir=root) as folder:
    first = Path(folder) / 'first'
    second = Path(folder) / 'second'
    first.write_text('a', encoding='utf-8')
    os.replace(first, second)
    with second.open('a', encoding='utf-8') as stream:
        stream.write('b')
    if second.read_text(encoding='utf-8') != 'ab':
        raise RuntimeError('R2 mount failed the write/rename/append check')
PY
if [ ! -e "$CLINKRAG_CONFIG_PATH" ]; then
  cat > "$CLINKRAG_CONFIG_PATH" <<'YAML'
LLM_PROVIDER: deepseek
MODEL_NAME: deepseek-flash
DEEPSEEK_BASE_URL: https://api.deepseek.com
RERANKER_DEVICE: cpu
RERANKER_MODEL: /opt/models/bge-reranker-v2-m3
RERANKER_FP16: false
RERANKER_OFFLINE: true
YAML
fi
exec python /app/debug_ui/server.py --host 0.0.0.0 --port 8080
