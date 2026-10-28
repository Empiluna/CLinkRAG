"""Validated, secret-safe local configuration editing. Never call a paid API here."""
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
import threading
import uuid
from urllib.parse import urlsplit
import yaml
from llms.settings import load_settings, provider, bool_setting, configured_key
from debug_ui.model_presets import PRESETS

ROOT = Path(__file__).resolve().parents[1]
DEFAULTS = {
    'LLM_PROVIDER': 'openai_compatible', 'MODEL_NAME': '',
    'OPENAI_BASE_URL': 'https://api.openai.com/v1',
    'DEEPSEEK_BASE_URL': 'https://api.deepseek.com',
    'ANTHROPIC_BASE_URL': 'https://api.anthropic.com',
    'QWEN_BASE_URL': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    'DEEPSEEK_THINKING': 'disabled', 'REQUEST_TIMEOUT': 90, 'MAX_RETRIES': 2,
    'RERANKER_MODEL': 'BAAI/bge-reranker-v2-m3', 'RERANKER_DEVICE': 'cpu',
    'RERANKER_BATCH_SIZE': 4, 'RERANKER_MAX_LENGTH': 512,
    'RERANKER_FP16': True, 'RERANKER_OFFLINE': True,
}
SECRETS = ('OPENAI_API_KEY', 'DEEPSEEK_API_KEY', 'ANTHROPIC_API_KEY', 'QWEN_API_KEY', 'S2_API_KEY')
URL_KEYS = ('OPENAI_BASE_URL', 'DEEPSEEK_BASE_URL', 'ANTHROPIC_BASE_URL', 'QWEN_BASE_URL')
MODEL_KEYS = ('LLM_PROVIDER', 'MODEL_NAME', 'REQUEST_TIMEOUT', 'MAX_RETRIES', 'DEEPSEEK_THINKING')


def service_fields(kind):
    item = next(item for item in PRESETS if item['id'] == kind)
    return item['url_key'], item['key_field']


def profile_snapshot(config, identity, name=None):
    values = public_values(config)
    url_key, _ = service_fields(values['LLM_PROVIDER'])
    return {'id': identity, 'name': name or values['MODEL_NAME'],
            'values': {key: values[key] for key in (*MODEL_KEYS, url_key)},
            'api_key': configured_key(config) or ''}


def public_values(config):
    values = {key: config[key] if config.get(key) is not None else default for key, default in DEFAULTS.items()}
    for key in (*URL_KEYS, 'RERANKER_MODEL'):
        values[key] = values[key] or DEFAULTS[key]
    values['LLM_PROVIDER'] = provider(config)
    for key in ('REQUEST_TIMEOUT', 'MAX_RETRIES', 'RERANKER_BATCH_SIZE', 'RERANKER_MAX_LENGTH'):
        values[key] = int(values[key])
    for key in ('RERANKER_FP16', 'RERANKER_OFFLINE'):
        values[key] = bool_setting(config, key, DEFAULTS[key])
    return values


def validate(values):
    if not isinstance(values, dict) or set(values) != set(DEFAULTS):
        raise ValueError('运行配置字段不完整或包含未知字段，请重新加载设置。')
    values = values.copy()
    for key in ('MODEL_NAME', 'RERANKER_MODEL'):
        val = values[key]
        if not isinstance(val, str) or not val.strip() or len(val) > 512 or any(ord(c) < 32 for c in val):
            raise ValueError(f'{key} 需要填写有效的模型 ID 或路径。')
        values[key] = val.strip()
    if values['LLM_PROVIDER'] not in {preset['id'] for preset in PRESETS}:
        raise ValueError('请选择受支持的模型接口类型。')
    if values['DEEPSEEK_THINKING'] not in ('disabled', 'enabled', 'omit'):
        raise ValueError('无效的思考模式。')
    for key in URL_KEYS:
        val = values[key]
        if not isinstance(val, str) or len(val) > 1000 or any(ord(c) < 33 for c in val):
            raise ValueError('API 地址必须是完整的 HTTP(S) 地址。')
        parsed = urlsplit(val)
        if (not parsed.hostname or parsed.scheme not in ('https', 'http') or parsed.username or
                parsed.password or parsed.query or parsed.fragment):
            raise ValueError('API 地址不能包含账号、密钥、查询参数或片段。')
        if parsed.scheme == 'http' and parsed.hostname not in ('localhost', '127.0.0.1', '::1'):
            raise ValueError('远程模型服务请使用 HTTPS；HTTP 仅用于本机服务。')
        values[key] = val.rstrip('/')
    for key, low, high in [('REQUEST_TIMEOUT', 10, 600), ('MAX_RETRIES', 0, 5),
                           ('RERANKER_BATCH_SIZE', 1, 64), ('RERANKER_MAX_LENGTH', 128, 8192)]:
        if type(values[key]) is not int or not low <= values[key] <= high:
            raise ValueError(f'{key} 必须是 {low}–{high} 的整数。')
    if not isinstance(values['RERANKER_DEVICE'], str) or not re.fullmatch(r'cpu|cuda(?::\d{1,2})?', values['RERANKER_DEVICE']):
        raise ValueError('重排设备请填写 cpu、cuda 或 cuda:0 等设备编号。')
    for key in ('RERANKER_FP16', 'RERANKER_OFFLINE'):
        if type(values[key]) is not bool:
            raise ValueError(f'{key} 必须是布尔值。')
    return values


