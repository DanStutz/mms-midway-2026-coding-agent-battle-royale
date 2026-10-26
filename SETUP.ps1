$ErrorActionPreference='Stop'
$py=Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
python -c "import sys; assert sys.version_info >= (3,12), 'Python 3.12 or newer is required'"
if($LASTEXITCODE){throw 'Install Python 3.12 or newer and make python available in PowerShell.'}
if(-not (Test-Path -LiteralPath $py)){
    python -m venv (Join-Path $PSScriptRoot '.venv')
    if($LASTEXITCODE){throw 'Could not create Python environment'}
}
& $py -m pip install -r (Join-Path $PSScriptRoot 'requirements.txt')
if($LASTEXITCODE){throw 'Dependency installation failed'}
Write-Host 'Runtime ready. Start Docker Desktop, run PREPARE-ARENA.ps1, then START-ARENA.ps1.'
Write-Host 'For API-backed harnesses, connect your own keys in the local webpage. Native CLI sign-ins are optional.'
