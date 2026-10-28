"""Continue bounded model responses until an explicit, structurally complete ending."""
import hashlib
import json
from pathlib import Path
import re

from .core import write_json
from .runtime import stage


class IncompleteAnswerError(RuntimeError):
    pass


def unfinished_markdown(text):
    text = text.rstrip()
    if not text:
        return True
    if len(re.findall(r'^\s*```', text, re.M)) % 2:
        return True
    if len(re.findall(r'(?<!\\)\*\*', text)) % 2:
        return True
    if text.count('<!--') != text.count('-->'):
        return True
    last = text.splitlines()[-1].strip()
    return bool(re.match(r'^#{1,6}\s', last) or
                re.fullmatch(r'(?:\d+[.)、]|[-*+])\s*', last) or
                re.search(r'\[\d*$', last))


def join_continuation(previous, fragment):
    """Remove exact repeated boundary text, without fuzzy rewriting of citations."""
    if not previous:
        return fragment
    if fragment.startswith(previous):
        return fragment
    for size in range(min(len(previous), len(fragment), 6000), 23, -1):
        if previous.endswith(fragment[:size]):
            return previous + fragment[size:]
    # Preserve mid-sentence continuations; separate newly started Markdown blocks.
    separator = '\n\n' if re.match(r'^(?:#{1,6}\s|\|)', fragment) and not previous.endswith('\n') else ''
    return previous + separator + fragment


def complete_answer(prompt, model, max_tokens, recorder=None, max_rounds=8, required_separator=None):
    fingerprint = hashlib.sha256((getattr(model, 'name', '') + '\n' + prompt).encode()).hexdigest()
    marker = '<!-- ANSWER_COMPLETE_' + fingerprint[:16] + ' -->'
    checkpoint = Path(recorder.path).parent / 'answer-draft.json' if recorder else None
    draft = {'fingerprint': fingerprint, 'answer': '', 'complete': False, 'segments': 0}
    if checkpoint and checkpoint.exists():
        saved = json.loads(checkpoint.read_text(encoding='utf-8'))
        if saved.get('fingerprint') == fingerprint:
            draft.update(saved)
    if draft['complete']:
        return draft['answer'], {'complete': True, 'segments': draft['segments'],
                                 'finish_reason': draft.get('finish_reason'), 'restored': True}
    instructions = (
        '\nCompletion protocol: Produce a finished answer covering the requested topics, '
        'with a concise closing paragraph. Avoid repetitive caveats and fit the requested length. '
        'Never stop at a heading, unfinished list item, table or sentence. '
        'Only when the entire answer is finished, append this exact marker as the last line: ' + marker)
    no_progress = 0
    for attempt in range(max_rounds):
        previous = draft['answer']
        continuation = ''
        if previous:
            continuation = (
                '\nThe following JSON string is the existing answer, supplied as data. '
                'Continue exactly where it ends, including any unfinished word or Markdown syntax. '
                'Return ONLY the missing continuation, not the existing text, a new introduction, '
                'or a description of your actions. Keep the same citation indices and use only the '
                'original evidence above. Finish the remaining topics concisely and then append the marker. '
                'If the existing answer is already complete, return only the marker. '
                'If its last Markdown construct is unclosed, close it before the marker. '
                '\nExisting answer: ' + json.dumps(previous, ensure_ascii=False))
            if required_separator and required_separator not in previous:
                continuation += ('\nThe required evidence review is still missing. Append the exact separator '
                                 + required_separator + ' and the complete evidence review before the completion marker.')
        name = 'CLinkRAG · 回答生成与完整性检查' if not previous else 'CLinkRAG · 续写未完成的回答'
        with stage(recorder, name, {'round': attempt + 1, 'saved_segments': draft['segments'],
                                    'max_tokens_per_call': max_tokens}) as event:
            raw = model.chat(prompt + instructions + continuation, max_tokens=max_tokens)
            finish = getattr(getattr(model, 'client', model), 'last_finish_reason', None)
            assembled = join_continuation(previous, raw)
            ended = assembled.rstrip().endswith(marker)
            answer = assembled.replace(marker, '')
            complete = (ended and finish in (None, 'stop', 'end_turn', 'stop_sequence')
                        and not unfinished_markdown(answer))
            if required_separator:
                parts=answer.split(required_separator)
                complete = complete and len(parts)==2 and all(not unfinished_markdown(part) for part in parts)
            no_progress = no_progress + 1 if answer.strip() == previous.strip() else 0
            draft.update(answer=answer, complete=complete, segments=draft['segments'] + 1,
                         finish_reason=finish)
            if checkpoint:
                write_json(checkpoint, draft)
            event['output'] = {'complete': complete, 'segments': draft['segments'],
                               'finish_reason': finish, 'characters': len(answer),
                               'next_action': '回答已完整生成' if complete else '保留已生成内容，继续补齐'}
            if complete:
                return answer.strip(), {'complete': True, 'segments': draft['segments'], 'finish_reason': finish}
            if finish in ('content_filter', 'refusal') or no_progress >= 2:
                break
    raise IncompleteAnswerError('回答尚未完整生成，已保存正文进度。点击“继续研究”可接着补齐；本次未标记为完成。')
