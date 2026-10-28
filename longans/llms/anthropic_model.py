"""Claude native Messages transport; shared chat contract, no OpenAI payload fields."""
import json
import re
import time
import requests
from .base import LanguageModel
from .settings import load_settings


class Claude(LanguageModel):
    def __init__(self, model='claude-sonnet-5-5', api_key=None, base_url=None):
        super().__init__(model)
        config = load_settings()
        self.api_key = api_key or config.get('ANTHROPIC_API_KEY')
        if not self.api_key:
            raise ValueError('请在设置中填写 Claude / Anthropic API Key。')
        base = (base_url or config.get('ANTHROPIC_BASE_URL') or 'https://api.anthropic.com').rstrip('/')
        self.url = base + ('/messages' if base.endswith('/v1') else '/v1/messages')
        self.timeout = float(config.get('REQUEST_TIMEOUT', 90))
        self.retries = int(config.get('MAX_RETRIES', 2))

    def chat(self, messages, system_msg=None, temperature=0.7, max_tokens=1000,
             top_p=0.95, frequency_penalty=0.0, presence_penalty=0.0, json_mode=False):
        system = system_msg or 'You are a helpful assistant for scientific literature review.'
        if json_mode:
            # Tasks use different dynamic object schemas. Validate the requested JSON object
            # locally rather than claim a fixed Anthropic JSON schema covers every task.
            system += '\nReturn exactly one valid JSON object matching the user request. No markdown fences or surrounding explanation.'
        payload = {'model': self.model, 'system': system,
                   'messages': [{'role':'user', 'content':messages}], 'max_tokens':max_tokens}
        # Recent Claude models reject custom sampling parameters. Keep native defaults.
        self.last_request_parameters = {'model':self.model, 'max_tokens':max_tokens,
                                        'protocol':'anthropic_messages', 'sampling':'native defaults',
                                        'json_mode':'prompt_and_validation' if json_mode else False}
        headers = {'x-api-key': self.api_key, 'anthropic-version':'2023-06-01', 'content-type':'application/json'}
        data = None
        for attempt in range(self.retries + 1):
            try:
                response = requests.post(self.url, json=payload, headers=headers,
                                         timeout=self.timeout, allow_redirects=False)
            except requests.RequestException:
                if attempt == self.retries:
                    raise RuntimeError('Claude 请求超时或连接失败，请检查接口地址与网络。') from None
                time.sleep(min(2 ** attempt, 8))
                continue
            status = response.status_code
            if status in (408, 409, 429) or status >= 500:
                if attempt < self.retries:
                    response.close()
                    time.sleep(min(2 ** attempt, 8))
                    continue
            if not 200 <= status < 300:
                response.close()
                hint = {401:'检查 Claude API Key。',403:'检查账号权限与服务可用区域。',
                        404:'检查模型 ID 和 Base URL。',429:'检查额度或稍后重试。'}.get(status,'检查模型与请求参数。')
                raise RuntimeError(f'Claude API HTTP {status}：{hint}')
            try:
                data = response.json()
            except ValueError:
                raise RuntimeError('Claude 接口没有返回有效 JSON 响应。') from None
            finally:
                response.close()
            break
        if not isinstance(data, dict) or not isinstance(data.get('content'), list):
            raise RuntimeError('Claude 响应结构无效，请确认服务支持 Anthropic Messages 协议。')
        self.last_usage = data.get('usage')
        self.last_finish_reason = data.get('stop_reason')
        if self.last_finish_reason == 'refusal':
            raise RuntimeError('Claude 未提供本次请求的回答，请查看问题或调整任务。')
        if json_mode and self.last_finish_reason == 'max_tokens':
            raise RuntimeError('Claude JSON 输出被截断，请提高输出长度上限。')
        content = '\n'.join(block['text'] for block in data['content']
                            if isinstance(block, dict) and block.get('type') == 'text' and isinstance(block.get('text'), str)).strip()
        if not content:
            raise RuntimeError('Claude 未返回可用文本，请检查输出长度与模型设置。')
        if json_mode:
            fenced = re.fullmatch(r'```(?:json)?\s*([\s\S]*?)\s*```', content)
            if fenced:
                content = fenced.group(1)
            try:
                result = json.loads(content)
            except ValueError:
                raise RuntimeError('Claude 未返回有效的 JSON 对象，研究步骤已停止。') from None
            if not isinstance(result, dict):
                raise RuntimeError('Claude 的 JSON 输出必须为对象。')
            return json.dumps(result, ensure_ascii=False)
        return content
