$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
Set-Location -LiteralPath $projectRoot
$env:FLOODSYSTEM_ENV = 'development'
$env:FLOODSYSTEM_DB_PATH = Join-Path $projectRoot 'database\article-simulations.db'
$env:FLOODSYSTEM_ENABLE_ARTICLE_SIMULATIONS = 'true'
$env:FLOODSYSTEM_REQUIRE_DEVICE_AUTH = 'false'
Write-Host 'API exclusiva dos ensaios: http://127.0.0.1:8010'
Write-Host 'Banco: database/article-simulations.db'
& (Join-Path $projectRoot '.venv\Scripts\python.exe') -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8010
exit $LASTEXITCODE
