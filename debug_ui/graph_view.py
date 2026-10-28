"""Read-only projection of recorded retrieval evidence; never infer citation or causality."""
from collections import defaultdict
from itertools import combinations
import json
import re


def completed_steps(events):
    steps = {}
    for event in events:
        if event.get('event') == 'start':
            steps[event['id']] = dict(event)
        elif event.get('id') in steps:
            steps[event['id']].update(event)
    return list(steps.values())


def build_view(graph, result, events):
    result = result or {}
    steps = completed_steps(events)
    passages = {p['id']: p for p in graph.get('passages', [])}
    seeds, retrieved, scores, reasons = set(), set(), {}, {}
    candidate_paths = result.get('candidate_paths', [])
    for step in steps:
        out = step.get('output')
        if not isinstance(out, dict):
            continue
        if 'seeds' in out and 'candidates' in out:
            seeds.update(p['id'] for p in out['seeds'])
            retrieved.update(p['id'] for p in out['candidates'])
            passages.update((p['id'], p) for p in out['candidates'])
            reasons.update(out.get('entry_reasons', {}))
        if 'ranked' in out:
            for p in out['ranked']:
                if isinstance(p, dict) and p.get('paper_id'):
                    passages[p['id']] = p
                    scores[p['id']] = p.get('score')
        if 'paths' in out and 'rejected_links' in out:
            candidate_paths = out['paths']
    retrieved.update(result.get('retrieved_passage_ids', []))
    reasons.update(result.get('entry_reasons', {}))
    sources = result.get('sources', [])
    context = {p.get('passage_id') for p in sources}
    cited_indices = {int(i) for i in re.findall(r'\[(\d+)\]', result.get('answer', ''))}
    cited = {p.get('passage_id') for i, p in enumerate(sources) if i in cited_indices}
    nodes = {}
    for p in passages.values():
        pid = p['paper_id']
        # A fixed-corpus passage is not "retrieved" merely because it exists in the index.
        if p['id'] not in retrieved | seeds | context and p['id'] not in scores:
            continue
        node = nodes.setdefault(pid, {'id': pid, 'title': p['title'], 'passages': [],
            'seed': False, 'retrieved': False, 'context': False, 'cited': False, 'score': None})
        node['seed'] |= p['id'] in seeds
        node['retrieved'] |= p['id'] in retrieved | seeds | context
        node['context'] |= p['id'] in context
        node['cited'] |= p['id'] in cited
        score = scores.get(p['id'], p.get('score'))
        if isinstance(score, (int, float)):
            node['score'] = max(node['score'] if node['score'] is not None else score, score)
        node['passages'].append({**p, 'retrieved': p['id'] in retrieved | seeds | context,
                                'reasons': reasons.get(p['id'], [])})

    # Online SciRAG: expose recorded papers without inventing a missing entity graph.
    citations = set()
    def scan(value, admitted=True):
        if isinstance(value, list):
            for item in value:
                scan(item, admitted)
        elif isinstance(value, dict):
            paper = value.get('paper', value)
            pid = paper.get('paperId', paper.get('paper_id', paper.get('id'))) if isinstance(paper, dict) else None
            if pid and paper.get('title'):
                if pid not in nodes:
                    nodes[pid] = {'id': pid, 'title': paper['title'], 'seed': False,
                        'retrieved': admitted, 'context': False, 'cited': False, 'score': paper.get('score'),
                        'passages': [{'text': paper.get('text') or paper.get('abstract') or '',
                                      'retrieved': admitted, 'reasons': [{'type': 'recorded_retrieval' if admitted else 'api_candidate'}]}]}
                elif admitted:
                    nodes[pid]['retrieved'] = True
                for key in ('references', 'citations'):
                    for ref in value.get(key, []) or []:
                        target = ref.get('paperId') if isinstance(ref, dict) else None
                        if target:
                            citations.add((pid, target) if key == 'references' else (target, pid))
            for child in value.values():
                if isinstance(child, (dict, list)):
                    scan(child, admitted)
    if not graph:
        for step in steps:
            if step.get('kind') != 'llm':
                scan(step.get('output'), step.get('kind') != 'http')
        scan(sources)
        for step in steps:
            out = step.get('output')
            if isinstance(out, dict) and 'usable_contexts' in out:
                for p in out['usable_contexts']:
                    if p['paperId'] in nodes:
                        nodes[p['paperId']]['seed'] = True
    online = graph.get('online_corpus', {})
    scan(online.get('candidates', []), False)
    scan(online.get('papers', []), True)
    for paper in online.get('candidates', []):
        if paper.get('paperId') in nodes:
            nodes[paper['paperId']].update(indexed=paper.get('selected', False),
                exclusion_reason=paper.get('exclusion_reason', ''), url=paper.get('url'), year=paper.get('year'))
    for i, source in enumerate(sources):
        pid = source.get('id', source.get('paperId'))
        if pid in nodes:
            nodes[pid]['context'] = True
            nodes[pid]['cited'] |= i in cited_indices

    labels = {e['id']: e['name'] for e in graph.get('entities', [])}
    mentions = defaultdict(lambda: defaultdict(list))
    for m in graph.get('mentions', []):
        if m['paper_id'] in nodes and (online or m['passage_id'] in retrieved | seeds | context):
            mentions[m['entity_id']][m['paper_id']].append(m)
    edges = []
    shared = defaultdict(list)
    for eid, papers in mentions.items():
        for left, right in combinations(sorted(papers), 2):
            shared[left, right].append({'entity': labels.get(eid, eid), 'entity_id': eid,
                'mentions': papers[left] + papers[right]})
    for (left, right), evidence in sorted(shared.items()):
        edges.append({'source': left, 'target': right, 'type': 'shared', 'directed': False,
                      'label': f'共享 {len(evidence)} 个实体', 'weight': len(evidence), 'evidence': evidence})
    associations = defaultdict(list)
    for assoc in graph.get('associations', {}).get('edges', []):
        if not assoc['eligible']:
            continue
        for left in mentions[assoc['source']]:
            for right in mentions[assoc['target']]:
                if left == right:
                    continue
                pair = tuple(sorted((left, right)))
                witness = {'source_entity': labels.get(assoc['source'], assoc['source']),
                           'target_entity': labels.get(assoc['target'], assoc['target']),
                           'score': assoc['score'], 'windows': assoc['cij'], 'papers': assoc['paper_count']}
                if witness not in associations[pair]:
                    associations[pair].append(witness)
    for (left, right), evidence in sorted(associations.items()):
        edges.append({'source': left, 'target': right, 'type': 'cooccurrence', 'directed': False,
                      'label': '实体共现关联', 'weight': len(evidence), 'evidence': evidence})

    claims = {c['id']: c for c in graph.get('claims', [])}
    chosen = {p['id'] for p in result.get('paths', [])}
    paths = []
    for path in candidate_paths:
        relations = [claims[c] for c in path.get('claim_ids', []) if c in claims]
        if not relations:
            continue
        record = {**path, 'selected': path['id'] in chosen, 'relations': relations}
        paths.append(record)
        for left, right in zip(relations, relations[1:]):
            if left['paper_id'] == right['paper_id'] or not {left['paper_id'], right['paper_id']} <= nodes.keys():
                continue
            edges.append({'source': left['paper_id'], 'target': right['paper_id'], 'type': 'path',
                'directed': True, 'label': '已选证据接续' if record['selected'] else '候选证据接续',
                'weight': 1, 'path_id': path['id'], 'state': path['state'],
                'selected': record['selected'], 'evidence': [left, right], 'checks': path.get('checks', [])})
    for left, right in sorted(citations):
        if {left, right} <= nodes.keys():
            edges.append({'source': left, 'target': right, 'type': 'citation', 'directed': True,
                          'label': '引用', 'weight': 1, 'evidence': 'Semantic Scholar 返回的 references / citations 字段'})
    for i, edge in enumerate(edges):
        edge['id'] = f'edge-{i}'
    return {'nodes': sorted(nodes.values(), key=lambda n: (not n['context'], not n['seed'], n['title'])),
            'edges': edges, 'paths': paths, 'entity_labels': labels,
            'rejected_links': result.get('rejected_links', []),
            'has_entity_graph': bool(graph.get('graph_version')), 'graph_version': graph.get('graph_version'),
            'note': '论文连线是证据组织关系；箭头表示引用方向或证据接续顺序，不表示论文之间存在因果效应。'}


def load_view(root, folder, result, events):
    snapshot = folder / 'graph-snapshot.json'
    graph = {}
    if snapshot.exists():
        graph = json.loads(snapshot.read_text(encoding='utf-8'))
    else:
        version = (result or {}).get('graph_version')
        if not version:
            for step in completed_steps(events):
                out = step.get('output')
                if isinstance(out, dict) and out.get('graph_version'):
                    version = out['graph_version']
        if isinstance(version, str) and re.fullmatch(r'[a-f0-9]{20}', version):
            path = root / '.cache/clinkrag' / (version + '.json')
            if path.exists():
                graph = json.loads(path.read_text(encoding='utf-8'))
    manifest = folder / 'online-corpus.json'
    if manifest.exists():
        graph['online_corpus'] = json.loads(manifest.read_text(encoding='utf-8'))
    return build_view(graph, result, events)
