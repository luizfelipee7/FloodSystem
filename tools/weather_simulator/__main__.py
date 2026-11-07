"""Download/preview/send without SQLite access or implicit administrative setup."""

import argparse
import json
import os
from urllib.error import URLError
from urllib.parse import urlsplit

from tools.simulator.client import ApiClient, ApiError
from .model import generate
from .source import download, read_snapshot


def main():
    parser = argparse.ArgumentParser(description="Ensaios meteorológicos isolados do FloodSystem.")
    commands = parser.add_subparsers(dest="command", required=True)
    fetch = commands.add_parser("download", help="Preserva uma resposta original da Open-Meteo, sem banco.")
    fetch.add_argument("--latitude", type=float, default=-23.5505)
    fetch.add_argument("--longitude", type=float, default=-46.6333)
    fetch.add_argument("--start-day", default="2025-01-01", help="Primeiro dia em Brasília.")
    fetch.add_argument("--end-day", default="2025-01-03", help="Último dia incluído, em Brasília.")
    fetch.add_argument("--output", default="experiments/artifacts/open-meteo")
    for name in ("preview", "send"):
        command = commands.add_parser(name)
        command.add_argument("--snapshot", required=True)
        command.add_argument("--initial-residual-mm", default="0")
        if name == "send":
            command.add_argument("--base-url", default="http://127.0.0.1:8010")
            command.add_argument("--dry-run", action="store_true", help="Somente gera os pacotes; sem rede ou banco.")
    args = parser.parse_args()
    try:
        if args.command == "download":
            result = download(latitude=args.latitude, longitude=args.longitude, start_day=args.start_day,
                              end_day=args.end_day, output=args.output)
        else:
            manifest, raw = read_snapshot(args.snapshot)
            scenario = generate(manifest, raw, args.initial_residual_mm)
            if args.command == "preview" or args.dry_run:
                result = scenario
            else:
                if urlsplit(args.base_url).hostname not in {"127.0.0.1", "localhost", "::1"}:
                    raise ValueError("Esta primeira entrega envia somente à API local exclusiva dos ensaios.")
                client = ApiClient(args.base_url, os.environ.get("FLOODSYSTEM_SIMULATION_TOKEN"))
                state = client.request("GET", "/api/v1/experiments/status")
                if not state.get("enabled") or state.get("purpose") != "article-simulations":
                    raise ApiError("A API não é o ambiente exclusivo dos ensaios.")
                path = "/api/v1/experiments/" + scenario["run_id"]
                prepared = client.request("GET", path)
                if (prepared["device_id"] != scenario["device_id"] or prepared["profile"] != scenario["profile"]
                        or prepared["dataset_id"] != scenario["dataset_id"]):
                    raise ApiError("Perfil cadastrado difere do cenário. Nenhum envio realizado.")
                inserted, duplicates = 0, 0
                for offset in range(0, len(scenario["events"]), 500):
                    events = [{"event_id": e["event_id"], "occurred_at": e["occurred_at"]}
                              for e in scenario["events"][offset:offset + 500]]
                    reply = client.request("POST", "/api/v1/rain-tips",
                                           body={"device_id": scenario["device_id"], "events": events})
                    if any(item["event"]["origin"] != "simulation" or item["event"]["calibration_version"] != 1
                           for item in reply["results"]):
                        raise ApiError("Origem/calibração inesperada na confirmação.")
                    inserted += reply["inserted_count"]
                    duplicates += reply["duplicate_count"]
                final = client.request("GET", path)
                if final["status"] != "complete":
                    raise ApiError("Ensaio permanece incompleto. Retome usando o mesmo snapshot.")
                result = {"run_id": scenario["run_id"], "device_id": scenario["device_id"], "status": final["status"],
                          "inserted": inserted, "duplicates": duplicates, "source_total_mm": scenario["source_total_mm"],
                          "represented_mm": final["received_rain_mm"], "residual_mm": scenario["final_residual_mm"],
                          "notice": scenario["notice"]}
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    except (OSError, ValueError, KeyError, ApiError, URLError) as exc:
        parser.exit(1, f"Erro: {exc}\nO banco físico não é usado. Reenvios devem usar o mesmo snapshot e parâmetros.\n")


if __name__ == "__main__":
    main()
