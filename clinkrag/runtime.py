"""Measured model calls and shared cached GPU reranker."""
from contextlib import contextmanager
import json
import time
from .structured import StructuredOutputError, parse_object

@contextmanager
def stage(recorder,name,inputs=None,kind='stage'):
    if recorder:
        with recorder.step(name,kind,inputs) as item:
            yield item
    else:
        yield {}

class Model:
    def __init__(self,name,recorder=None):
        from llms import get_model
        self.client=get_model(name)
        self.name=name;self.recorder=recorder;self.calls=[]
    def chat(self,messages,**kwargs):
        # Identical temperature for reproducible method comparisons; no response caching.
        kwargs.setdefault('temperature',0)
        with stage(self.recorder,'模型调用 · CLinkRAG',{'messages':messages,**kwargs},'llm') as event:
            start=time.monotonic()
            answer=self.client.chat(messages,**kwargs)
            usage=getattr(self.client,'last_usage',None)
            self.calls.append({'seconds':time.monotonic()-start,'usage':usage,
                               'finish_reason':getattr(self.client,'last_finish_reason',None),
                               'input_characters':len(messages),'output_characters':len(answer)})
            event['output']={'text':answer,'usage':usage,
                             'transport_parameters':getattr(self.client,'last_request_parameters',None)}
            return answer
    def json(self,prompt,max_tokens=3000,max_attempts=2,required_list=None):
        failure=None
        for attempt in range(max_attempts):
            retry=('\nYour previous response could not be parsed as a complete JSON object. '
                   'Generate the full requested object again from the original evidence. '
                   'Use double-quoted property names, balanced braces/brackets, no duplicate keys, '
                   'no trailing commas, and no markdown. Keep quotes short and verbatim. '
                   'Do not invent evidence or change the required schema.') if attempt else ''
            with stage(self.recorder,'结构化输出 · 解析与恢复',{'attempt':attempt+1,'max_attempts':max_attempts}) as event:
                try:
                    try:
                        raw=self.chat(prompt+retry,json_mode=True,max_tokens=max_tokens)
                    except RuntimeError as exc:
                        # Provider adapters reject explicitly truncated JSON before returning it.
                        if 'json' in str(exc).lower() and ('truncat' in str(exc).lower() or
                                getattr(self.client,'last_finish_reason',None) in ('length','max_tokens')):
                            raise StructuredOutputError('模型的 JSON 输出达到长度上限，内容不完整。') from exc
                        raise
                    value=parse_object(raw)
                    if required_list is not None and (not isinstance(value.get(required_list),list) or
                            any(not isinstance(item,dict) for item in value[required_list])):
                        raise StructuredOutputError(f'模型结果缺少有效的 {required_list} 对象列表。')
                except StructuredOutputError as exc:
                    failure=exc
                    event['output']={'parsed':False,'reason':str(exc),'retrying':attempt+1<max_attempts}
                else:
                    event['output']={'parsed':True,'recovered':attempt>0}
                    return value
        raise StructuredOutputError(f'结构化结果经过 {max_attempts} 次尝试仍无法解析。'+str(failure)) from failure

class Ranker:
    def __init__(self,device='cuda:0',recorder=None):
        self.device=device;self.recorder=recorder;self.model=None
    def rank(self,query,items,text=lambda x:x['text']):
        if not items:return []
        from llms.reranking import create_reranker, score_options, options
        with stage(self.recorder,'语义召回与候选重排',{'query':query,'candidates':len(items), 'reranker':options(self.device)},'gpu') as event:
            if self.model is None:
                self.model=create_reranker(self.device)
            scores=self.model.compute_score([[query,text(x)] for x in items],**score_options())
            if isinstance(scores,(int,float)):scores=[scores]
            result=sorted([dict(x,score=float(score)) for x,score in zip(items,scores)],key=lambda x:x['score'],reverse=True)
            event['output']={'device':str(self.model.model.device),'ranked':result}
            return result

def token_count(text):
    # cl100k is a consistent budgeting proxy, not DeepSeek's billing tokenizer.
    import tiktoken
    return len(tiktoken.get_encoding('cl100k_base').encode(text))
