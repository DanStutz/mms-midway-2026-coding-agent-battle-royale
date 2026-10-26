param(
    [ValidateSet('check','pilot','conference','plan','validate','baseline','report','view')][string]$Mode='check',
    [string]$Model,
    [ValidateRange(1,20)][int]$Attempts=1,
    [ValidateSet('codex','opencode','pi')][string]$Harness,
    [switch]$DryRun,
    [int]$Port=8082
)
$ErrorActionPreference='Stop'
$py=Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $py)) { throw 'Run SETUP.ps1 first.' }
$harbor=Join-Path (Split-Path $py) 'harbor.exe'
if ($Mode -eq 'check') {
    & $py --version
    & $harbor --version
    docker info --format 'Docker engine: {{.OSType}} {{.ServerVersion}}'
    codex login status
    Write-Host 'OpenCode and Pi require their own native browser sign-ins. See LOGIN.ps1.'
    exit
}
if ($Mode -eq 'view') { $jobDir=if ($env:SHOWDOWN_JOBS_DIR) {$env:SHOWDOWN_JOBS_DIR} else {Join-Path $PSScriptRoot '.arena\jobs'}; if (-not (Test-Path -LiteralPath $jobDir)) {$jobDir=Join-Path $PSScriptRoot 'jobs'}; & $harbor view $jobDir --host 127.0.0.1 --port $Port; exit }
$action=if ($Mode -in 'pilot','conference') {'run'} else {$Mode}
$params=@((Join-Path $PSScriptRoot 'showdown.py'),$action)
if ($Mode -in 'pilot','conference','plan') {
    if (-not $Model) { throw 'Supply -Model with an exact model ID available in all three authenticated tools.' }
    $suite=if ($Mode -eq 'conference') {'conference'} else {'pilot'}
    $params+=@('--model',$Model,'--suite',$suite,'--attempts',[string]$Attempts)
    if ($Harness) {$params+=@('--harness',$Harness)}
}
if ($DryRun) {$params+='--dry-run'}
& $py @params
exit $LASTEXITCODE
