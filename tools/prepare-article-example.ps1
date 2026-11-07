param([switch]$DownloadNew)
$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
Set-Location -LiteralPath $projectRoot
$python = Join-Path $projectRoot '.venv\Scripts\python.exe'
$selectionPath = Join-Path $projectRoot 'experiments\artifacts\example.json'
$env:FLOODSYSTEM_ENV = 'development'
$env:FLOODSYSTEM_DB_PATH = Join-Path $projectRoot 'database\article-simulations.db'
$env:FLOODSYSTEM_ENABLE_ARTICLE_SIMULATIONS = 'true'
$env:FLOODSYSTEM_REQUIRE_DEVICE_AUTH = 'false'
if ((Test-Path -LiteralPath $selectionPath) -and -not $DownloadNew) {
    $snapshotPath = (Get-Content -LiteralPath $selectionPath -Raw -Encoding UTF8 | ConvertFrom-Json).snapshot
    Write-Host 'Reutilizando a resposta original preservada.'
} else {
    Write-Host 'Obtendo ERA5 para Sao Paulo: 01 a 03/01/2025, dias de Brasilia.'
    $downloadOutput = & $python -m tools.weather_simulator download
    if ($LASTEXITCODE -ne 0) { throw 'Falha no download; nenhum ensaio preparado.' }
    $snapshotPath = (($downloadOutput -join "`n") | ConvertFrom-Json).snapshot
}
$prepareOutput = & $python -m backend.app.manage prepare-weather-experiment --snapshot $snapshotPath
if ($LASTEXITCODE -ne 0) { throw 'Falha ao preparar o ensaio.' }
$prepared = (($prepareOutput -join "`n") | ConvertFrom-Json)
@{ snapshot = $snapshotPath; run_id = $prepared.run_id; device_id = $prepared.device_id } |
    ConvertTo-Json | Set-Content -LiteralPath $selectionPath -Encoding UTF8
$prepared | Format-List
Write-Host 'Fonte importada e ensaio preparado. O envio de basculadas ocorre pelo script send-article-example.ps1.'
