"""Reproducible, offline article figures and sensitivity cases.

No network, API writes, physical telemetry, or SQLite mutation. The published
experiment remains unchanged; alternate cases are explicitly computational.
"""

import argparse
import csv
import hashlib
import io
import json
import sqlite3
import zipfile
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_EVEN
from pathlib import Path

from .model import K, generate, instant, normalize, text_decimal, timestamp
from .source import read_snapshot

MICROSECONDS_PER_HOUR = Decimal(3_600_000_000)
PROFILES = {
    "uniform_hour": (Decimal(0), MICROSECONDS_PER_HOUR),
    "first_15_minutes": (Decimal(0), Decimal(900_000_000)),
    "last_15_minutes": (Decimal(2_700_000_000), Decimal(900_000_000)),
}


def _csv_bytes(rows, fields):
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=fields, delimiter=";", lineterminator="\n")
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8-sig")


def _simulate(intervals, k, profile):
    """Apply the same residual rule to a series without modifying the source."""
    if not k.is_finite() or k <= 0 or profile not in PROFILES:
        raise ValueError("K ou perfil temporal inválido.")
    start_offset, span = PROFILES[profile]
    residual = Decimal(0)
    source_total = Decimal(0)
    rows, events = [], []
    for interval in intervals:
        rain = Decimal(interval["rain_mm"])
        if not rain.is_finite() or rain < 0:
            raise ValueError("Chuva sintética inválida.")
        before = residual
        count = int((before + rain) // k)
        if len(events) + count > 100_000:
            raise ValueError("Mais de 100.000 eventos; reduza a série.")
        hour_start = instant(interval["start"])
        for j in range(count):
            fraction = ((j + 1) * k - before) / rain
            offset = int((start_offset + fraction * span).to_integral_value(rounding=ROUND_HALF_EVEN))
            offset = max(0, min(offset, 3_599_999_999))
            events.append({"interval_index": interval["index"],
                           "occurred_at": timestamp(hour_start + timedelta(microseconds=offset))})
        residual = before + rain - count * k
        if not Decimal(0) <= residual < k:
            raise AssertionError("Residual fora do intervalo [0, K).")
        source_total += rain
        rows.append({"interval_index": interval["index"], "start_at": interval["start"],
                     "end_at": interval["end"], "source_time": interval["source_time"],
                     "rain_mm": text_decimal(rain), "tip_count": count,
                     "represented_mm": text_decimal(count * k),
                     "residual_before_mm": text_decimal(before),
                     "residual_after_mm": text_decimal(residual)})
    represented = len(events) * k
    if source_total != represented + residual:
        raise AssertionError("Balanço global não fecha.")
    return rows, events, source_total, represented, residual


def _peak_five_minute_intensity(events, k):
    """Largest half-open 5-minute window starting at a simulated event."""
    if not events:
        return Decimal(0)
    times = sorted(instant(event["occurred_at"]) for event in events)
    right, maximum = 0, 0
    for left, at in enumerate(times):
        right = max(right, left)
        while right < len(times) and times[right] < at + timedelta(minutes=5):
            right += 1
        maximum = max(maximum, right - left)
    return Decimal(maximum) * k * 12


def _case(case_id, kind, intervals, k, profile):
    hourly, events, source, represented, residual = _simulate(intervals, k, profile)
    rainy = sum(Decimal(row["rain_mm"]) > 0 for row in hourly)
    summary = {"case_id": case_id, "input_kind": kind, "k_mm_per_tip": text_decimal(k),
               "intrahour_profile": profile, "hours": len(hourly), "rainy_hours": rainy,
               "source_total_mm": text_decimal(source), "tip_count": len(events),
               "represented_mm": text_decimal(represented),
               "final_residual_mm": text_decimal(residual),
               "peak_simulated_5min_mm_h": text_decimal(_peak_five_minute_intensity(events, k)),
               "first_tip_at": events[0]["occurred_at"] if events else ""}
    return summary, hourly, events


def _idealized(base, amounts):
    if len(base) != len(amounts):
        raise ValueError("Série idealizada com tamanho diferente da série de referência.")
    return [{**row, "rain_mm": text_decimal(amount)} for row, amount in zip(base, amounts)]


def _audit_export(path, manifest, raw, baseline):
    """Check the existing published export against a fresh pure generation."""
    with zipfile.ZipFile(path) as archive:
        required = {"source-response.json", "source-manifest.json", "experiment.json",
                    "hourly-comparison.csv", "simulated-events.csv", "README.txt"}
        if set(archive.namelist()) != required:
            raise ValueError("O ZIP publicado não contém exatamente os seis arquivos esperados.")
        if archive.read("source-response.json") != raw:
            raise ValueError("Resposta original do ZIP difere do snapshot.")
        if json.loads(archive.read("source-manifest.json")) != manifest:
            raise ValueError("Manifesto do ZIP difere do snapshot.")
        hourly = list(csv.DictReader(io.StringIO(archive.read("hourly-comparison.csv").decode("utf-8-sig")), delimiter=";"))
        events = list(csv.DictReader(io.StringIO(archive.read("simulated-events.csv").decode("utf-8-sig")), delimiter=";"))
        if len(hourly) != len(baseline["intervals"]) or len(events) != len(baseline["events"]):
            raise ValueError("Contagens do ZIP e da geração independente divergem.")
        for exported, expected in zip(hourly, baseline["intervals"]):
            for a, b in (("interval_index", "index"), ("start_at", "start"),
                         ("end_at", "end"), ("source_time", "source_time"),
                         ("rain_mm", "rain_mm"), ("residual_after_mm", "residual_after_mm"),
                         ("expected_tip_count", "expected_tip_count")):
                if str(exported[a]) != str(expected[b]):
                    raise ValueError(f"Divergência no ZIP, hora {expected['index']}, campo {a}.")
        for exported, expected in zip(events, baseline["events"]):
            for field in ("event_id", "occurred_at", "interval_index"):
                if str(exported[field]) != str(expected[field]):
                    raise ValueError(f"Divergência de evento no ZIP: {field}.")
        if any(item["origin"] != "simulation" for item in events):
            raise ValueError("Origem inesperada no ZIP.")
        return {"status": "matched", "hourly_rows": len(hourly), "event_rows": len(events),
                "archive_sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest()}


def _audit_sqlite(path, baseline, raw):
    """Read-only check of the local scientific database, never the physical DB."""
    expected_name = "article-simulations.db"
    if Path(path).name != expected_name:
        raise ValueError(f"Somente o banco científico {expected_name} pode ser auditado.")
    uri = Path(path).resolve().as_uri() + "?mode=ro&immutable=1"
    connection = sqlite3.connect(uri, uri=True)
    try:
        row = connection.execute(
            "SELECT dataset_id, device_id, expected_tip_count, source_total_mm, final_residual_mm "
            "FROM simulation_runs WHERE run_id=?", (baseline["run_id"],)).fetchone()
        if row is None or row[0] != baseline["dataset_id"] or row[1] != baseline["device_id"]:
            raise ValueError("Execução não encontrada no SQLite científico.")
        if (row[2], Decimal(row[3]), Decimal(row[4])) != (
                len(baseline["events"]), Decimal(baseline["source_total_mm"]),
                Decimal(baseline["final_residual_mm"])):
            raise ValueError("Resumo do SQLite diverge da geração.")
        source = connection.execute("SELECT raw_response FROM weather_datasets WHERE dataset_id=?",
                                    (baseline["dataset_id"],)).fetchone()
        if source is None or source[0] != raw:
            raise ValueError("Fonte armazenada no SQLite difere do snapshot.")
        actual = connection.execute(
            "SELECT t.event_id, t.occurred_at FROM rain_tip_events t "
            "WHERE t.device_id=? ORDER BY t.occurred_at, t.event_id", (baseline["device_id"],)).fetchall()
        expected = sorted(((event["event_id"], event["occurred_at"]) for event in baseline["events"]),
                          key=lambda x: (x[1], x[0]))
        if actual != expected:
            raise ValueError("Eventos no SQLite científico divergem da geração.")
        return {"status": "matched", "run_id": baseline["run_id"], "stored_events": len(actual),
                "scientific_db_sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest()}
    finally:
        connection.close()


def _plot(output, baseline_hourly, summaries):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError as exc:
        raise RuntimeError("Instale as dependências de tools/weather_simulator/requirements-analysis.txt.") from exc

    x = list(range(len(baseline_hourly)))
    rain = [float(row["rain_mm"]) for row in baseline_hourly]
    represented = [float(row["represented_mm"]) for row in baseline_hourly]
    residual = [float(row["residual_after_mm"]) for row in baseline_hourly]
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "savefig.dpi": 200})
    fig, ax = plt.subplots(figsize=(10, 4))
    ax.bar(x, rain, width=.85, color="#287dba", label="ERA5: chuva por hora")
    tip_hours = [(index, amount) for index, amount in enumerate(represented) if amount > 0]
    ax.scatter([item[0] for item in tip_hours], [item[1] for item in tip_hours],
               s=38, color="#c34d38", label="Chuva em basculadas simuladas", zorder=3)
    ax.set(xlabel="Hora desde 01/01/2025 00h (Brasília)", ylabel="Precipitação (mm por hora)")
    ax.set_xlim(-1, len(x)); ax.grid(axis="y", alpha=.25); ax.legend(frameon=False)
    fig.tight_layout()
    for ext in ("png", "svg"):
        fig.savefig(output / f"figura-chuva-eventos.{ext}")
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(10, 3.7))
    ax.step(x, residual, where="post", color="#2b7d68", linewidth=2, label="Residual simulado")
    ax.axhline(float(K), linestyle="--", color="#9b5c2b", label="K = 2,17 mm")
    ax.set(xlabel="Hora desde 01/01/2025 00h (Brasília)", ylabel="Residual (mm)")
    ax.set_xlim(-1, len(x)); ax.set_ylim(bottom=0); ax.grid(axis="y", alpha=.25); ax.legend(frameon=False)
    fig.tight_layout()
    for ext in ("png", "svg"):
        fig.savefig(output / f"figura-residual.{ext}")
    plt.close(fig)

    sensitivity = [row for row in summaries if row["case_id"] in
                   ("era5_k_minus_10pct", "era5_reference", "era5_k_plus_10pct")]
    sensitivity.sort(key=lambda row: Decimal(row["k_mm_per_tip"]))
    fig, ax = plt.subplots(figsize=(7, 4))
    xs = [float(row["k_mm_per_tip"]) for row in sensitivity]
    ys = [int(row["tip_count"]) for row in sensitivity]
    ax.scatter(xs, ys, s=65, color="#514c9e", zorder=3)
    for x_value, y_value, row in zip(xs, ys, sensitivity):
        ax.annotate(f"residual {row['final_residual_mm']} mm", (x_value, y_value),
                    xytext=(0, 11), textcoords="offset points", ha="center", fontsize=8)
    ax.set(xlabel="K hipotético (mm por basculada)", ylabel="Basculadas simuladas")
    ax.set_xticks(xs); ax.set_xlim(min(xs) - .12, max(xs) + .12)
    ax.set_ylim(0, max(ys) + 2); ax.grid(alpha=.25)
    fig.tight_layout()
    for ext in ("png", "svg"):
        fig.savefig(output / f"figura-sensibilidade-k.{ext}")
    plt.close(fig)


