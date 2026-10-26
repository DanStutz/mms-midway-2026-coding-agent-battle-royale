param([Parameter(Mandatory=$true)][ValidateSet('codex','opencode','pi')][string]$Harness)
$ErrorActionPreference='Stop'
$work=if($env:ARENA_DATA_DIR){$env:ARENA_DATA_DIR}else{Join-Path $PSScriptRoot '.arena'}
$cache=Join-Path $work 'npm-cache'
if ($Harness -eq 'codex') {
    codex login
    if ($LASTEXITCODE -eq 0) {codex login status}
    exit
}
if ($Harness -eq 'opencode') {
    $prefix=Join-Path $work 'opencode-tools'
    $bin=Join-Path $prefix 'node_modules\opencode-windows-x64\bin\opencode.exe'
    if (-not (Test-Path $bin)) {
        npm.cmd --cache $cache install --prefix $prefix opencode-ai@1.19.3 opencode-windows-x64@1.19.3 --ignore-scripts --no-audit --no-fund
        if ($LASTEXITCODE) {throw 'OpenCode installation failed'}
    }
    $env:XDG_DATA_HOME=Join-Path $work 'auth\opencode-data'
    $env:XDG_STATE_HOME=Join-Path $work 'auth\opencode-state'
    $env:XDG_CONFIG_HOME=Join-Path $work 'auth\opencode-config'
    & $bin auth login --provider openai --method 'ChatGPT Pro/Plus (browser)'
    exit
}
$prefix=Join-Path $work 'pi-tools'
$bin=Join-Path $prefix 'node_modules\.bin\pi.cmd'
if (-not (Test-Path $bin)) {
    npm.cmd --cache $cache install --prefix $prefix @earendil-works/pi-coding-agent@1.3.0 --ignore-scripts --no-audit --no-fund
    if ($LASTEXITCODE) {throw 'Pi installation failed'}
}
$env:PI_CODING_AGENT_DIR=Join-Path $work 'auth\pi'
Write-Host 'In Pi, type /login openai-codex, then choose Browser login (default).'
Write-Host 'Choose your own authorized workspace. After success, press Ctrl+C twice to exit.'
& $bin --offline --no-skills --no-extensions --no-context-files
