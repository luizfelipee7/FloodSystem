"""Create source-backed, editable figures for the computational article.

Reads the published scientific export and the local scientific SQLite in
read-only mode. It never reads the physical database or changes the manuscript.
"""

import argparse
import csv
import hashlib
import io
import json
import sqlite3
import zipfile
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import matplotlib
matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch

BRASILIA = ZoneInfo("America/Sao_Paulo")
RUN_ID = "d72e3d0894e8d2314d50199f"
K = Decimal("2.17")


def _time(value):
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write_csv(path, rows, fields):
    with Path(path).open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields, delimiter=";")
        writer.writeheader()
        writer.writerows(rows)


def _read_export(path):
    with zipfile.ZipFile(path) as archive:
        detail = json.loads(archive.read("experiment.json"))
        hourly = list(csv.DictReader(io.StringIO(archive.read("hourly-comparison.csv").decode("utf-8-sig")), delimiter=";"))
        events = list(csv.DictReader(io.StringIO(archive.read("simulated-events.csv").decode("utf-8-sig")), delimiter=";"))
    if len(hourly) != 72 or len(events) != 6:
        raise ValueError("O export científico não contém 72 horas e seis eventos.")
    if any(row["run_id"] != RUN_ID or row["origin"] != "simulation" for row in events):
        raise ValueError("Eventos exportados não pertencem ao ensaio científico esperado.")
    for i, row in enumerate(hourly):
        if int(row["interval_index"]) != i or _time(row["end_at"]) - _time(row["start_at"]) != timedelta(hours=1):
            raise ValueError("Horas exportadas ausentes ou fora de ordem.")
        if row["source_time"] != row["end_at"]:
            raise ValueError("A marca da fonte não corresponde ao fim da hora precedente.")
    if sum((Decimal(row["rain_mm"]) for row in hourly), Decimal(0)) != Decimal("14.5"):
        raise ValueError("Chuva da fonte não corresponde aos 14,50 mm documentados.")
    return detail, hourly, events


def _read_residual(path):
    path = Path(path)
    if path.name != "article-simulations.db":
        raise ValueError("Somente o SQLite científico local pode fornecer os resíduos.")
    with sqlite3.connect(path.resolve().as_uri() + "?mode=ro&immutable=1", uri=True) as db:
        record = db.execute("SELECT dataset_id, profile_json, expected_tip_count FROM simulation_runs WHERE run_id=?",
                            (RUN_ID,)).fetchone()
        if record is None or record[2] != 6:
            raise ValueError("Ensaio esperado não encontrado no SQLite científico.")
        profile = json.loads(record[1])
        if Decimal(profile["k_mm_per_tip"]) != K:
            raise ValueError("K do SQLite difere do perfil do artigo.")
        rows = db.execute(
            "SELECT s.interval_index, w.start_at, w.end_at, w.source_time, w.rain_mm, "
            "s.residual_before_mm, s.residual_after_mm, s.expected_tip_count "
            "FROM simulation_steps s JOIN weather_intervals w "
            "ON w.dataset_id=? AND w.interval_index=s.interval_index "
            "WHERE s.run_id=? ORDER BY s.interval_index", (record[0], RUN_ID)).fetchall()
    if len(rows) != 72:
        raise ValueError("SQLite científico não contém os 72 passos do residual.")
    fields = ["interval_index", "start_at", "end_at", "source_time", "rain_mm",
              "residual_before_mm", "residual_after_mm", "expected_tip_count"]
    items = [dict(zip(fields, row)) for row in rows]
    prior = Decimal(0)
    for i, row in enumerate(items):
        before, after, rain = (Decimal(row[key]) for key in ("residual_before_mm", "residual_after_mm", "rain_mm"))
        if int(row["interval_index"]) != i or before != prior or before + rain != K * row["expected_tip_count"] + after:
            raise ValueError(f"Passo {i} não fecha o balanço/continuidade.")
        if not Decimal(0) <= after < K:
            raise ValueError(f"Residual fora dos limites na hora {i}.")
        prior = after
    if prior != Decimal("1.48"):
        raise ValueError("Residual final difere de 1,48 mm.")
    return items


