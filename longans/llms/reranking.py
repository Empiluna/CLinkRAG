"""One configuration contract for both scientific retrieval pipelines."""
import os
from pathlib import Path
from .settings import load_settings, bool_setting


def options(device=None):
    config = load_settings()
    target = device or config.get('RERANKER_DEVICE', 'cpu')
    return dict(model=config.get('RERANKER_MODEL') or 'BAAI/bge-reranker-v2-m3',
                device=target,
                fp16=target != 'cpu' and bool_setting(config, 'RERANKER_FP16', True),
                batch_size=int(config.get('RERANKER_BATCH_SIZE', 4)),
                max_length=int(config.get('RERANKER_MAX_LENGTH', 512)),
                offline=bool_setting(config, 'RERANKER_OFFLINE', True))


def create_reranker(device=None):
    values = options(device)
    os.environ['HF_HUB_OFFLINE'] = '1' if values['offline'] else '0'
    os.environ['TRANSFORMERS_OFFLINE'] = '1' if values['offline'] else '0'
    model_path = values['model']
    if values['offline'] and not Path(model_path).is_dir():
        from huggingface_hub import snapshot_download
        model_path = snapshot_download(model_path, local_files_only=True)
    from FlagEmbedding import FlagReranker
    return FlagReranker(model_path, use_fp16=values['fp16'], devices=values['device'],
                        trust_remote_code=False)


def score_options():
    values = options()
    return dict(batch_size=values['batch_size'], max_length=values['max_length'])
