$ErrorActionPreference='Stop'
$servers=@()
try {
    for ($i=0;$i -lt 3;$i++) {
        $label=@('A','B','C')[$i]
        $dir=Join-Path $PSScriptRoot "materials\blind\$label"
        if (-not (Test-Path (Join-Path $dir 'index.html'))) {throw 'Generate blind submissions with showdown.py blind --model YOUR_MODEL first.'}
        $port=8091+$i
        $args=@('-m','http.server',[string]$port,'--bind','127.0.0.1','--directory',('"'+$dir+'"'))
        $servers+=Start-Process -FilePath (Get-Command python).Source -ArgumentList $args -PassThru -WindowStyle Hidden
        Write-Host "$label : http://127.0.0.1:$port"
    }
    Write-Host 'Separate ports prevent one submission from sharing localStorage with another.'
    Read-Host 'Press Enter after the demo to stop these three local servers'
} finally {
    foreach ($server in $servers) {if (-not $server.HasExited) {Stop-Process -Id $server.Id}}
}
