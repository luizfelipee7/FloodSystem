$ErrorActionPreference = 'Stop'
$projectRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
Set-Location -LiteralPath $projectRoot
$selectionPath = Join-Path $projectRoot 'experiments\artifacts\example.json'
if (-not (Test-Path -LiteralPath $selectionPath)) { throw 'Execute primeiro tools/prepare-article-example.ps1.' }
$selected = Get-Content -LiteralPath $selectionPath -Raw -Encoding UTF8 | ConvertFrom-Json
& (Join-Path $projectRoot '.venv\Scripts\python.exe') -m tools.weather_simulator send --snapshot $selected.snapshot --base-url 'http://127.0.0.1:8010'
if ($LASTEXITCODE -ne 0) { throw 'Envio incompleto; mantenha a API dos ensaios aberta e repita este comando.' }
