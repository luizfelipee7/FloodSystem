[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^\d{4}-\d{2}-\d{2}$')]
    [string]$DataBrasilia
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$sshExe = Join-Path $env:WINDIR 'System32\OpenSSH\ssh.exe'
$keyPath = 'D:\FloodSystem\PrivateKey\ssh-key-2026-10-06.key'
$target = 'ubuntu@168.75.66.112'
$dbPath = '/srv/floodsystem/database/production.db'
$backupTool = '/srv/floodsystem/deploy/sqlite_backup.py'
$backupDirectory = '/var/backups/floodsystem'

if (-not (Test-Path -LiteralPath $sshExe)) {
    throw "Cliente OpenSSH não encontrado: $sshExe"
}
if (-not (Test-Path -LiteralPath $keyPath -PathType Leaf)) {
    throw "Chave SSH não encontrada no caminho configurado: $keyPath"
}

$sshArgs = @('-T', '-i', $keyPath, '-o', 'BatchMode=yes', $target)

function Invoke-FloodVm {
    param(
        [Parameter(Mandatory = $true)] [string]$Command,
        [string]$StdinText
    )

    if ($PSBoundParameters.ContainsKey('StdinText')) {
        $result = $StdinText | & $sshExe @sshArgs $Command
    } else {
        $result = & $sshExe @sshArgs $Command
    }
    if ($LASTEXITCODE -ne 0) {
        throw "Comando remoto falhou (código $LASTEXITCODE): $Command"
    }
    return [string]::Join([Environment]::NewLine, @($result))
}

$culture = [Globalization.CultureInfo]::InvariantCulture
$day = [datetime]::ParseExact($DataBrasilia, 'yyyy-MM-dd', $culture)
$brasiliaOffset = [TimeSpan]::FromHours(-3)
$startLocal = [DateTimeOffset]::new(
    $day.Year, $day.Month, $day.Day, 0, 0, 0, $brasiliaOffset
)
$endLocal = $startLocal.AddDays(1)
$startUtc = $startLocal.UtcDateTime.ToString("yyyy-MM-dd'T'HH:mm:ss.ffffff'Z'", $culture)
$endUtc = $endLocal.UtcDateTime.ToString("yyyy-MM-dd'T'HH:mm:ss.ffffff'Z'", $culture)
$startJson = ConvertTo-Json -InputObject $startUtc -Compress
$endJson = ConvertTo-Json -InputObject $endUtc -Compress

$preflightScript = @'
import json
import sqlite3

db = "file:/srv/floodsystem/database/production.db?mode=ro"
start = __START__
end = __END__
con = sqlite3.connect(db, uri=True)
try:
    result = {}
    for table, name, time_column in (
        ("rain_tip_events", "rain", "occurred_at"),
        ("level_readings", "level", "measured_at"),
    ):
        row = con.execute(
            f"SELECT COUNT(*), MIN({time_column}), MAX({time_column}) "
            f"FROM {table} "
            f"WHERE device_id = ? AND origin = ? AND {time_column} >= ? AND {time_column} < ?",
            ("esp32-01", "esp32", start, end),
        ).fetchone()
        result[name] = {"count": row[0], "first": row[1], "last": row[2]}
    print(json.dumps(result))
finally:
    con.close()
'@
$preflightScript = $preflightScript.Replace('__START__', $startJson).Replace('__END__', $endJson)

Write-Host "Conferindo dados ESP32 medidos em $DataBrasilia (horário de Brasília)..."
$preflightOutput = Invoke-FloodVm -Command 'sudo python3 -' -StdinText $preflightScript
$jsonLine = ($preflightOutput -split '\r?\n' | Where-Object { $_.Trim() } | Select-Object -Last 1)
$summary = $jsonLine | ConvertFrom-Json

Write-Host "Basculadas encontradas: $($summary.rain.count)"
Write-Host "Leituras de nível encontradas: $($summary.level.count)"
if ($summary.rain.count -gt 0) {
    Write-Host "Primeira basculada: $($summary.rain.first)"
    Write-Host "Última basculada:   $($summary.rain.last)"
}
if ($summary.level.count -gt 0) {
    Write-Host "Primeira leitura de nível: $($summary.level.first)"
    Write-Host "Última leitura de nível:   $($summary.level.last)"
}
Write-Warning 'A API não distingue ensaios manuais de medições reais. A confirmação apagará TODAS as basculadas e leituras de nível ESP32 desse dispositivo medidas no dia escolhido.'

$totalCount = [int]$summary.rain.count + [int]$summary.level.count
if ($totalCount -eq 0) {
    Write-Host 'Nenhum dado para apagar. A VM não foi alterada.'
    return
}

$confirmation = Read-Host "Para continuar, digite APAGAR $totalCount"
if ($confirmation -cne "APAGAR $totalCount") {
    Write-Host 'Cancelado. Nenhum dado foi apagado e a API não foi parada.'
    return
}

$stopped = $false
try {
    Write-Host 'Parando a API para evitar gravações simultâneas...'
    Invoke-FloodVm -Command 'sudo systemctl stop floodsystem-api' | Out-Host
    $stopped = $true

    Write-Host 'Criando backup antes da exclusão...'
    Invoke-FloodVm -Command "sudo python3 $backupTool backup $dbPath $backupDirectory" | Out-Host

    $deleteScript = @'
import sqlite3

db = "/srv/floodsystem/database/production.db"
start = __START__
end = __END__
expected_rain = __EXPECTED_RAIN__
expected_level = __EXPECTED_LEVEL__
params = ("esp32-01", "esp32", start, end)
con = sqlite3.connect(db, timeout=30)
try:
    con.execute("BEGIN IMMEDIATE")
    deleted = {}
    for table, time_column, expected in (
        ("rain_tip_events", "occurred_at", expected_rain),
        ("level_readings", "measured_at", expected_level),
    ):
        where = f"device_id = ? AND origin = ? AND {time_column} >= ? AND {time_column} < ?"
        before = con.execute("SELECT COUNT(*) FROM " + table + " WHERE " + where, params).fetchone()[0]
        if before != expected:
            raise RuntimeError(f"A quantidade em {table} mudou ({before}); cancelando a exclusão.")
        deleted[table] = con.execute("DELETE FROM " + table + " WHERE " + where, params).rowcount
        remaining = con.execute("SELECT COUNT(*) FROM " + table + " WHERE " + where, params).fetchone()[0]
        if deleted[table] != expected or remaining != 0:
            raise RuntimeError(f"A conferência de {table} falhou; cancelando a transação.")
    con.commit()
    print(f"basculadas_apagadas={deleted['rain_tip_events']}; niveis_apagados={deleted['level_readings']}")
except Exception:
    con.rollback()
    raise
finally:
    con.close()
'@
    $deleteScript = $deleteScript.Replace('__START__', $startJson).Replace('__END__', $endJson).Replace('__EXPECTED_RAIN__', [string]$summary.rain.count).Replace('__EXPECTED_LEVEL__', [string]$summary.level.count)
    Invoke-FloodVm -Command 'sudo python3 -' -StdinText $deleteScript | Out-Host
}
finally {
    if ($stopped) {
        Write-Host 'Reiniciando a API...'
        Invoke-FloodVm -Command 'sudo systemctl start floodsystem-api' | Out-Host
    }
}

Write-Host 'Conferindo API e banco...'
Invoke-FloodVm -Command 'systemctl is-active floodsystem-api && curl --fail --silent --show-error https://floodsystem.duckdns.org/health' | Out-Host
$after = Invoke-FloodVm -Command 'sudo python3 -' -StdinText $preflightScript
$afterLine = ($after -split '\r?\n' | Where-Object { $_.Trim() } | Select-Object -Last 1)
$afterSummary = $afterLine | ConvertFrom-Json
if ($afterSummary.rain.count -ne 0 -or $afterSummary.level.count -ne 0) {
    throw "A verificação final encontrou $($afterSummary.rain.count) basculadas e $($afterSummary.level.count) leituras de nível restantes para esse dia."
}
Write-Host "Concluído: basculadas e leituras de nível ESP32 medidas em $DataBrasilia = 0."
