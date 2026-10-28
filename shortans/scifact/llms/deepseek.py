from .openai_model import chatgpt
from .settings import load_settings

class DeepSeek(chatgpt):
    def __init__(self, model='deepseek-flash', api_key=None, **kwargs):
        config = load_settings()
        key = api_key or config.get('DEEPSEEK_API_KEY') or config.get('OPENAI_API_KEY')
        if not key:
            raise ValueError('Missing DEEPSEEK_API_KEY. Fill config.local.yaml in the project root.')
        super().__init__(model=model, api_key=key,
                         base_url=config.get('DEEPSEEK_BASE_URL') or 'https://api.deepseek.com',
                         **kwargs)
