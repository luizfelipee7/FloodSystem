$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot

# The built site remains local; only its /api requests use the published API.
$env:API_PROXY_TARGET = 'https://floodsystem.duckdns.org'
pnpm run preview
