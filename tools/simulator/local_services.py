"""Explicit local development startup; never reads or writes telemetry."""

import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import time
from urllib.error import URLError
from urllib.parse import urlsplit
from urllib.request import ProxyHandler, Request, build_opener
import webbrowser

ROOT = Path(__file__).resolve().parents[2]
API_URL = "http://127.0.0.1:8000"
SITE_URL = "http://127.0.0.1:5173"
_STARTED = {}


def _get(url):
    # Local service checks must not go through a system HTTP proxy.
    opener = build_opener(ProxyHandler({}))
    with opener.open(Request(url), timeout=1) as response:
        return response.read(262144).decode("utf-8")


def service_status(service):
    """An open port alone is not proof that the expected service is healthy."""
    port = 8000 if service == "api" else 5173
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.3):
            pass
    except (ConnectionRefusedError, TimeoutError):
        pending = _STARTED.get(service)
        if pending is not None and pending.poll() is None:
            return "starting", "INICIANDO — processo ativo, aguardando resposta"
        return "stopped", "DESLIGADO"
    except OSError:
        return "occupied", "INDETERMINADO — não foi possível verificar a porta"
    try:
        if service == "api":
            schema = json.loads(_get(API_URL + "/openapi.json"))
            health = json.loads(_get(API_URL + "/health"))
            valid = (schema.get("info", {}).get("title") == "FloodSystem API"
                     and health.get("status") == "ok" and health.get("database") == "ok")
        else:
            page = _get(SITE_URL + "/")
            valid = "<title>FloodSystem" in page and 'id="root"' in page
        if valid:
            return "running", "LIGADO — respondendo"
    except (URLError, OSError, ValueError, UnicodeError, AttributeError):
        pass
    return "occupied", "PORTA OCUPADA — serviço não confirmado ou ainda iniciando"


def show_status():
    print("\nSERVIÇOS LOCAIS (neste computador)", flush=True)
    for service, label, url in (("api", "API ", API_URL), ("site", "SITE", SITE_URL)):
        _, message = service_status(service)
        print(f"  {label}: {message} | {url}", flush=True)
    print("O site e a API são serviços separados; o painel precisa dos dois.")


def _command(service):
    if service == "api":
        python = ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        if not python.is_file():
            raise ValueError("Ambiente .venv não encontrado. Consulte docs/api.md.")
        return [str(python), "-m", "uvicorn", "backend.app.main:app",
                "--host", "127.0.0.1", "--port", "8000"], ROOT
    node = shutil.which("node")
    if not node:
        bundled = (Path.home() / ".cache/codex-runtimes/codex-primary-runtime/"
                   "dependencies/node/bin/node.exe")
        if bundled.is_file():
            node = str(bundled)
    if not node:
        raise ValueError("Node.js não encontrado. Consulte docs/frontend.md.")
    vite = ROOT / "frontend/node_modules/vite/bin/vite.js"
    if not vite.is_file():
        raise ValueError("Instale as dependências do frontend conforme docs/frontend.md.")
    return [node, str(vite), "--host", "127.0.0.1", "--port", "5173", "--strictPort"], ROOT / "frontend"


def start_service(service, base_url):
    if service == "api":
        parsed = urlsplit(base_url)
        if (parsed.scheme != "http" or parsed.hostname not in {"localhost", "127.0.0.1"}
                or parsed.port != 8000 or parsed.path.rstrip("/")):
            print("A opção liga somente a API local em http://127.0.0.1:8000.")
            print("Você selecionou outra API com --base-url; inicie-a no ambiente correspondente.")
            return
    state, message = service_status(service)
    if state != "stopped":
        print(f"\n{message}. Nenhum novo processo foi iniciado.")
        return
    command, cwd = _command(service)
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    if service == "api":
        # The menu is a local development launcher, never a production launcher.
        env["FLOODSYSTEM_ENV"] = "development"
        env["FLOODSYSTEM_DB_PATH"] = str(ROOT / "database/development.db")
        env["FLOODSYSTEM_TEST_DB_PATH"] = str(ROOT / "database/test.db")
        print("API local: ambiente development, banco database/development.db.")
    else:
        env["API_PROXY_TARGET"] = API_URL
        env["VITE_API_BASE_URL"] = ""
        print(f"Site local: consultas encaminhadas para {API_URL}.")
    logs = ROOT / ".logs"
    logs.mkdir(exist_ok=True)
    log_path = logs / f"{service}-menu.log"
    options = {}
    if os.name == "nt":
        options["creationflags"] = subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
        startup = subprocess.STARTUPINFO()
        startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startup.wShowWindow = subprocess.SW_HIDE
        options["startupinfo"] = startup
    else:
        options["start_new_session"] = True
    with log_path.open("ab", buffering=0) as log:
        process = subprocess.Popen(command, cwd=cwd, env=env, stdin=subprocess.DEVNULL,
                                   stdout=log, stderr=subprocess.STDOUT, **options)
    _STARTED[service] = process
    print(f"Iniciando em segundo plano (PID {process.pid})...", flush=True)
    print(f"Registro de execução: {log_path}")
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if process.poll() is not None:
            print(f"O processo encerrou com código {process.returncode}. Consulte o registro acima.")
            return
        state, _ = service_status(service)
        if state == "running":
            print("LIGADO — serviço pronto.")
            print("Fechar o menu não desliga o serviço. Reiniciar o computador o encerra.")
            return
        time.sleep(0.4)
    print("O processo foi iniciado, mas ainda não confirmou que está pronto.")
    print("Use a opção 7 para atualizar o status e consulte o registro se não responder.")


def open_site():
    state, message = service_status("site")
    if state != "running":
        print(f"Site: {message}. Use a opção 6 para iniciar o site local.")
        return
    if not webbrowser.open(SITE_URL + "/"):
        print(f"Abra no navegador: {SITE_URL}/")


def handle_service_option(choice, base_url):
    try:
        if choice == "5":
            start_service("api", base_url)
        elif choice == "6":
            start_service("site", base_url)
        elif choice == "7":
            show_status()
        elif choice == "8":
            open_site()
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(f"Não foi possível concluir: {exc}")
