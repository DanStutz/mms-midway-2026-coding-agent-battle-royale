param([int]$Port=8090)
$ErrorActionPreference='Stop'
$python=Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if(-not (Test-Path -LiteralPath $python)){throw 'Run SETUP.ps1 first.'}
$env:PYTHONUTF8='1'
$env:ARENA_PORT=[string]$Port
Write-Host "After startup, open http://127.0.0.1:$Port"
& $python (Join-Path $PSScriptRoot 'arena\server.py')
