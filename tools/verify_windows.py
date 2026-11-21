"""Black-box smoke test for an extracted Windows release, with no model or search keys."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import socket
import subprocess
import tempfile
import time
import urllib.request
import zipfile

FORBIDDEN = {'.git', '.cache', '.venv', 'results', '__pycache__', 'config.local.yaml', 'config.yaml'}


def text_pdf():
    """A one-page text PDF containing a known reference sentence."""
    stream = b'BT /F1 12 Tf 25 80 Td (Archive dates were independently recorded.) Tj ET'
    objects = [b'<< /Type /Catalog /Pages 2 0 R >>', b'<< /Type /Pages /Kids [3 0 R] /Count 1 >>',
               b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 400 120] /Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >>',
               b'<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>',
               b'<< /Length %d >>\nstream\n' % len(stream) + stream + b'\nendstream']
    data = bytearray(b'%PDF-1.4\n')
    offsets = []
    for i, obj in enumerate(objects, 1):
        offsets.append(len(data))
        data.extend(b'%d 0 obj\n' % i + obj + b'\nendobj\n')
    start = len(data)
    data.extend(b'xref\n0 6\n0000000000 65535 f \n')
    for offset in offsets:
        data.extend(b'%010d 00000 n \n' % offset)
    data.extend(b'trailer\n<< /Size 6 /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF' % start)
    return bytes(data)


def unpack(archive_path, dest):
    with zipfile.ZipFile(archive_path) as archive:
        hashes = json.loads(archive.read('CLinkRAG/FILES.sha256.json'))
        checked = set()
        for name in archive.namelist():
            path = PurePosixPath(name)
            if (path.parts[0] != 'CLinkRAG' or '..' in path.parts or '\\' in name or ':' in name or
                    set(part.lower() for part in path.parts) & FORBIDDEN):
                raise ValueError(f'Unexpected release member: {name}')
            member = '/'.join(path.parts[1:])
            if member == 'FILES.sha256.json':
                continue
            if member in checked or hashlib.sha256(archive.read(name)).hexdigest() != hashes[member]:
                raise ValueError(f'Invalid archive manifest: {name}')
            checked.add(member)
        if checked != set(hashes):
            raise ValueError('Archive is incomplete')
        archive.extractall(dest)
    return dest / 'CLinkRAG'


def validate(package, *, with_research, online):
    env = {k: v for k, v in os.environ.items()
           if not k.endswith('API_KEY') and not k.startswith(('PYTHON', 'CONDA', 'VIRTUAL_ENV'))}
    env.update(PATH=str(Path(os.environ['SystemRoot']) / 'System32'), CLINKRAG_UNATTENDED='1')
    client = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with tempfile.TemporaryDirectory(prefix='CLinkRAG 便携验收 ') as tmp, socket.socket() as busy:
        root = unpack(package, Path(tmp))
        probe = subprocess.run([str(root/'runtime/python.exe'), '-I', '-c',
                                'import yaml,requests,ssl; import sys; print(sys.version, sys.prefix)'],
                               env=env, capture_output=True, cwd=root)
        if probe.returncode:
            raise RuntimeError(probe.stderr.decode('utf-8', errors='replace'))
        busy.bind(('127.0.0.1', 0))
        busy.listen()
        requested = busy.getsockname()[1]
        command = [env['COMSPEC'], '/d', '/c', 'Start-CLinkRAG.cmd', '--no-browser', '--port', str(requested)]
        with (Path(tmp) / 'launcher.log').open('wb') as log:
            proc = subprocess.Popen(command, cwd=root, env=env, stdout=log, stderr=log,
                                    creationflags=subprocess.CREATE_NO_WINDOW)
            try:
                state = root/'.cache/launcher/instance.json'
                for _ in range(200):
                    if state.exists() or proc.poll() is not None:
                        break
                    time.sleep(.05)
                if not state.exists():
                    raise RuntimeError((Path(tmp)/'launcher.log').read_text('utf-8', errors='replace'))
                port = json.loads(state.read_text('utf-8'))['port']
                assert port != requested, 'Port collision was not handled'
                base = f'http://127.0.0.1:{port}'
                def get_json(path):
                    with client.open(base+path, timeout=10) as response:
                        return json.load(response)
                with client.open(base+'/', timeout=10) as response:
                    html = response.read().decode('utf-8')
                assert '<html' in html.lower()
                assets = re.findall(r'<(?:link|script)\b[^>]*?\b(?:href|src)="(/[^"]+)"', html)
                mime = {'.js':'text/javascript', '.css':'text/css', '.svg':'image/svg+xml'}
                assert {url.split('?')[0] for url in assets} >= {'/source-tour.js', '/literature.css'}
                for url in assets:
                    filename = url.split('?')[0].lstrip('/')
                    local = root/'debug_ui/static'/filename
                    with client.open(base+url, timeout=5) as response:
                        assert response.headers.get_content_type() == mime[local.suffix], filename
                        assert response.read() == local.read_bytes(), filename
                print(f'Verified all {len(assets)} local UI scripts, stylesheets and icon over HTTP.')
                config = get_json('/api/config')
                assert not config['s2_configured'] and not config['llm_configured']
                assert get_json('/api/runs') == [] and get_json('/api/settings')
                second = subprocess.run(command, cwd=root, env=env, timeout=15,
                                        capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
                assert second.returncode == 0 and base.encode() in second.stdout, 'Second launch lost the session'
                cli = subprocess.run([str(root/'runtime/python.exe'), 'debug_ui/server.py', '--port', str(port)],
                                     cwd=root, env=env, timeout=15, capture_output=True,
                                     creationflags=subprocess.CREATE_NO_WINDOW)
                assert cli.returncode == 0 and base.encode() in cli.stdout, 'CLI did not reuse the active workbench'
                ps = str(Path(os.environ['SystemRoot'])/'System32/WindowsPowerShell/v1.0/powershell.exe')
                legacy = subprocess.run([ps, '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                                         'start-ui.ps1', '-Port', str(port)], cwd=root, env=env, timeout=15,
                                        capture_output=True, creationflags=subprocess.CREATE_NO_WINDOW)
                assert legacy.returncode == 0 and base.encode() in legacy.stdout, 'PowerShell entry point failed'
                if with_research:
                    library = get_json('/api/literature')
                    assert library['count'] > 0 and library['example_question']
                    def search(collection, question, **kwargs):
                        query = json.dumps(dict(collection=collection, question=question, **kwargs)).encode()
                        request = urllib.request.Request(base + '/api/literature/search', data=query,
                            headers={'X-SciRAG-Token': config['token'], 'Content-Type': 'application/json',
                                     'Origin': base})
                        with client.open(request, timeout=45) as response:
                            return json.load(response)
                    result = search('builtin', library['example_question'])
                    corpus = json.loads((root/'clinkrag/data/library.json').read_text('utf-8'))
                    rows = {p['paper_id']:p for p in corpus}
                    assert result['items'] and result['markdown'] and result['ris']
                    for item in result['items']:
                        original = rows[item['paper_id']]['text']
                        assert item['quote'] == original[item['start']:item['end']]
                        assert item['title'] in result['ris'] and item['quote'] in result['markdown']
                    personal = '手稿甲写于六月。手稿乙另于九月补记，同时注明秋粮的来源。'
                    own = search('personal', '手稿乙何时补记秋粮', papers=[{'title':'自带文本', 'text':personal}])
                    excerpt = own['items'][0]
                    assert excerpt['quote'] == personal[excerpt['start']:excerpt['end']]
                    pdf = urllib.request.Request(base+'/api/literature/pdf?first=1&last=1', data=text_pdf(),
                                                 headers={'Content-Type':'application/pdf', 'Origin':base,
                                                          'X-SciRAG-Token':config['token']})
                    with client.open(pdf, timeout=10) as response:
                        extraction = json.load(response)
                    assert extraction['page_count'] == 1 and extraction['pages'][0]['page'] == 1
                    assert extraction['text'] == 'Archive dates were independently recorded.'
                    print('PDF text and page number matched the original fixture.')
                    print(f"Verified {len(result['items'])} source offsets from the bundled collection and one from imported text. Markdown/RIS passed.")
                    if online:
                        real = search('crossref', 'distributional semantics word embeddings', limit=3)
                        assert real['items'] and all(p['url'] and p['quote'] for p in real['items'])
                        print(f"Crossref live search returned {len(real['items'])} works with evidence.")
                print('PASS: manifest, clean extract, private runtime, no keys, real CMD, HTTP, settings, empty history, occupied port, second launch.')
            finally:
                if proc.poll() is None:
                    # Only terminate the tree created by this test in its unique temp directory.
                    subprocess.run(['taskkill', '/pid', str(proc.pid), '/t', '/f'], stdout=subprocess.DEVNULL,
                                   check=False, creationflags=subprocess.CREATE_NO_WINDOW)
                    proc.wait(timeout=10)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('zip', type=Path)
    parser.add_argument('--startup-only', action='store_true', help='for pre-release launcher checks')
    parser.add_argument('--online', action='store_true', help='also query the public Crossref API once')
    args = parser.parse_args()
    validate(args.zip.resolve(), with_research=not args.startup_only, online=args.online)