class SettingsStore:
    def __init__(self, path=None, loader=None):
        self.path = path or ROOT / 'config.local.yaml'
        self.loader = loader or load_settings
        self.lock = threading.RLock()

    def _read(self):
        try:
            data = yaml.safe_load(self.path.read_text(encoding='utf-8')) or {} if self.path.exists() else {}
        except yaml.YAMLError:
            raise ValueError('本地配置 YAML 无法解析，请先修复文件。') from None
        if not isinstance(data, dict):
            raise ValueError('本地配置必须是键值对象。')
        return data

    def _profiles(self, existing, config):
        profiles = existing.get('MODEL_PROFILES', [])
        if not isinstance(profiles, list) or any(not isinstance(p, dict) or not isinstance(p.get('values'), dict)
                                               or not isinstance(p.get('id'), str) for p in profiles):
            raise ValueError('保存的模型列表格式无效，请检查本地配置。')
        profiles = [dict(p) for p in profiles]
        active = existing.get('ACTIVE_MODEL_PROFILE', '')
        if not profiles and config.get('MODEL_NAME'):
            profiles = [profile_snapshot(config, 'current')]
            active = 'current'
        # The effective flat configuration remains authoritative for legacy workers and env overrides.
        for index, item in enumerate(profiles):
            if item['id'] == active:
                profiles[index] = {**item, **profile_snapshot(config, active, item.get('name'))}
        return profiles, active

    def _write(self, existing):
        fd, name = tempfile.mkstemp(prefix='.settings-', suffix='.tmp', dir=self.path.parent)
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as stream:
                yaml.safe_dump(existing, stream, allow_unicode=True, sort_keys=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(name, self.path)
        finally:
            if os.path.exists(name):
                os.unlink(name)

    def view(self):
        with self.lock:
            config = self.loader()
            raw = self.path.read_bytes() if self.path.exists() else b''
            revision = hashlib.sha256(raw + json.dumps(config, sort_keys=True, default=str).encode()).hexdigest()
            overrides = [key for key in (*DEFAULTS, *SECRETS) if os.environ.get(key)]
            if os.environ.get('SEMANTIC_SCHOLAR_API_KEY'):
                overrides.append('SEMANTIC_SCHOLAR_API_KEY')
            profiles, active = self._profiles(self._read(), config)
            public_profiles = []
            for item in profiles:
                values = item['values']
                url_key, _ = service_fields(values['LLM_PROVIDER'])
                public_profiles.append({'id': item['id'], 'name': item['name'],
                    'provider': values['LLM_PROVIDER'], 'model': values['MODEL_NAME'],
                    'base_url': values[url_key], 'configured': bool(item.get('api_key')),
                    'active': item['id'] == active})
            return {'values': public_values(config), 'revision': revision,
                    'profiles': public_profiles, 'active_profile': active, 'profile_support': True,
                    'service_support': True, 'services': self._public_services(profiles, public_profiles),
                    'credentials': {key: bool(config.get(key)) for key in SECRETS},
                    'llm_configured': bool(configured_key(config)), 'environment_overrides': overrides,
                    'presets': PRESETS, 'presets_checked_at': '2026-10-19'}

    def save(self, payload):
        with self.lock:
            if not isinstance(payload, dict):
                raise ValueError('设置请求必须是对象。')
            view = self.view()
            if payload.get('revision') != view['revision']:
                raise ValueError('配置已被其他页面或文件编辑修改。请重新加载后再保存。')
            if payload.get('service_action'):
                return self._service_action(payload, view)
            if payload.get('profile_action'):
                return self._profile_action(payload, view)
            values = validate(payload.get('values'))
            keys = payload.get('secrets', {})
            if not isinstance(keys, dict) or set(keys) - set(SECRETS):
                raise ValueError('未知密钥字段。')
            for key, value in keys.items():
                if not isinstance(value, str) or len(value) > 4096 or any(ord(c) < 32 for c in value):
                    raise ValueError('密钥格式无效，请检查粘贴内容。')
            changes = {key for key, value in values.items() if value != view['values'][key]}
            changes.update(key for key, value in keys.items() if value.strip())
            if changes.intersection(view['environment_overrides']):
                raise ValueError('这些字段被启动环境变量覆盖，请先修改环境变量并重启服务：' + ', '.join(sorted(changes.intersection(view['environment_overrides']))))
            existing = self._read()
            profiles, active = self._profiles(existing, self.loader())
            existing.update(values)
            existing.update({key: value.strip() for key, value in keys.items() if value.strip()})
            effective = {**self.loader(), **values, **{k:v.strip() for k,v in keys.items() if v.strip()}}
            if not active:
                active = uuid.uuid4().hex
                profiles.append(profile_snapshot(effective, active))
            else:
                profiles = [{**p, **profile_snapshot(effective, active, p['name'])} if p['id'] == active else p for p in profiles]
            existing.update(MODEL_PROFILES=profiles, ACTIVE_MODEL_PROFILE=active)
            self._write(existing)
            return self.view()

    @staticmethod
    def _services(profiles):
        groups = {}
        for profile in profiles:
            values = profile['values']
            url_key, _ = service_fields(values['LLM_PROVIDER'])
            identity = (values['LLM_PROVIDER'], values[url_key].rstrip('/'), profile.get('api_key', ''))
            groups.setdefault(identity, []).append(profile)
        return list(groups.values())

    def _public_services(self, profiles, public_profiles):
        public = {p['id']: p for p in public_profiles}
        result = []
        for members in self._services(profiles):
            first = public[members[0]['id']]
            name = members[0].get('service_name') or next(p['name'] for p in PRESETS if p['id'] == first['provider'])
            result.append({'id': first['id'], 'name': name, 'provider': first['provider'],
                           'base_url': first['base_url'], 'configured': first['configured'],
                           'models': [public[p['id']] for p in members]})
        return result

    def _connection(self, item, profiles, view):
        if not isinstance(item, dict):
            raise ValueError('请填写模型商连接。')
        members = next((g for g in self._services(profiles) if g[0]['id'] == item.get('id')), [])
        if item.get('id') and not members:
            raise ValueError('模型商配置已改变，请重新加载。')
        kind = item.get('provider')
        if kind not in {p['id'] for p in PRESETS}:
            raise ValueError('请选择支持的模型接口。')
        url_key, key_field = service_fields(kind)
        values = validate({**view['values'], 'LLM_PROVIDER': kind,
                           'MODEL_NAME': view['values']['MODEL_NAME'] or 'catalog', url_key: item.get('base_url')})
        key = item.get('api_key', '')
        if not isinstance(key, str) or len(key) > 4096 or any(ord(c) < 32 for c in key):
            raise ValueError('密钥格式无效。')
        same = members and members[0]['values']['LLM_PROVIDER'] == kind and members[0]['values'].get(url_key) == values[url_key]
        key = key.strip() or (members[0].get('api_key', '') if same else '')
        if not key:
            raise ValueError('请填写此模型商的 API 密钥。更换接口或地址后需要重新填写。')
        return members, values, key_field, key

    def catalog_config(self, item):
        with self.lock:
            view = self.view()
            profiles, _ = self._profiles(self._read(), self.loader())
            _, values, key_field, key = self._connection(item, profiles, view)
            return {**values, key_field: key}

    def _service_action(self, payload, view):
        existing, config = self._read(), self.loader()
        profiles, active = self._profiles(existing, config)
        item = payload.get('service')
        if payload['service_action'] == 'delete':
            members = next((g for g in self._services(profiles) if g[0]['id'] == payload.get('service_id')), [])
            if not members:
                raise ValueError('未找到这个模型商。')
            ids = {p['id'] for p in members}
            if active in ids:
                raise ValueError('请先使用其他模型商的模型，再移除此模型商。')
            profiles = [p for p in profiles if p['id'] not in ids]
        elif payload['service_action'] == 'save':
            members, values, key_field, key = self._connection(item, profiles, view)
            name, models = item.get('name', ''), item.get('models')
            if not isinstance(name, str) or not name.strip() or len(name) > 80 or any(ord(c)<32 for c in name):
                raise ValueError('请填写 1–80 字的模型商名称。')
            if not isinstance(models, list) or not 1 <= len(models) <= 50 or any(not isinstance(m,str) for m in models):
                raise ValueError('请至少选择一个模型，最多 50 个。')
            model_ids = []
            for model in models:
                model = validate({**values, 'MODEL_NAME': model})['MODEL_NAME']
                if model not in model_ids:
                    model_ids.append(model)
            # Reuse an identical connection rather than creating duplicate provider cards.
            url_key, _ = service_fields(values['LLM_PROVIDER'])
            duplicate = next((g for g in self._services(profiles)
                if g[0]['values']['LLM_PROVIDER'] == values['LLM_PROVIDER']
                and g[0]['values'].get(url_key) == values[url_key] and g[0].get('api_key') == key), [])
            if members and duplicate and duplicate[0]['id'] != members[0]['id']:
                raise ValueError('此连接已存在，请在对应模型商中管理模型。')
            if not members:
                url_key, _ = service_fields(values['LLM_PROVIDER'])
                members = next((g for g in self._services(profiles)
                    if g[0]['values']['LLM_PROVIDER'] == values['LLM_PROVIDER']
                    and g[0]['values'].get(url_key) == values[url_key] and g[0].get('api_key') == key), [])
                model_ids = list(dict.fromkeys([p['values']['MODEL_NAME'] for p in members] + model_ids))
            old_ids = {p['id'] for p in members}
            by_model = {p['values']['MODEL_NAME']: p for p in members}
            replacement = []
            url_key, _ = service_fields(values['LLM_PROVIDER'])
            for model in model_ids:
                previous = by_model.get(model)
                base = previous or (members[0] if members else {})
                replacement.append({'id': previous['id'] if previous else uuid.uuid4().hex,
                    'name': previous.get('name', model) if previous else model, 'service_name': name.strip(),
                    'values': {k: ({**values, **base.get('values', {}), 'LLM_PROVIDER': values['LLM_PROVIDER'],
                                   url_key: values[url_key], 'MODEL_NAME': model})[k] for k in (*MODEL_KEYS, url_key)}, 'api_key': key})
            if len(profiles)-len(members)+len(replacement) > 50:
                raise ValueError('最多保存 50 个模型，请减少选择。')
            profiles = [p for p in profiles if p['id'] not in old_ids] + replacement
            current = next((p for p in profiles if p['id'] == active), None)
            if active in old_ids or not current or not current.get('api_key'):
                target = next((p for p in replacement if p['id'] == active), replacement[0])
                changes = {**target['values'], key_field: key}
                blocked = [k for k,v in changes.items() if k in view['environment_overrides'] and str(config.get(k,'')) != str(v)]
                if blocked:
                    raise ValueError('启动环境变量固定了这些字段，请修改后重启服务：'+', '.join(blocked))
                existing.update(changes)
                active = target['id']
        else:
            raise ValueError('不支持的模型商操作。')
        existing.update(MODEL_PROFILES=profiles, ACTIVE_MODEL_PROFILE=active)
        self._write(existing)
        return self.view()

    def _profile_action(self, payload, view):
        existing = self._read()
        config = self.loader()
        profiles, active = self._profiles(existing, config)
        action = payload['profile_action']
        target = next((p for p in profiles if p['id'] == payload.get('profile_id')), None)
        activate = False
        if action in ('update', 'activate', 'delete') and target is None:
            raise ValueError('未找到这个模型配置，请重新加载。')
        if action in ('add', 'update'):
            item = payload.get('profile')
            if not isinstance(item, dict):
                raise ValueError('请填写模型配置。')
            name = item.get('name', '')
            if not isinstance(name, str) or not name.strip() or len(name) > 80 or any(ord(c)<32 for c in name):
                raise ValueError('请填写 1–80 字的模型名称。')
            kind = item.get('provider')
            if kind not in {p['id'] for p in PRESETS}:
                raise ValueError('请选择支持的模型服务。')
            url_key, _ = service_fields(kind)
            values = validate({**view['values'], **(target['values'] if target else {}),
                'LLM_PROVIDER': kind, 'MODEL_NAME': item.get('model'), url_key: item.get('base_url')})
            key = item.get('api_key', '')
            if not isinstance(key, str) or len(key)>4096 or any(ord(c)<32 for c in key):
                raise ValueError('密钥格式无效。')
            same_service = target and target['values']['LLM_PROVIDER'] == kind and target['values'].get(url_key) == values[url_key]
            key = key.strip() or (target.get('api_key','') if same_service else '')
            if not key:
                raise ValueError('请填写此服务的 API 密钥。更换服务或地址时需要重新填写。')
            if action == 'add' and len(profiles)>=50:
                raise ValueError('最多保存 50 个模型配置。')
            identity = target['id'] if target else uuid.uuid4().hex
            target = {'id':identity,'name':name.strip(),'values':{k:values[k] for k in (*MODEL_KEYS,url_key)},'api_key':key}
            profiles = [target if p['id']==identity else p for p in profiles] if action=='update' else profiles+[target]
            activate = identity == active or not active
        elif action == 'model':
            # Choosing an API-discovered model creates a sibling, preserving the saved original.
            current = next((p for p in profiles if p['id']==active), None)
            if current is None:
                raise ValueError('请先添加模型服务。')
            values = validate({**view['values'], 'MODEL_NAME':payload.get('model')})
            url_key, _ = service_fields(values['LLM_PROVIDER'])
            target = next((p for p in profiles if p['values']['MODEL_NAME']==values['MODEL_NAME']
                and p['values']['LLM_PROVIDER']==values['LLM_PROVIDER'] and p['values'].get(url_key)==values[url_key]
                and p.get('api_key')==current.get('api_key')), None)
            if target is None:
                if len(profiles)>=50:
                    raise ValueError('最多保存 50 个模型配置，请先移除不用的模型。')
                target = {**current,'id':uuid.uuid4().hex,'name':values['MODEL_NAME'],
                          'values':{**current['values'],'MODEL_NAME':values['MODEL_NAME']}}
                profiles.append(target)
            activate = True
        elif action == 'activate':
            activate = True
        elif action == 'delete':
            if target['id'] == active:
                raise ValueError('请先切换到其他模型，再移除当前模型。')
            profiles = [p for p in profiles if p['id'] != target['id']]
        else:
            raise ValueError('不支持的模型管理操作。')
        if activate:
            _, key_field = service_fields(target['values']['LLM_PROVIDER'])
            changes = {**target['values'], key_field:target.get('api_key','')}
            blocked = [key for key,value in changes.items() if key in view['environment_overrides']
                       and str(config.get(key,'')) != str(value)]
            if blocked:
                raise ValueError('启动环境变量固定了这些字段，请修改后重启服务：'+', '.join(blocked))
            if not target.get('api_key'):
                raise ValueError('这个模型尚未配置 API 密钥，请先编辑。')
            existing.update(changes)
            active = target['id']
        existing.update(MODEL_PROFILES=profiles, ACTIVE_MODEL_PROFILE=active)
        self._write(existing)
        return self.view()


def check_local(values):
    values = validate(values)
    checks = [{'status': 'ok', 'title': '参数格式', 'detail': '字段与范围检查通过；不代表远程 API 已连通。'}]
    import torch
    devices = [{'id': 'cpu', 'name': 'CPU'}]
    devices += [{'id': f'cuda:{i}', 'name': torch.cuda.get_device_name(i)} for i in range(torch.cuda.device_count())]
    target = values['RERANKER_DEVICE']
    available = target == 'cpu' or (target == 'cuda' and len(devices) > 1) or any(d['id'] == target for d in devices)
    checks.append({'status': 'ok' if available else 'error', 'title': '运行设备',
                   'detail': f'{target} 可用。' if available else f'{target} 不可用，请选择 CPU 或已检测到的 GPU。'})
    model = values['RERANKER_MODEL']
    folder = Path(model)
    if not folder.is_dir():
        from huggingface_hub import snapshot_download
        try:
            folder = Path(snapshot_download(model, local_files_only=True))
        except Exception:
            folder = None
    cached = folder is not None and (folder / 'config.json').exists() and any(folder.glob('*.safetensors'))
    cached = cached or (folder is not None and (folder / 'config.json').exists() and any(folder.glob('pytorch_model*.bin')))
    checks.append({'status': 'ok' if cached else 'error' if values['RERANKER_OFFLINE'] else 'warning',
                   'title': '重排模型文件', 'detail': '找到配置和权重文件；尚未加载权重或验证模型兼容性。' if cached else
                   ('未找到本地权重。仅本地模式下研究会失败，请先准备模型或允许首次下载。' if values['RERANKER_OFFLINE'] else '未找到本地权重；首次研究将尝试下载，可能耗时较长。')})
    if target == 'cpu' and values['RERANKER_FP16']:
        checks.append({'status': 'warning', 'title': '精度', 'detail': 'CPU 将自动使用 FP32；FP16 只用于 GPU。'})
    return {'checks': checks, 'devices': devices, 'remote_tested': False}
