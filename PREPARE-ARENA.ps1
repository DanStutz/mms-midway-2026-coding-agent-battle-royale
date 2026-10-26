param()
$ErrorActionPreference='Stop'
$docker=Get-Command docker -ErrorAction SilentlyContinue
if(-not $docker){throw 'Install Docker Desktop and open a new PowerShell window.'}
& $docker.Source info --format '{{.OSType}}'
if($LASTEXITCODE -ne 0){throw 'Start Docker Desktop and wait for its Linux engine.'}
Write-Host 'Preparing the Arena tools image. This one-time step can take several minutes; no model calls are made.'
& $docker.Source build -f (Join-Path $PSScriptRoot 'arena/Dockerfile.tools') -t agent-arena-tools:20261026-nine (Join-Path $PSScriptRoot 'arena')
if($LASTEXITCODE -ne 0){throw 'Tools image preparation failed. Review the Docker build output above.'}
Write-Host 'Arena tools are ready. Start the Arena with START-ARENA.ps1.'