def _save_figure(fig, output, stem):
    fig.savefig(output / f"{stem}.svg", bbox_inches="tight")
    fig.savefig(output / f"{stem}.png", dpi=240, bbox_inches="tight")
    plt.close(fig)


def _box(ax, xy, width, height, title, subtitle, face="#eef4f8", edge="#2d5066", title_size=10):
    x, y = xy
    rect = FancyBboxPatch((x, y), width, height,
                          boxstyle="round,pad=0.03,rounding_size=0.08",
                          linewidth=1.5, edgecolor=edge, facecolor=face)
    ax.add_patch(rect)
    ax.text(x + width / 2, y + height * .74, title, ha="center", va="center",
            fontsize=title_size, fontweight="bold", color="#172b3a")
    ax.text(x + width / 2, y + height * .29, subtitle, ha="center", va="center",
            fontsize=8.5, color="#273b49", linespacing=1.4)


def _arrow(ax, start, end, label=None, color="#48697a", rad=0):
    arrow = FancyArrowPatch(start, end, arrowstyle="-|>", mutation_scale=14,
                            linewidth=1.7, color=color,
                            connectionstyle=f"arc3,rad={rad}")
    ax.add_patch(arrow)
    if label:
        ax.text((start[0] + end[0]) / 2, (start[1] + end[1]) / 2 + .14,
                label, ha="center", va="bottom", fontsize=8, color=color)


def _diagram_flow(output):
    fig, ax = plt.subplots(figsize=(10.4, 9))
    ax.set_xlim(0, 10.4); ax.set_ylim(0, 12.7); ax.axis("off")
    nodes = [
        (11.35, "Consultar dados", "Snapshot ERA5/manifesto\nresposta original e SHA-256"),
        (9.75, "Verificar intervalos", "Unidade mm, UTC e sequência de 72 h\nrain = soma da hora precedente"),
        (7.80, "Converter cada hora i", "nᵢ = ⌊(rᵢ + pᵢ)/K⌋\nrᵢ₊₁ = rᵢ + pᵢ − nᵢK"),
        (5.85, "Gerar eventos sintéticos", "Hipótese uniforme por hora\nhorários e IDs determinísticos"),
        (4.25, "Preparar ensaio isolado", "Dispositivo virtual, perfil e ledger\nno SQLite científico; sem telemetria"),
        (2.65, "Enviar eventos", "Lotes HTTP para API científica local\nPOST /api/v1/rain-tips"),
        (1.05, "Conferir persistência", "GET do ensaio: esperado = recebido\nbalanço, completude e ZIP"),
    ]
    heights = [1.05, 1.05, 1.37, 1.1, 1.05, 1.05, 1.05]
    for (y, title, subtitle), h in zip(nodes, heights):
        _box(ax, (1.35, y), 7.7, h, title, subtitle,
             face="#e7f4f1" if title == "Converter cada hora i" else "#eef4f8")
    for idx in range(len(nodes) - 1):
        y, _, _ = nodes[idx]
        next_y, _, _ = nodes[idx + 1]
        _arrow(ax, (5.2, y - .04), (5.2, next_y + heights[idx + 1] + .04))
    ax.text(5.2, .45, "Repetir por 72 horas; r é residual contínuo de chuva, não nível da água",
            ha="center", fontsize=9, color="#5a6770")
    _save_figure(fig, output, "figura-1-fluxograma-algoritmo")


