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
            local = Path(os.environ.get('CLINKRAG_CONFIG_PATH', parent / 'config.local.yaml'))
            if local.exists():
                settings.update(yaml.safe_load(local.read_text(encoding='utf-8')) or {})
            os.environ.setdefault('HF_HOME', str(parent / '.cache' / 'huggingface'))
            os.environ.setdefault('TORCH_HOME', str(parent / '.cache' / 'torch'))
            break
    for key in ('MODEL_NAME', 'OPENAI_API_KEY', 'OPENAI_BASE_URL',
                'DEEPSEEK_API_KEY', 'DEEPSEEK_BASE_URL', 'DEEPSEEK_THINKING',
                'ANTHROPIC_API_KEY', 'ANTHROPIC_BASE_URL', 'QWEN_API_KEY', 'QWEN_BASE_URL',
                'S2_API_KEY', 'REQUEST_TIMEOUT', 'MAX_RETRIES', 'RERANKER_DEVICE',
                'LLM_PROVIDER', 'RERANKER_MODEL', 'RERANKER_BATCH_SIZE',
                'RERANKER_MAX_LENGTH', 'RERANKER_FP16', 'RERANKER_OFFLINE'):
        if os.environ.get(key):
            settings[key] = os.environ[key]
    if os.environ.get('SEMANTIC_SCHOLAR_API_KEY') and not settings.get('S2_API_KEY'):
        settings['S2_API_KEY'] = os.environ['SEMANTIC_SCHOLAR_API_KEY']
    # Other saved profiles contain credentials and are not runtime/trace data.
    settings.pop('MODEL_PROFILES', None)
    return settings


def provider(settings, model=None):
    value = settings.get('LLM_PROVIDER', 'auto')
    if value in ('deepseek', 'openai_compatible', 'anthropic', 'openai', 'qwen'):
        return value
    return 'deepseek' if 'deepseek' in str(model or settings.get('MODEL_NAME', '')).lower() else 'openai_compatible'


def configured_key(settings):
    if provider(settings) == 'anthropic':
        return settings.get('ANTHROPIC_API_KEY')
    if provider(settings) == 'qwen':
        return settings.get('QWEN_API_KEY')
    if provider(settings) == 'deepseek':
        return settings.get('DEEPSEEK_API_KEY') or settings.get('OPENAI_API_KEY')
    return settings.get('OPENAI_API_KEY')


def bool_setting(settings, key, default):
    value = settings.get(key, default)
    return value is True or str(value).lower() in ('true', '1', 'yes')
