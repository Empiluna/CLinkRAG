param([int]$Port = 8765)
$ErrorActionPreference = 'Stop'
$pythonExe = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
if (!(Test-Path -LiteralPath $pythonExe)) {
    $pythonExe = Join-Path $PSScriptRoot 'runtime/python.exe'
}
if (!(Test-Path -LiteralPath $pythonExe)) { throw 'Extract the portable Windows release or install the local environment. See WINDOWS_RELEASE.md.' }
$env:PYTHONUTF8 = '1'
Write-Host "Open http://127.0.0.1:$Port in your browser. Press Ctrl+C to stop."
& $pythonExe (Join-Path $PSScriptRoot 'debug_ui/server.py') --port $Port
exit $LASTEXITCODE
