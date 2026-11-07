"""Explicit local administration, without adding an administration API."""

import argparse
import json

from .core.config import Settings
from .core.database import initialize_database
from .repositories.telemetry import TelemetryRepository


def main():
    parser = argparse.ArgumentParser(description="Cadastro local de dispositivos, calibrações e preparação de simulação do FloodSystem.")
    commands = parser.add_subparsers(dest="command", required=True)
    register = commands.add_parser("register-device")
    register.add_argument("--device-id", required=True)
    register.add_argument("--name", required=True)
    register.add_argument("--origin", choices=("simulation", "esp32"), required=True)
    commands.add_parser("prepare-simulator", help="Cadastra simulador-01 e sua calibração SINTÉTICA explicitamente.")
    weather = commands.add_parser("prepare-weather-experiment", help="Importa uma fonte preservada e prepara um ensaio em banco exclusivo.")
    weather.add_argument("--snapshot", required=True, help="Pasta com manifest.json e response.json.")
    weather.add_argument("--initial-residual-mm", default="0")
    calibration = commands.add_parser(
        "add-calibration", help="Registra uma nova calibração explícita para um dispositivo."
    )
    calibration.add_argument("--device-id", required=True)
    calibration.add_argument("--valid-from", required=True, help="Inicio de vigencia ISO 8601 com fuso horario.")
    calibration.add_argument("--h0-cm", type=float, help="H0 conhecido; omita se ainda nao medido.")
    calibration.add_argument("--k-mm-per-tip", type=float, help="K conhecido em mm por basculada.")
    args = parser.parse_args()
    try:
        settings = Settings.from_env()
        if args.command == "prepare-weather-experiment":
            from tools.weather_simulator.source import read_snapshot
            from .repositories.experiments import prepare_experiment
            manifest, raw = read_snapshot(args.snapshot)
            output = prepare_experiment(settings, manifest, raw, args.initial_residual_mm)
        elif args.command == "prepare-simulator":
            # Only the administrative CLI reads this shared, pure JSON profile.
            # The simulator itself never imports backend modules or opens SQLite.
            from tools.simulator.profile import load_profile
            from .repositories.simulation_setup import prepare_simulation

            if settings.environment == "production":
                raise ValueError("prepare-simulator não é permitido no ambiente production.")
            profile = load_profile()
            initialize_database(settings)
            output = prepare_simulation(settings, profile)
        elif args.command == "add-calibration":
            if args.h0_cm is None and args.k_mm_per_tip is None:
                raise ValueError("Informe --h0-cm, --k-mm-per-tip ou ambos.")
            initialize_database(settings)
            output = TelemetryRepository(settings).add_calibration(
                args.device_id,
                valid_from=args.valid_from,
                h0_cm=args.h0_cm,
                k_mm_per_tip=args.k_mm_per_tip,
            )
        else:
            initialize_database(settings)
            result = TelemetryRepository(settings).register_device(args.device_id, args.name, args.origin)
            output = {"created": result.created, "device": result.record}
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
