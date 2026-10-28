"""OpenAI-compatible transport, with bounded SDK retries and explicit errors."""
import numpy as np
from openai import OpenAI
from .base import LanguageModel
from .settings import load_settings

class chatgpt(LanguageModel):
    def __init__(self, model='gpt-4o', embedding_model='text-embedding-ada-002',
                 api_key=None, base_url=None):
        super().__init__(model)
        self.settings = load_settings()
        key = api_key or self.settings.get('OPENAI_API_KEY')
        if not key or str(key).startswith('your-'):
            raise ValueError('Missing API key. Fill config.local.yaml in the project root.')
        self.client = OpenAI(
            api_key=key,
            base_url=base_url or self.settings.get('OPENAI_BASE_URL') or 'https://api.openai.com/v1',
            timeout=float(self.settings.get('REQUEST_TIMEOUT', 90)),
            max_retries=int(self.settings.get('MAX_RETRIES', 2)),
        )
        self.embedding_model = embedding_model

    def chat(self, messages, system_msg=None, temperature=0.7, max_tokens=1000,
             top_p=0.95, frequency_penalty=0.0, presence_penalty=0.0,
             json_mode=False):
        system_msg = system_msg or 'You are a helpful assistant for scientific literature review.'
        options = {}
        if json_mode:
            system_msg += '\nReturn a valid JSON object only.'
            options['response_format'] = {'type': 'json_object'}
        if 'deepseek' in self.model.lower():
            options['extra_body'] = {'thinking': {'type': self.settings.get('DEEPSEEK_THINKING', 'disabled')}}
        response = self.client.chat.completions.create(
            model=self.model,
            messages=[{'role': 'system', 'content': system_msg},
                      {'role': 'user', 'content': messages}],
            temperature=temperature, max_tokens=max_tokens, top_p=top_p,
            frequency_penalty=frequency_penalty, presence_penalty=presence_penalty,
            **options,
        )
        choice = response.choices[0]
        content = choice.message.content
        if not content or not content.strip():
            raise RuntimeError('Empty model response; check model settings and token limit.')
        if json_mode and choice.finish_reason == 'length':
            raise RuntimeError('Truncated JSON response; increase the token limit.')
        return content

    def embed(self, query, **kwargs):
        response = self.client.embeddings.create(input=query, model=self.embedding_model, **kwargs)
        result = np.array([item.embedding for item in response.data])
        return result[0] if isinstance(query, str) else result
