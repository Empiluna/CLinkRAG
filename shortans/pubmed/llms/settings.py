"""Read legacy config, private project config, then environment variables."""
import os
from pathlib import Path
import yaml

def load_settings():
    branch = Path(__file__).resolve().parents[1]
    settings = {}
    legacy = branch / 'config.yaml'
    if legacy.exists():
        settings.update(yaml.safe_load(legacy.read_text(encoding='utf-8')) or {})
    for parent in (branch, *branch.parents):
        if (parent / 'requirements-windows.txt').exists():
            local = parent / 'config.local.yaml'
            if local.exists():
                settings.update(yaml.safe_load(local.read_text(encoding='utf-8')) or {})
            os.environ.setdefault('HF_HOME', str(parent / '.cache' / 'huggingface'))
            os.environ.setdefault('TORCH_HOME', str(parent / '.cache' / 'torch'))
            break
    for key in ('MODEL_NAME', 'OPENAI_API_KEY', 'OPENAI_BASE_URL',
                'DEEPSEEK_API_KEY', 'DEEPSEEK_BASE_URL', 'DEEPSEEK_THINKING',
                'S2_API_KEY', 'REQUEST_TIMEOUT', 'MAX_RETRIES', 'RERANKER_DEVICE'):
        if os.environ.get(key):
            settings[key] = os.environ[key]
    if os.environ.get('SEMANTIC_SCHOLAR_API_KEY') and not settings.get('S2_API_KEY'):
        settings['S2_API_KEY'] = os.environ['SEMANTIC_SCHOLAR_API_KEY']
    settings.pop('MODEL_PROFILES', None)
    return settings