def _diagram_architecture(output):
    fig, ax = plt.subplots(figsize=(14.5, 6.7))
    ax.set_xlim(0, 15); ax.set_ylim(0, 7.2); ax.axis("off")
    ax.text(.35, 6.65, "TELEMETRIA FÍSICA", fontsize=11, fontweight="bold", color="#1e5572")
    ax.text(.35, 3.37, "ENSAIO COMPUTACIONAL", fontsize=11, fontweight="bold", color="#247b64")
    ax.plot([.3, 14.7], [3.8, 3.8], color="#c7d2d8", linewidth=1.2)
    physical = [
        (.35, "ESP32 + sensores", "KY-024 / HC-SR04"),
        (3.1, "Nginx / HTTPS", "domínio publicado"),
        (5.85, "API física", "FastAPI /api"),
        (8.6, "SQLite físico", "production.db"),
        (11.35, "Dashboard", "Tempo real / Histórico"),
    ]
    for x, title, subtitle in physical:
        _box(ax, (x, 4.78), 2.3, 1.12, title, subtitle, face="#e9f2f8", edge="#37749a", title_size=9.2)
    for a, b in zip(physical[:3], physical[1:4]):
        _arrow(ax, (a[0] + 2.34, 5.34), (b[0] - .06, 5.34),
               "POST" if a[1] == "Nginx / HTTPS" else None, color="#37749a")
    _arrow(ax, (8.58, 5.0), (8.2, 5.0), color="#37749a")
    _arrow(ax, (8.12, 5.94), (12.45, 5.94), "GET via API", color="#37749a", rad=-.18)

    scientific = [
        (.25, "Open-Meteo / ERA5", "chuva horária histórica"),
        (2.55, "Snapshot", "JSON + manifesto/hash"),
        (4.85, "Conversor", "K, residual, IDs"),
        (7.15, "API científica local", "POST eventos virtuais"),
        (9.45, "SQLite científico", "ensaios separados"),
        (11.75, "API pública + painel", "GET /article-api\npainel /ensaios/")
    ]
    for x, title, subtitle in scientific:
        _box(ax, (x, 1.35), 2.03, 1.16, title, subtitle, face="#e7f4ef", edge="#328568", title_size=8.8)
    for a, b in zip(scientific, scientific[1:]):
        _arrow(ax, (a[0] + 2.07, 1.93), (b[0] - .05, 1.93), color="#328568")
    ax.text(7.5, .75, "Bancos segregados; a página científica não consulta nem altera a telemetria física",
            ha="center", fontsize=9, color="#5a6770")
    _save_figure(fig, output, "figura-2-arquitetura-segregada")


def _plot_rain_events(output, hourly, events):
    starts = [_time(row["start_at"]) for row in hourly]
    values = [float(Decimal(row["rain_mm"])) for row in hourly]
    instants = sorted(_time(event["occurred_at"]) for event in events)
    fig, (top, bottom) = plt.subplots(2, 1, figsize=(11, 5.7), sharex=True,
                                      gridspec_kw={"height_ratios": [4, 1], "hspace": .08})
    top.bar(starts, values, width=1 / 24, align="edge", color="#287ba2", edgecolor="white", linewidth=.3)
    top.set_ylabel("Chuva na hora (mm)")
    top.grid(axis="y", color="#dce2e5", linewidth=.7)
    top.set_axisbelow(True)
    top.set_ylim(bottom=0)
    for index, when in enumerate(instants, 1):
        bottom.vlines(when, 0, .72, color="#bf4e3f", linewidth=2.1)
        bottom.text(when, .78, str(index), ha="center", va="bottom", fontsize=9, color="#a63f33")
    bottom.set_ylim(0, 1.12); bottom.set_yticks([])
    bottom.set_ylabel("Eventos\nsimulados", rotation=0, labelpad=47, va="center")
    bottom.set_xlabel("Data e hora em Brasília")
    bottom.xaxis.set_major_locator(mdates.HourLocator(interval=12, tz=BRASILIA))
    bottom.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m\n%Hh", tz=BRASILIA))
    bottom.set_xlim(starts[0], _time(hourly[-1]["end_at"]))
    bottom.grid(axis="x", color="#e1e5e8", linewidth=.65)
    fig.subplots_adjust(left=.11, right=.99, bottom=.14, top=.98)
    _save_figure(fig, output, "figura-3-chuva-horaria-eventos")