def build(snapshot, output, published_export=None, scientific_db=None):
    output = Path(output)
    if output.exists():
        raise FileExistsError(f"Pasta de saída já existe: {output}. Use outra pasta para preservar a execução.")
    manifest, raw = read_snapshot(snapshot)
    baseline = generate(manifest, raw)
    intervals, _ = normalize(manifest, raw)
    if len(intervals) != 72:
        raise ValueError("Esta análise predefinida exige as 72 horas do exemplo original.")
    total = sum((Decimal(row["rain_mm"]) for row in intervals), Decimal(0))
    if total != Decimal("14.5"):
        raise ValueError("Esta análise predefinida exige o snapshot original de 14,50 mm.")
    base_k = Decimal(K)
    zeros = [Decimal(0)] * len(intervals)
    steady = [Decimal("0.5") if i < 29 else Decimal(0) for i in range(len(intervals))]
    burst = [total if i == 36 else Decimal(0) for i in range(len(intervals))]
    cases = [
        ("era5_reference", "ERA5 reanalysis", intervals, base_k, "uniform_hour"),
        ("era5_k_minus_10pct", "ERA5 reanalysis", intervals, base_k * Decimal("0.9"), "uniform_hour"),
        ("era5_k_plus_10pct", "ERA5 reanalysis", intervals, base_k * Decimal("1.1"), "uniform_hour"),
        ("era5_first_15m", "ERA5 reanalysis + temporal assumption", intervals, base_k, "first_15_minutes"),
        ("era5_last_15m", "ERA5 reanalysis + temporal assumption", intervals, base_k, "last_15_minutes"),
        ("idealized_dry", "fully synthetic", _idealized(intervals, zeros), base_k, "uniform_hour"),
        ("idealized_steady", "fully synthetic", _idealized(intervals, steady), base_k, "uniform_hour"),
        ("idealized_burst", "fully synthetic", _idealized(intervals, burst), base_k, "uniform_hour"),
    ]
    summaries, hourly_all, events_all = [], [], []
    baseline_hourly = None
    for case_id, kind, series, k, profile in cases:
        summary, hourly, events = _case(case_id, kind, series, k, profile)
        summaries.append(summary)
        hourly_all.extend({"case_id": case_id, **row} for row in hourly)
        events_all.extend({"case_id": case_id, "event_index": i, **event}
                          for i, event in enumerate(events))
        if case_id == "era5_reference":
            baseline_hourly = hourly
            if len(events) != len(baseline["events"]) or any(
                    a["occurred_at"] != b["occurred_at"] for a, b in zip(events, baseline["events"])):
                raise AssertionError("A reprodução da condição-base diverge do gerador publicado.")

    checks = {"source_sha256_matches_manifest": hashlib.sha256(raw).hexdigest() == manifest["response_sha256"],
              "source_hours": len(intervals), "rainy_hours": sum(Decimal(r["rain_mm"]) > 0 for r in intervals),
              "baseline_run_id": baseline["run_id"], "all_cases_balance_and_residual_checked": True}
    if published_export:
        checks["published_export"] = _audit_export(published_export, manifest, raw, baseline)
    if scientific_db:
        checks["local_scientific_sqlite"] = _audit_sqlite(scientific_db, baseline, raw)

    output.mkdir(parents=True)
    (output / "case-summary.csv").write_bytes(_csv_bytes(summaries, list(summaries[0])))
    (output / "hourly-cases.csv").write_bytes(_csv_bytes(hourly_all, list(hourly_all[0])))
    (output / "simulated-events-cases.csv").write_bytes(_csv_bytes(events_all, list(events_all[0])))
    (output / "audit.json").write_text(json.dumps(checks, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _plot(output, baseline_hourly, summaries)

    def table(ids):
        rows = [next(item for item in summaries if item["case_id"] == key) for key in ids]
        header = "| Cenário | K (mm) | Horas com chuva | Eventos | Representado (mm) | Residual (mm) | Pico sintético 5 min (mm/h) |\n"
        header += "| --- | ---: | ---: | ---: | ---: | ---: | ---: |\n"
        return header + "".join(
            f"| `{r['case_id']}` | {r['k_mm_per_tip']} | {r['rainy_hours']} | {r['tip_count']} | "
            f"{r['represented_mm']} | {r['final_residual_mm']} | {r['peak_simulated_5min_mm_h']} |\n"
            for r in rows)

    def temporal_table():
        keys = ["era5_first_15m", "era5_reference", "era5_last_15m"]
        rows = [next(item for item in summaries if item["case_id"] == key) for key in keys]
        return ("| Hipótese | Primeiro evento simulado (UTC) | Eventos | Pico sintético 5 min (mm/h) |\n"
                "| --- | --- | ---: | ---: |\n" + "".join(
                    f"| `{row['intrahour_profile']}` | {row['first_tip_at']} | {row['tip_count']} | "
                    f"{row['peak_simulated_5min_mm_h']} |\n" for row in rows))

    report = f"""# Resultados computacionais complementares para o artigo FloodSystem

**Natureza:** análise computacional offline, sem novos ensaios físicos nem dados de nível.  
**Fonte preservada:** Open-Meteo/ERA5, variável `rain`, {len(intervals)} horas, SHA-256 `{manifest['response_sha256']}`.  
**Execução original:** `{baseline['run_id']}`. O JSON original e o manifesto continuam na pasta do snapshot, sem alteração.

## Método e limites

O horário `t` da variável `rain` é a soma da hora precedente `[t−1 h, t)`. Em cada hora, o algoritmo soma chuva e residual anterior, emite `floor(disponível/K)` eventos e transporta o residual. A condição-base reproduz o gerador publicado. Três cenários adicionais são **totalmente idealizados**: ausência de chuva, 0,5 mm/h nas primeiras 29 horas e 14,5 mm concentrados na hora 37. Os dois últimos preservam os 14,5 mm totais da condição-base, mas não provêm da ERA5. A variação de K em ±10% é **exploratória**; não representa intervalo de confiança da calibração. As hipóteses `first_15_minutes` e `last_15_minutes` colocam a chuva de cada hora uniformemente no primeiro ou último quarto de hora, respectivamente. Todas as basculadas e intensidades de cinco minutos dessas variantes são sintéticas.

## Condição-base e cenários contrastantes

{table(['era5_reference', 'idealized_dry', 'idealized_steady', 'idealized_burst'])}

## Sensibilidade ilustrativa à resolução K

{table(['era5_k_minus_10pct', 'era5_reference', 'era5_k_plus_10pct'])}

## Sensibilidade à distribuição dentro da hora

{temporal_table()}

Mudanças de distribuição dentro da hora **não alteram o total horário, a quantidade final de eventos ou o residual** quando K e a série horária permanecem iguais. Neste recorte, o primeiro evento varia de 16:10:03Z a 16:55:03Z, enquanto o pico calculado em cinco minutos permanece igual nos três perfis. Em outros recortes, esse pico também pode mudar. O pico apresentado é o maior valor em janelas semiabertas de cinco minutos iniciadas em cada evento simulado; **não é uma observação meteorológica de cinco minutos**. Com zero eventos no cenário seco controlado, zero chuva é conhecido por construção. A mesma conclusão não vale para um período físico sem eventos recebidos.

## Auditoria da condição-base

- Hash da resposta original igual ao manifesto: `{checks['source_sha256_matches_manifest']}`.
- Horas completas no recorte: **{checks['source_hours']}**; horas com chuva positiva: **{checks['rainy_hours']}**.
- Balanço e `0 ≤ residual < K` conferidos para os oito casos gerados.
- ZIP publicado: **{checks.get('published_export', {}).get('status', 'não fornecido')}**; comparação de horas/eventos com nova execução determinística do gerador do projeto.
- SQLite científico local: **{checks.get('local_scientific_sqlite', {}).get('status', 'não fornecido')}**; acesso somente leitura. A verificação não substitui auditoria de logs de rede/ESP32.

## Arquivos desta execução

- `case-summary.csv`: resumo dos oito casos.
- `hourly-cases.csv`: todas as séries horárias e resíduos, com identificação do caso.
- `simulated-events-cases.csv`: timestamps de todas as viradas sintéticas.
- `audit.json`: conferências efetuadas e identificação da execução original.
- `figura-chuva-eventos.png/.svg`, `figura-residual.png/.svg`, `figura-sensibilidade-k.png/.svg`: figuras exportáveis para o artigo.
- `manifest.json`: parâmetros, proveniência e hashes de todos os arquivos acima.

**Uso no manuscrito:** estes resultados permitem descrever robustez computacional sob condições controladas. Não sustentam precisão física do pluviômetro, medição residencial, nível da água, alerta antecipado ou prevenção de enchentes. O autor deve selecionar as tabelas e figuras relevantes e manter a identificação da origem de cada série.
"""
    (output / "report.md").write_text(report, encoding="utf-8")
    files = sorted(p for p in output.iterdir() if p.is_file())
    import matplotlib
    metadata = {"analysis_version": "article-analysis-v1", "baseline_run_id": baseline["run_id"],
                "source_response_sha256": manifest["response_sha256"],
                "source_model": "ERA5 via Open-Meteo", "source_variable": "rain",
                "source_time_rule": "preceding hour [t-1h,t)", "case_count": len(summaries),
                "analysis_code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "matplotlib_version": matplotlib.__version__,
                "case_definitions": {"dry": "72 hours zero", "steady": "0.5 mm/h for first 29 hours",
                                     "burst": "14.5 mm in interval index 36", "k_minus_10pct": "1.953 mm/tip",
                                     "k_plus_10pct": "2.387 mm/tip",
                                     "temporal_profiles": list(PROFILES)},
                "files_sha256": {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in files}}
    (output / "manifest.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"output": str(output.resolve()), "cases": len(summaries), "audit": checks}


def main():
    parser = argparse.ArgumentParser(description="Gera análise científica offline, sem alterar bancos ou API.")
    parser.add_argument("--snapshot", required=True, help="Pasta contendo response.json e manifest.json.")
    parser.add_argument("--output", required=True, help="Nova pasta de resultados; não pode existir.")
    parser.add_argument("--published-export", help="ZIP científico já exportado, para comparação de leitura.")
    parser.add_argument("--scientific-db", help="Banco article-simulations.db local, aberto somente para leitura.")
    args = parser.parse_args()
    result = build(args.snapshot, args.output, args.published_export, args.scientific_db)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
