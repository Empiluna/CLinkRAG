"""python -m clinkrag.cli build|ask|compare --corpus <JSON>"""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'longans'))
from llms.settings import load_settings
from debug_ui.tracing import Recorder
from .core import Config,write_json
from .index import build_index
from .runtime import Model,Ranker
from .pipeline import run

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('command',choices=['build','ask','compare'])
    parser.add_argument('--corpus',default=str(ROOT/'evaluation/data/corpus.json'))
    parser.add_argument('--questions',default=str(ROOT/'evaluation/data/questions.json'))
    parser.add_argument('--output',default=str(ROOT/'results/clinkrag'))
    parser.add_argument('--question',default='')
    args=parser.parse_args()
    settings=load_settings(); os.environ['HF_HUB_OFFLINE']='1';os.environ['TRANSFORMERS_OFFLINE']='1'
    output=Path(args.output);output.mkdir(parents=True,exist_ok=True)
    recorder=Recorder(output/'events.jsonl',[v for k,v in settings.items() if 'KEY' in k])
    model=Model(settings.get('MODEL_NAME') or 'deepseek-flash',recorder)
    papers=json.loads(Path(args.corpus).read_text(encoding='utf-8'))['papers']
    graph=build_index(papers,model,ROOT/'.cache/clinkrag',recorder)
    write_json(output/'index-summary.json',{'version':graph['version'],'graph_version':graph['graph_version'],
        'papers':len(graph['papers']),'passages':len(graph['passages']),'entities':len(graph['entities']),
        'claims':len(graph['claims']),'associations':sum(e['eligible'] for e in graph['associations']['edges']),
        'offline_calls':model.calls})
    print(json.dumps({'index_ready':True,'papers':len(graph['papers']),'claims':len(graph['claims'])}),flush=True)
    if args.command=='build':return
    ranker=Ranker(settings.get('RERANKER_DEVICE','cpu'),recorder)
    if args.command=='ask':
        if not args.question:parser.error('--question is required')
        write_json(output/'result.json',run(args.question,graph,model,ranker,recorder=recorder))
    else:
        from .evaluate import compare
        compare(graph,json.loads(Path(args.questions).read_text(encoding='utf-8')),model,ranker,output,recorder)

if __name__=='__main__':main()