def _plot_residual(output, rows):
    ends = [_time(row["end_at"]) for row in rows]
    after = [float(Decimal(row["residual_after_mm"])) for row in rows]
    start = _time(rows[0]["start_at"])
    fig, ax = plt.subplots(figsize=(11, 4.8))
    ax.plot([start] + ends, [0] + after, color="#267e69", linewidth=1.45,
            marker="o", markersize=2.6)
    ax.axhline(float(K), color="#a46632", linestyle="--", linewidth=1.1,
               label="K = 2,17 mm")
    ax.set_ylabel("Residual do modelo (mm)")
    ax.set_xlabel("Fim de cada intervalo horário em Brasília")
    ax.set_ylim(0, 2.35)
    ax.set_xlim(start, ends[-1])
    ax.grid(axis="y", color="#dce2e5", linewidth=.7)
    ax.legend(frameon=False, loc="upper right")
    ax.xaxis.set_major_locator(mdates.HourLocator(interval=12, tz=BRASILIA))
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%d/%m\n%Hh", tz=BRASILIA))
    ax.text(.01, -.31, "Pontos: rᵢ₊₁ armazenado ao fim de cada hora; linhas apenas guiam a leitura entre pontos.",
            transform=ax.transAxes, fontsize=8.5, color="#52616b")
    fig.subplots_adjust(left=.1, right=.99, bottom=.27, top=.98)
    _save_figure(fig, output, "figura-4-residual-horario")


FLOW_MMD = """flowchart TD
    A["Snapshot ERA5 + manifesto e SHA-256"] --> B["Validar modelo, unidade, UTC e 72 horas"]
    B --> C["Para cada hora i: disponível = rᵢ + pᵢ; nᵢ = piso(disponível/K); rᵢ₊₁ = disponível − nᵢK"]
    C --> D["Hipótese uniforme: gerar horários e IDs sintéticos"]
    D --> E["Preparar dispositivo virtual, perfil e ledger no SQLite científico"]
    E --> F["Enviar lotes HTTP para API científica local"]
    F --> G["Conferir esperado = recebido; balanço e exportação ZIP"]
"""

ARCH_MMD = """flowchart LR
    subgraph F[Telemetria física]
      ESP["ESP32 + sensores KY-024 e HC-SR04"] --> NG["Nginx / HTTPS"] --> AF["FastAPI física /api"]
      AF <--> BF["SQLite físico production.db"]
      AF <--> DF["Dashboard Tempo real / Histórico"]
    end
    subgraph S[Ensaio computacional]
      ERA["Open-Meteo / ERA5"] --> SNAP["Snapshot JSON + manifesto"] --> CONV["Conversor K + residual"]
      CONV --> AS["API científica local POST"] --> BS["SQLite científico isolado"]
      BS --> AR["API pública somente leitura /article-api"] <--> PS["Painel /ensaios/"]
    end
"""


