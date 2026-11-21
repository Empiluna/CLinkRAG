from .base import LanguageModel
from .settings import load_settings, provider


def __getattr__(name):
    """Import provider SDKs only when a research run needs them."""
    if name == 'chatgpt':
        from .openai_model import chatgpt
        return chatgpt
    if name == 'DeepSeek':
        from .deepseek import DeepSeek
        return DeepSeek
    if name == 'Claude':
        from .anthropic_model import Claude
        return Claude
    raise AttributeError(name)

MODEL_DICT = {
    "gpt4o": "gpt-4o",
    "deepseek-r1": "deepseek-reasoner",
    "deepseek-v3": "deepseek-chat",
}


def get_model(model_name: str, **kwargs) -> LanguageModel:
    if model_name == 'configured':
        model_name = load_settings().get('MODEL_NAME') or 'deepseek-flash'
    if model_name in MODEL_DICT.keys():
        model_name = MODEL_DICT[model_name]

    settings = load_settings()
    selected = provider(settings, model_name)
    if selected == 'anthropic':
        from . import Claude
        return Claude(model=model_name, **kwargs)
    if selected == 'qwen':
        from . import chatgpt
        if not settings.get('QWEN_API_KEY'):
            raise ValueError('请在设置中填写通义千问 / 百炼 API Key。')
        return chatgpt(model=model_name, api_key=settings['QWEN_API_KEY'],
                       base_url=settings.get('QWEN_BASE_URL') or 'https://dashscope.aliyuncs.com/compatible-mode/v1', **kwargs)
    if selected == 'deepseek':
        from . import DeepSeek
        return DeepSeek(model=model_name, **kwargs)
    else:
        from . import chatgpt
        return chatgpt(model=model_name, **kwargs)
