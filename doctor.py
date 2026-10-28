"""Local checks never call paid APIs; --live explicitly checks external services."""
import argparse
import importlib
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
os.environ.setdefault('HF_HOME', str(ROOT / '.cache' / 'huggingface'))
os.environ.setdefault('TORCH_HOME', str(ROOT / '.cache' / 'torch'))
sys.path.insert(0, str(ROOT / 'longans'))

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--live', action='store_true')
    parser.add_argument('--prepare-reranker', action='store_true')
    args = parser.parse_args()
    missing = []
    for name in ['yaml', 'openai', 'requests', 'numpy', 'jsonlines', 'datasets', 'torch', 'FlagEmbedding']:
        try:
            module = importlib.import_module(name)
            print('OK dependency:', name, getattr(module, '__version__', ''))
        except Exception as exc:
            print('FAIL dependency:', name, type(exc).__name__, str(exc))
            missing.append(name)
    if missing:
        return 1
    from llms import get_model
    from llms.settings import load_settings
    from pipe import pipeline
    from run import process_input_data
    config = load_settings()
    sample = json.loads((ROOT / 'examples/sample.jsonl').read_text(encoding='utf-8'))
    process_input_data([sample])
    pipeline()
    print('OK pipeline import and sample input')
    print('Model:', config.get('MODEL_NAME', 'deepseek-flash'))
    print('Model key:', 'configured' if config.get('DEEPSEEK_API_KEY') or config.get('OPENAI_API_KEY') else 'MISSING')
    print('Semantic Scholar key:', 'configured' if config.get('S2_API_KEY') else 'MISSING')
    if args.prepare_reranker:
        from FlagEmbedding import FlagReranker
        device = config.get('RERANKER_DEVICE', 'cpu')
        import torch
        if str(device).startswith('cuda'):
            if not torch.cuda.is_available():
                raise RuntimeError('CUDA requested but not available; install the CUDA PyTorch build.')
            print('GPU:', torch.cuda.get_device_name(device), 'PyTorch CUDA:', torch.version.cuda)
            torch.cuda.reset_peak_memory_stats(device)
        print('Preparing original BAAI/bge-reranker-v2-m3 on', device, flush=True)
        ranker = FlagReranker('BAAI/bge-reranker-v2-m3', devices=device, use_fp16=device != 'cpu')
        scores = ranker.compute_score([
            ['What is retrieval augmented generation?', 'Retrieval augmented generation retrieves documents to inform language model answers.'],
            ['What is retrieval augmented generation?', 'A recipe describes baking a chocolate cake.'],
        ], batch_size=2)
        print('Reranker scores:', scores)
        if len(scores) != 2 or scores[0] <= scores[1]:
            raise RuntimeError('Unexpected reranker output on sanity example.')
        actual_device = str(next(ranker.model.parameters()).device)
        print('Model parameter device:', actual_device)
        if str(device).startswith('cuda'):
            torch.cuda.synchronize(device)
            if actual_device != str(torch.device(device)):
                raise RuntimeError('Reranker did not run on the configured CUDA device.')
            print('Peak allocated GPU MiB:', round(torch.cuda.max_memory_allocated(device) / 2**20, 1))
        print('OK real reranker inference')
    if args.live:
        import requests
        failures = []
        try:
            client = get_model('configured')
            response = client.chat('Return a JSON object with the single field ok set to true.', max_tokens=64, json_mode=True)
            if json.loads(response).get('ok') is not True:
                raise RuntimeError('Unexpected JSON response')
            print('OK real model request and JSON mode')
        except Exception as exc:
            failures.append('model')
            print('FAIL model:', type(exc).__name__, 'Check credentials, balance, endpoint and model ID.')
        try:
            if not config.get('S2_API_KEY'):
                raise ValueError('Missing key')
            response = requests.get('https://api.semanticscholar.org/graph/v1/snippet/search',
                params={'query': 'retrieval augmented generation', 'limit': 1},
                headers={'x-api-key': config['S2_API_KEY']}, timeout=60)
            response.raise_for_status()
            if not response.json().get('data'):
                raise RuntimeError('No snippets')
            print('OK real Semantic Scholar snippet search')
        except Exception as exc:
            failures.append('retrieval')
            status = getattr(getattr(exc, 'response', None), 'status_code', None)
            print('FAIL retrieval:', type(exc).__name__, 'HTTP:', status, 'Check S2 key and snippet API access.')
        if failures:
            return 2
    else:
        print('This command did not call the model or Semantic Scholar APIs.')
    return 0

if __name__ == '__main__':
    raise SystemExit(main())
