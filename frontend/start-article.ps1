$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$env:API_PROXY_TARGET = 'https://floodsystem.duckdns.org'
$env:ARTICLE_API_PROXY_TARGET = 'http://127.0.0.1:8010'
$env:VITE_API_BASE_URL = ''
$env:VITE_ARTICLE_MODE = 'false'
$env:VITE_EXPERIMENTS_ENABLED = 'true'
$env:VITE_DEFAULT_DEVICE_ID = 'esp32-01'
Write-Host 'FloodSystem integrado: http://127.0.0.1:5180/ (ensaios em /ensaios/)'
pnpm exec vite --host 127.0.0.1 --port 5180 --strictPort
exit $LASTEXITCODE
