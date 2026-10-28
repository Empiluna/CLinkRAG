$ErrorActionPreference = 'Stop'
if (!(Get-Command uv -ErrorAction SilentlyContinue)) { throw 'uv is required to create the local environment.' }
$venv = Join-Path $PSScriptRoot '.venv'
$pythonExe = Join-Path $venv 'Scripts/python.exe'
$cache = Join-Path $PSScriptRoot '.cache/uv'
if (!(Test-Path -LiteralPath $pythonExe)) {
    uv venv --python 3.12 $venv
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
uv pip install --python $pythonExe --cache-dir $cache 'https://download.pytorch.org/whl/cu128/torch-2.8.0%2Bcu128-cp312-cp312-win_amd64.whl#sha256=0ad925202387f4e7314302a1b4f8860fa824357f9b1466d7992bf276370ebcff'
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
uv pip install --python $pythonExe --cache-dir $cache -r (Join-Path $PSScriptRoot 'requirements-windows.lock.txt')
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
$localConfig = Join-Path $PSScriptRoot 'config.local.yaml'
if (!(Test-Path -LiteralPath $localConfig)) {
    Copy-Item -LiteralPath (Join-Path $PSScriptRoot 'config.local.example.yaml') -Destination $localConfig
}
& $pythonExe (Join-Path $PSScriptRoot 'doctor.py')
exit $LASTEXITCODE
