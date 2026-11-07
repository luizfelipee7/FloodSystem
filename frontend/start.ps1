param([int]$Port = 5173)

# Usa o Node disponível no computador, com fallback para o runtime local.
$floodNodeCommand = Get-Command node -ErrorAction SilentlyContinue
$floodNode = if ($floodNodeCommand) { $floodNodeCommand.Source } else {
    Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe'
}
$floodVite = Join-Path $PSScriptRoot 'node_modules\vite\bin\vite.js'
if (-not (Test-Path -LiteralPath $floodNode)) {
    throw 'Node.js não encontrado. Consulte D:\FloodSystem\docs\frontend.md para preparar o ambiente.'
}
if (-not (Test-Path -LiteralPath $floodVite)) {
    throw 'Dependências do frontend não encontradas. Instale-as conforme docs/frontend.md.'
}
Push-Location $PSScriptRoot
try {
    & $floodNode $floodVite --host 127.0.0.1 --port $Port
} finally {
    Pop-Location
}
