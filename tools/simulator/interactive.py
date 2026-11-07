"""Human-friendly terminal menu over the existing HTTP simulator."""

import json
import os
import subprocess
import sys
from datetime import timedelta, timezone
from pathlib import Path

from .client import ApiClient, ApiError, send_scenario
from .profile import load_profile, parse_instant, timestamp
from .scenarios import DEFAULT_STARTS, build_scenario
from .local_services import handle_service_option, show_status

OPTIONS = {
    "1": ("sem-chuva", "Sem chuva e nível estável", "Simulação · sem chuva"),
    "2": ("chuva-5min", "Dez basculadas em cinco minutos", "Simulação · chuva em 5 min"),
    "3": ("sobe-desce", "Nível subindo e descendo", "Simulação · subida e descida"),
    "4": ("chuva-atraso", "Chuva seguida de alteração do nível", "Simulação · chuva com atraso de 2 min"),
}
# Brasília uses UTC−3 for the project's 2026 timestamps. Use a fixed offset so
# the simulator also works on Windows installations without an IANA tz database.
BRASILIA = timezone(timedelta(hours=-3), name="BRT")
ROOT = Path(__file__).resolve().parents[2]


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def run_stage7_validation():
    script = ROOT / "backend" / "tests" / "validate_stage7.py"
    if not script.is_file():
        print("Validação não encontrada. Confira backend/tests/validate_stage7.py.")
        return
    print("VALIDAÇÃO DO FLUXO COMPLETO")
    print("A verificação usa um SQLite temporário e servidores locais de teste.")
    print("Os resultados simulados desse teste não aparecem no site de desenvolvimento.\n")
    try:
        result = subprocess.run([sys.executable, str(script)], cwd=ROOT, check=False)
    except OSError as exc:
        print(f"Não foi possível iniciar a validação: {exc}")
        return
    if result.returncode:
        print(f"\nA validação terminou com erro (código {result.returncode}). Confira a mensagem acima.")
    else:
        print("\nValidação concluída com sucesso.")


def brasilia_time(value):
    return parse_instant(value).astimezone(BRASILIA).isoformat(timespec="seconds")


def ask_start(name, profile):
    default = DEFAULT_STARTS[name]
    print(f"\nHorário padrão: {brasilia_time(default)} (Brasília).")
    print("Enter mantém o horário padrão deste cenário.")
    print("Para outro período, digite horário de Brasília, por exemplo 2026-10-09T20:27:00-03:00.")
    while True:
        value = input("Início [Enter = padrão]: ").strip() or default
        try:
            instant = parse_instant(value)
            if instant < parse_instant(profile.valid_from):
                raise ValueError("O início precisa estar dentro da vigência da calibração sintética.")
            return timestamp(instant)
        except (ValueError, OverflowError) as exc:
            print(f"Horário inválido: {exc}")


def ask_delay():
    print("\nO atraso começa no fim da janela de cinco minutos de chuva.")
    while True:
        value = input("Atraso em segundos, de 0 a 3600 [Enter = 120]: ").strip() or "120"
        try:
            delay = int(value)
            if 0 <= delay <= 3600:
                return delay
        except ValueError:
            pass
        print("Digite um número inteiro entre 0 e 3600.")


def show_site_instructions(scenario, site_label):
    print("\nCOMO VER NO SITE")
    print("Abra http://127.0.0.1:5173/ no computador do projeto.")
    print("Na barra lateral, abra Histórico. Os cenários têm horários antigos e não aparecem em Tempo real.")
    if (scenario["start"] == timestamp(parse_instant(DEFAULT_STARTS[scenario["scenario"]]))
            and (scenario["scenario"] != "chuva-atraso" or scenario["delay_seconds"] == 120)):
        print(f'Em CONSULTA HISTÓRICA, escolha "{site_label}".')
    else:
        print('Em CONSULTA HISTÓRICA, escolha "Intervalo personalizado" e preencha no horário de Brasília:')
        print(f'  Início: {brasilia_time(scenario["start"])}')
        print(f'  Fim:    {brasilia_time(scenario["end"])}')
    print("Use o dispositivo simulador-01 e clique em Aplicar filtros.")
    print("Se o mesmo período já estiver aberto, clique em Atualizar.")
    if scenario["scenario"] == "sobe-desce":
        print("A velocidade média do período todo é zero: veja a subida e a descida no gráfico.")
    if scenario["scenario"] == "chuva-atraso":
        print(f'Para analisar só a janela da chuva no Histórico, use {brasilia_time(scenario["start"])} até {brasilia_time(scenario["rain_window_end"])}.')


