from .openai_model import chatgpt
from .base import LanguageModel
from .deepseek import DeepSeek
from .anthropic_model import Claude
from .settings import load_settings, provider

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
        return Claude(model=model_name, **kwargs)
    if selected == 'qwen':
        if not settings.get('QWEN_API_KEY'):
            raise ValueError('请在设置中填写通义千问 / 百炼 API Key。')
        return chatgpt(model=model_name, api_key=settings['QWEN_API_KEY'],
                       base_url=settings.get('QWEN_BASE_URL') or 'https://dashscope.aliyuncs.com/compatible-mode/v1', **kwargs)
    if selected == 'deepseek':
        return DeepSeek(model=model_name, **kwargs)
    else:
        return chatgpt(model=model_name, **kwargs)
