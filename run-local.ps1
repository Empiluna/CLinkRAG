param(
    [switch]$Check,
    [switch]$Live,
    [switch]$Test,
    [switch]$PrepareReranker,
    [string]$InputFile = '',
    [string]$OutputFile = '',
    [string]$Model = ''
)
$ErrorActionPreference = 'Stop'
$pythonExe = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
if (!(Test-Path -LiteralPath $pythonExe)) { throw 'Missing .venv. See RUN_LOCAL.md.' }
$env:PYTHONUTF8 = '1'
if ($Test) {
    & $pythonExe -m unittest discover -s (Join-Path $PSScriptRoot 'tests') -v
} elseif ($Check -or $Live -or $PrepareReranker) {
    $checkArgs = @((Join-Path $PSScriptRoot 'doctor.py'))
    if ($Live) { $checkArgs += '--live' }
    if ($PrepareReranker) { $checkArgs += '--prepare-reranker' }
    & $pythonExe @checkArgs
} else {
    if (!$InputFile) { $InputFile = Join-Path $PSScriptRoot 'examples/sample.jsonl' }
    if (!$OutputFile) { $OutputFile = Join-Path $PSScriptRoot ('results/run-' + (Get-Date -Format 'yyyyMMdd-HHmmss') + '.jsonl') }
    $runArgs = @((Join-Path $PSScriptRoot 'longans/run.py'), '--input_file', $InputFile, '--output_file', $OutputFile)
    if ($Model) { $runArgs += @('--model_name', $Model) }
    & $pythonExe @runArgs
    if ($LASTEXITCODE -eq 0) { Write-Output "Result: $OutputFile" }
}
exit $LASTEXITCODE
