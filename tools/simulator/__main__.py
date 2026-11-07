"""Run with python -m tools.simulator from the project root."""

import argparse
import json
import sys

from .client import ApiClient, ApiError, send_scenario
from .profile import load_profile
from .scenarios import DEFAULT_STARTS, build_scenario


def main():
    parser = argparse.ArgumentParser(description="FloodSystem: dados SINTÉTICOS enviados somente por HTTP.")
    parser.add_argument("scenario", nargs="?", default="menu", choices=[*DEFAULT_STARTS, "menu"],
                        help="Escolha um cenário diretamente ou use menu (padrão) para seleção interativa.")
    parser.add_argument("--start", help="Início ISO 8601 com fuso. Cada cenário tem um início fixo próprio por padrão.")
    parser.add_argument("--delay-seconds", type=int, default=None, help="Somente chuva-atraso: atraso após a janela de chuva, de 0 a 3600 s; padrão 120.")
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--dry-run", action="store_true", help="Exibe perfil e pacotes sem acessar API ou banco.")
    args = parser.parse_args()
    try:
        if args.scenario == "menu":
            if args.start is not None or args.delay_seconds is not None:
                raise ValueError("No menu, escolha horário e atraso nas perguntas, sem --start ou --delay-seconds.")
            from .interactive import run_interactive
            parser.exit(run_interactive(args.base_url, preview_only=args.dry_run))
        if args.delay_seconds is not None and args.scenario != "chuva-atraso":
            raise ValueError("--delay-seconds só se aplica a chuva-atraso.")
        scenario = build_scenario(args.scenario, args.start or DEFAULT_STARTS[args.scenario], load_profile(),
                                  120 if args.delay_seconds is None else args.delay_seconds)
        if args.dry_run:
            result = scenario
        else:
            print(scenario["notice"], file=sys.stderr)
            print("Enviando por HTTP. Horários simulados são reproduzidos sem espera em tempo real.", file=sys.stderr)
            result = send_scenario(ApiClient(args.base_url), scenario)
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    except (ApiError, ValueError, OSError, OverflowError) as exc:
        parser.exit(1, f"Erro: {exc}\nUma execução interrompida pode ter enviado parte dos dados; repetir o mesmo comando reutiliza os IDs.\n")
    except KeyboardInterrupt:
        parser.exit(130, "Interrompido. Reexecute o mesmo comando para retomar sem duplicar registros.\n")


if __name__ == "__main__":
    main()
