"""Strict parsing with only unambiguous transport-envelope cleanup.

Never eval model output, invent missing braces/quotes, or silently discard fields.
"""
import json
import re


class StructuredOutputError(ValueError):
    """A model response could not be used as a complete JSON object."""


def parse_object(text):
    if not isinstance(text, str):
        raise StructuredOutputError('模型没有返回 JSON 文本。')
    raw = text.strip().lstrip('\ufeff')
    fence = re.fullmatch(r'```(?:json)?\s*\n?(.*?)\s*```', raw, flags=re.S | re.I)
    if fence:
        raw = fence.group(1).strip()
    def unique_pairs(pairs):
        obj = {}
        for key, value in pairs:
            if key in obj:
                raise StructuredOutputError('模型返回了重复 JSON 字段，无法确定应采用哪个值。')
            obj[key] = value
        return obj
    def reject_constant(value):
        raise StructuredOutputError('模型返回了非法 JSON 数值：'+value)
    try:
        value = json.loads(raw, object_pairs_hook=unique_pairs, parse_constant=reject_constant)
    except json.JSONDecodeError as exc:
        raise StructuredOutputError(f'模型返回的 JSON 格式无效（第 {exc.lineno} 行，第 {exc.colno} 列）：{exc.msg}') from exc
    if not isinstance(value, dict):
        raise StructuredOutputError('模型应返回 JSON 对象，但返回了其他类型。')
    return value