def build(export, db, output):
    output = Path(output)
    if output.exists():
        previous = output / "manifest.json"
        if not previous.is_file():
            raise FileExistsError("Pasta existente sem manifesto gerado; escolha outra pasta.")
        existing = json.loads(previous.read_text(encoding="utf-8"))
        if existing.get("run_id") != RUN_ID or any(
                not (output / name).is_file() or _sha(output / name) != digest
                for name, digest in existing.get("files_sha256", {}).items()):
            raise FileExistsError("Figuras existentes foram alteradas; escolha outra pasta para preservá-las.")
    detail, hourly, events = _read_export(export)
    residual = _read_residual(db)
    for source, step in zip(hourly, residual):
        if (source["start_at"] != step["start_at"] or
                Decimal(source["rain_mm"]) != Decimal(step["rain_mm"]) or
                Decimal(source["residual_after_mm"]) != Decimal(step["residual_after_mm"])):
            raise ValueError("ZIP publicado e SQLite científico divergem em hora, chuva ou residual.")
    output.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9.5,
                         "svg.fonttype": "none", "savefig.facecolor": "white"})
    _diagram_flow(output)
    _diagram_architecture(output)
    _plot_rain_events(output, hourly, events)
    _plot_residual(output, residual)
    (output / "figura-1-fluxograma-algoritmo.mmd").write_text(FLOW_MMD, encoding="utf-8")
    (output / "figura-2-arquitetura-segregada.mmd").write_text(ARCH_MMD, encoding="utf-8")
    _write_csv(output / "dados-chuva-horaria.csv", hourly, list(hourly[0]))
    _write_csv(output / "dados-seis-eventos.csv", events, list(events[0]))
    _write_csv(output / "dados-residual-72h.csv", residual, list(residual[0]))
    captions = """# Figuras para o artigo computacional

Os arquivos SVG são vetoriais e mantêm texto editável; os dois arquivos `.mmd` são as fontes Mermaid editáveis dos diagramas. Os PNGs são alternativas para programas que não preservam SVG. Use apenas as figuras necessárias, respeitando a contagem de elementos gráficos da revista.

## Legendas sugeridas

1. **Fluxo de conversão e conferência dos eventos simulados.** Esquema baseado em `tools/weather_simulator/model.py`, `tools/weather_simulator/__main__.py`, `backend/app/manage.py` e `backend/app/repositories/experiments.py`. O símbolo `r` é o residual de chuva no modelo da báscula, não o nível do recipiente. Os boxes representam operações reais do código; a figura não demonstra desempenho físico.
2. **Arquitetura física e científica segregada do FloodSystem.** A via física usa ESP32, API e SQLite de produção. A via computacional usa um snapshot ERA5, dispositivo virtual, SQLite científico e API pública de leitura. O diagrama é baseado na implementação e na configuração de publicação; não mistura telemetria física e simulada.
3. **Chuva horária ERA5 e seis horários de eventos simulados, 01–03/01/2025.** Barras mostram totais das horas `[início,fim)` extraídos de `hourly-comparison.csv`; traços numerados mostram `occurred_at` dos seis eventos de `simulated-events.csv`. Os instantes dentro de cada hora dependem da hipótese de distribuição uniforme; não são medições meteorológicas sub-horárias. Fonte: ZIP científico publicado do ensaio `d72e3d0894e8d2314d50199f`.
4. **Residual horário do modelo de báscula em 72 intervalos.** Cada ponto representa `rᵢ₊₁` preservado em `simulation_steps` no SQLite científico; a linha apenas guia a leitura entre pontos. `K=2,17 mm/basculada`. O residual é chuva ainda insuficiente para nova virada, não altura de água. Não houve interpolação de totais diários.

## Proveniência e reprodução

- Figuras 3 e 4 foram geradas por `python -m tools.weather_simulator.article_figures` a partir do ZIP do ensaio publicado e de `database/article-simulations.db` **somente leitura**.
- Os CSVs nesta pasta são cópias das linhas usadas nas figuras; `dados-residual-72h.csv` vem diretamente das 72 linhas `simulation_steps` associadas a `weather_intervals`.
- `manifest.json` guarda os hashes dos arquivos gerados e das duas entradas.
- Nenhuma figura resulta de ensaio de campo, nível de água simulado ou medição residencial.
"""
    (output / "LEIA-ME-figuras.md").write_text(captions, encoding="utf-8")
    files = sorted(path for path in output.iterdir() if path.is_file())
    meta = {"run_id": RUN_ID, "data_kind": "ERA5 hourly source + simulated tips + scientific SQLite ledger",
            "hourly_rows": len(hourly), "event_rows": len(events), "residual_rows": len(residual),
            "k_mm_per_tip": str(K), "published_export_sha256": _sha(export),
            "scientific_db_sha256": _sha(db), "generator_sha256": _sha(__file__),
            "matplotlib_version": matplotlib.__version__,
            "files_sha256": {path.name: _sha(path) for path in files}}
    (output / "manifest.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"folder": str(output.resolve()), "figures": 4,
            "hourly_rows": len(hourly), "events": len(events), "residual_rows": len(residual)}


def main():
    parser = argparse.ArgumentParser(description="Gera figuras editáveis a partir do ensaio científico existente.")
    parser.add_argument("--export", required=True, help="ZIP científico publicado (leitura).")
    parser.add_argument("--scientific-db", required=True, help="article-simulations.db local (somente leitura).")
    parser.add_argument("--output", required=True, help="Pasta nova para as figuras.")
    args = parser.parse_args()
    print(json.dumps(build(args.export, args.scientific_db, args.output), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