def run_interactive(base_url="http://127.0.0.1:8000", *, preview_only=False):
    client = ApiClient(base_url)
    profile = load_profile()
    active_scenario = None
    try:
        while True:
            clear_screen()
            if preview_only:
                print("MODO PRÉVIA: nenhum pacote será enviado e nenhuma consulta HTTP será feita.")
            print("\n" + "─" * 58)
            if not preview_only:
                show_status()
            print("\nSIMULAÇÃO DE DADOS")
            for key, (_, label, _) in OPTIONS.items():
                print(f"  {key} - {label}")
            if not preview_only:
                print("\nSERVIÇOS LOCAIS")
                print("  5 - Ligar a API local (backend)")
                print("  6 - Ligar o site local (frontend / localhost)")
                print("  7 - Atualizar status da API e do site")
                print("  8 - Abrir o site no navegador")
                print("\nVALIDAÇÃO")
                print("  9 - Validar o fluxo completo (banco temporário)")
            print("\n  0 - Sair\n")
            choice = input("Digite uma opção e pressione Enter: ").strip()
            clear_screen()
            if choice == "0":
                print("Simulador encerrado. Os dados já gravados continuam no SQLite.")
                if not preview_only:
                    print("A API e o site que estiverem ligados continuam em execução.")
                return 0
            if choice in {"5", "6", "7", "8"} and not preview_only:
                handle_service_option(choice, client.base_url)
                input("\nPressione Enter para voltar ao menu...")
                continue
            if choice == "9" and not preview_only:
                run_stage7_validation()
                input("\nPressione Enter para voltar ao menu...")
                continue
            if choice not in OPTIONS:
                print("Opção inválida. Escolha um dos números exibidos no menu.")
                input("\nPressione Enter para voltar ao menu...")
                continue
            name, label, site_label = OPTIONS[choice]
            active_scenario = None
            try:
                start = ask_start(name, profile)
                delay = ask_delay() if name == "chuva-atraso" else 120
                scenario = build_scenario(name, start, profile, delay)
                active_scenario = scenario
                tips = sum(len(batch["events"]) for batch in scenario["rain_batches"])
                print(f"\nCenário: {label}")
                print(f'Período de Brasília: {brasilia_time(scenario["start"])} até {brasilia_time(scenario["end"])} (fim excluído).')
                print(f'Pacotes: {len(scenario["level_readings"])} leituras e {tips} basculadas.')
                print(f'Identificador da execução: {scenario["run_id"]}')
                if preview_only:
                    print(json.dumps(scenario, ensure_ascii=False, indent=2, allow_nan=False))
                    print("\nPrévia concluída. Nenhum dado enviado.")
                else:
                    print("\nEnviando pela API...", flush=True)
                    result = send_scenario(client, scenario)
                    counts = result["counts"]
                    print("\nENVIO CONCLUÍDO")
                    print(f'  Leituras novas:              {counts["new_readings"]}')
                    print(f'  Leituras já existentes:      {counts["duplicate_readings"]}')
                    print(f'  Basculadas novas:            {counts["new_tips"]}')
                    print(f'  Basculadas já existentes:    {counts["duplicate_tips"]}')
                    print("A API reconhece os registros existentes sem criar cópias.")
                    show_site_instructions(scenario, site_label)
            except (ApiError, ValueError, OSError, OverflowError) as exc:
                print(f"\nNão foi possível concluir: {exc}")
                if active_scenario and not preview_only:
                    print("Parte dos dados pode já ter sido recebida. Para retomar, use os mesmos parâmetros:")
                    print(f'  Cenário: {name} | início: {brasilia_time(active_scenario["start"])} (Brasília) | atraso: {delay} s')
                print("Se a API estiver parada, inicie o backend. O menu não cadastra nem apaga dados diretamente.")
            active_scenario = None
            input("\nPressione Enter para voltar ao menu...")
    except (KeyboardInterrupt, EOFError):
        print("\nMenu encerrado.")
        if active_scenario and not preview_only:
            print("Se o envio foi interrompido, repita o mesmo cenário e início para retomar sem duplicar:")
            print(f'  {active_scenario["scenario"]} | {brasilia_time(active_scenario["start"])} (Brasília) | atraso: {active_scenario["delay_seconds"]}')
        return 0
