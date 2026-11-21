"""Build a portable release from reviewed project files and a pinned CPython archive."""
import argparse
import hashlib
from importlib.metadata import distribution
import json
from pathlib import Path, PurePosixPath
import subprocess
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PYTHON_ZIP = 'python-3.14.10-embed-amd64.zip'
PYTHON_URL = 'https://www.python.org/ftp/python/3.14.10/' + PYTHON_ZIP
PYTHON_SHA = '90905e64a840557d8c1bc4f5b74db3d7ee85e3ffb217611cac1c7813acea4159'
PYPDF_WHEEL = 'pypdf-6.21.4-py3-none-any.whl'
PYPDF_SHA = '33e4fb41ca352810eb4e9838aa0d82d6888a5f8bf682f43e99cce5faa666255c'
PACKAGES = {'PyYAML': 'yaml', 'requests': 'requests', 'urllib3': 'urllib3',
            'idna': 'idna', 'charset-normalizer': 'charset_normalizer', 'certifi': 'certifi'}
EXCLUDED = {'.git', '.cache', '.venv', '__pycache__', '.agents', '.codex', '.aws',
            'results', 'node_modules', 'runtime', 'dist', 'config.local.yaml', 'config.yaml'}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def project_files(extra):
    output = subprocess.check_output(['git', 'ls-files', '-z'], cwd=ROOT)
    tracked = set(output.decode('utf-8').strip('\0').split('\0'))
    for name in sorted(tracked | set(extra)):
        path = PurePosixPath(name)
        if (path.is_absolute() or '..' in path.parts or '\\' in name or ':' in name or
                any(part.lower() in EXCLUDED or part.lower().startswith('.env') for part in path.parts)
                or path.suffix.lower() in {'.pyc', '.pem', '.key', '.pfx', '.zip'}):
            if name in extra:
                raise ValueError(f'Cannot package this path: {name}')
            continue
        src = ROOT.joinpath(*path.parts)
        if src.is_file() and src.resolve().is_relative_to(ROOT):
            yield name, src.read_bytes()


def runtime_files(cache):
    cache.mkdir(parents=True, exist_ok=True)
    archive = cache / PYTHON_ZIP
    if not archive.is_file():
        with urllib.request.urlopen(PYTHON_URL, timeout=60) as r:
            content = r.read()
        if sha(content) != PYTHON_SHA:
            raise ValueError('Downloaded Python archive failed its SHA-256 check')
        archive.write_bytes(content)
    if sha(archive.read_bytes()) != PYTHON_SHA:
        raise ValueError('Cached Python archive failed its SHA-256 check')
    with zipfile.ZipFile(archive) as runtime:
        for name in runtime.namelist():
            if name.endswith('/'):
                continue
            data = runtime.read(name)
            if name == 'python314._pth':
                data = b'python314.zip\r\n.\r\nvendor\r\n'
            yield 'runtime/' + name, data


def vendor_files():
    # Keep pure Python modules, CA data and upstream license notices. Native
    # extension accelerators from the builder's ABI cannot be copied to 3.14.
    lock = dict(line.split('==') for line in
                (ROOT / 'requirements-windows.lock.txt').read_text().splitlines()
                if '==' in line and not line.startswith('#'))
    for package, module in PACKAGES.items():
        dist = distribution(package)
        if dist.version != lock[package.lower()]:
            raise ValueError(f'{package} {dist.version} differs from the Windows lockfile')
        licensed = False
        for file in dist.files or []:
            name = file.as_posix()
            path = PurePosixPath(name)
            base = path.parts[0]
            if base == module and path.suffix in ('.py', '.pem', '.typed'):
                yield 'runtime/vendor/' + name, file.locate().read_bytes()
            elif base.endswith('.dist-info'):
                notice = path.name.upper().startswith(('LICENSE', 'COPYING', 'NOTICE'))
                if notice or path.name == 'METADATA':
                    licensed |= notice
                    yield 'runtime/vendor/' + name, file.locate().read_bytes()
        if not licensed:
            raise ValueError(f'Missing license notice for {package}')
    wheel = ROOT / '.cache' / 'portable' / PYPDF_WHEEL
    if not wheel.is_file():
        with urllib.request.urlopen('https://pypi.org/pypi/pypdf/6.21.4/json', timeout=30) as response:
            metadata = json.load(response)
        artifact = next(f for f in metadata['urls'] if f['filename'] == PYPDF_WHEEL)
        with urllib.request.urlopen(artifact['url'], timeout=60) as response:
            data = response.read()
        if sha(data) != PYPDF_SHA:
            raise ValueError('Downloaded pypdf wheel failed its SHA-256 check')
        wheel.write_bytes(data)
    if sha(wheel.read_bytes()) != PYPDF_SHA:
        raise ValueError('Cached pypdf wheel failed its SHA-256 check')
    with zipfile.ZipFile(wheel) as source:
        for name in source.namelist():
            if name.startswith('pypdf/') or name.endswith(('/LICENSE', '/METADATA')):
                yield 'runtime/vendor/' + name, source.read(name)


def write_zip(output, extra):
    manifest = {}
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix('.building')
    with zipfile.ZipFile(temporary, 'w') as archive:
        def write(name, data):
            info = zipfile.ZipInfo('CLinkRAG/' + name, date_time=(2026, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, data)
            manifest[name] = sha(data)
        for generate in (project_files(extra), runtime_files(ROOT / '.cache' / 'portable'), vendor_files()):
            for name, content in generate:
                if name in manifest:
                    raise ValueError(f'Duplicate release member: {name}')
                write(name, content)
        for name in ('Start-CLinkRAG.cmd', 'tools/launch.py', 'debug_ui/server.py', 'runtime/LICENSE.txt'):
            if name not in manifest:
                raise ValueError(f'Missing mandatory release member: {name}')
        write('FILES.sha256.json', json.dumps(manifest, ensure_ascii=False, indent=2,
                                               sort_keys=True).encode('utf-8'))
    temporary.replace(output)
    digest = sha(output.read_bytes())
    output.with_suffix('.sha256').write_text(f'{digest}  {output.name}\n', encoding='ascii')
    print(f'{output}  {output.stat().st_size:,} bytes  SHA-256 {digest}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=ROOT.parent / 'CLinkRAG-Windows-x64.zip')
    parser.add_argument('--include', action='append', default=[],
                        help='explicit reviewed project-relative file, for pre-commit package tests')
    args = parser.parse_args()
    write_zip(args.output.resolve(), args.include)
