"""Stage 7 end-to-end check with an isolated, temporary SQLite database.

Run from the project root: .venv/Scripts/python.exe backend/tests/validate_stage7.py
Only localhost HTTP and a temporary test database are used.
"""

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ROOT = Path(__file__).resolve().parents[2]
PYTHON = sys.executable
FLAGS = getattr(subprocess, "CREATE_NO_WINDOW", 0)
RUNTIME = Path.home() / ".cache/codex-runtimes/codex-primary-runtime/dependencies/node"
NODE = RUNTIME / "bin/node.exe"
PLAYWRIGHT = RUNTIME / "node_modules/playwright"
CHROME = Path("C:/Program Files/Google/Chrome/Application/chrome.exe")
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


def available_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def request(base, method, path, payload=None, query=None):
    url = base + path + ("?" + urlencode(query) if query else "")
    data = json.dumps(payload).encode() if payload is not None else None
    req = Request(url, data=data, method=method,
                  headers={"Content-Type": "application/json", "Accept": "application/json"})
    try:
        with urlopen(req, timeout=5) as response:
            return response.status, json.load(response)
    except HTTPError as error:
        return error.code, json.load(error)


def start_api(port, env, log_path):
    log = open(log_path, "ab")
    process = subprocess.Popen(
        [PYTHON, "-m", "uvicorn", "backend.app.main:app", "--host", "127.0.0.1",
         "--port", str(port)], cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
        creationflags=FLAGS,
    )
    try:
        for _ in range(100):
            if process.poll() is not None:
                raise RuntimeError(f"API terminou cedo; consulte {log_path}")
            try:
                if request(f"http://127.0.0.1:{port}", "GET", "/health")[0] == 200:
                    return process, log
            except (URLError, TimeoutError):
                pass
            time.sleep(0.1)
        raise RuntimeError("API não iniciou em 10 segundos")
    except BaseException:
        process.terminate()
        process.wait(timeout=5)
        log.close()
        raise


def stop_api(process, log):
    process.terminate()
    try:
        process.wait(timeout=10)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
    log.close()


def start_site(port, api_base, log_path):
    if not (NODE.exists() and PLAYWRIGHT.exists() and CHROME.exists()):
        raise RuntimeError("Node, Playwright ou Chrome não encontrado para validar a interface")
    log = open(log_path, "ab")
    env = os.environ.copy()
    env["API_PROXY_TARGET"] = api_base
    env["VITE_API_BASE_URL"] = ""
    process = subprocess.Popen(
        [str(NODE), str(ROOT / "frontend/node_modules/vite/bin/vite.js"),
         "--host", "127.0.0.1", "--port", str(port), "--strictPort"],
        cwd=ROOT / "frontend", env=env, stdout=log, stderr=subprocess.STDOUT,
        creationflags=FLAGS,
    )
    try:
        for _ in range(100):
            if process.poll() is not None:
                raise RuntimeError(f"Frontend terminou cedo; consulte {log_path}")
            try:
                with urlopen(f"http://127.0.0.1:{port}", timeout=2) as response:
                    if response.status == 200:
                        return process, log
            except (URLError, TimeoutError):
                pass
            time.sleep(0.1)
        raise RuntimeError("Frontend não iniciou em 10 segundos")
    except BaseException:
        stop_api(process, log)
        raise


def check_ui(port, mode):
    env = os.environ.copy()
    env.update(PLAYWRIGHT_PACKAGE=str(PLAYWRIGHT), CHROME_PATH=str(CHROME),
               FLOODSYSTEM_FRONTEND_TEST_URL=f"http://127.0.0.1:{port}",
               FLOODSYSTEM_FRONTEND_TEST_MODE=mode)
    result = subprocess.run([str(NODE), str(ROOT / "frontend/tests/validate_stage7.cjs")],
                            cwd=ROOT / "frontend", env=env, text=True, encoding="utf-8", capture_output=True,
                            creationflags=FLAGS)
    print(result.stdout, end="")
    if result.returncode:
        raise AssertionError(result.stderr)


def run_cli(env, *args):
    completed = subprocess.run([PYTHON, "-m", *args], cwd=ROOT, env=env,
                               text=True, capture_output=True, creationflags=FLAGS)
    if completed.returncode:
        raise AssertionError(f"Comando falhou: {args}\n{completed.stderr}")
    return json.loads(completed.stdout)


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    print("OK:", message)


def main():
    with tempfile.TemporaryDirectory(prefix="floodsystem-stage7-") as folder:
        db = Path(folder) / "stage7.sqlite"
        env = os.environ.copy()
        env.update(FLOODSYSTEM_ENV="test", FLOODSYSTEM_TEST_DB_PATH=str(db))
        env.pop("FLOODSYSTEM_DB_PATH", None)
        run_cli(env, "backend.app.manage", "prepare-simulator")
        run_cli(env, "backend.app.manage", "register-device", "--device-id", "sem-calibracao-7",
                "--name", "Teste sintético sem calibração", "--origin", "simulation")
        port = available_port()
        base = f"http://127.0.0.1:{port}"
        log_path = Path(folder) / "api.log"
        process, log = start_api(port, env, log_path)
        site_process = site_log = None
        try:
            scenario = run_cli(env, "tools.simulator", "chuva-5min", "--base-url", base)
            check(scenario["counts"] == {"new_readings": 6, "duplicate_readings": 0,
                                         "new_tips": 10, "duplicate_tips": 0},
                  "simulador enviou 6 leituras e 10 basculadas novas por HTTP")
            period = {"device_id": "simulador-01", "start": "2026-10-08T13:00:00Z",
                      "end": "2026-10-08T13:05:00Z"}
            _, levels = request(base, "GET", "/api/v1/level-readings", query=period)
            _, tips = request(base, "GET", "/api/v1/rain-tips", query=period)
            _, summary = request(base, "GET", "/api/v1/summary", query={**period, "window_minutes": 5})
            check(len(levels["items"]) == 6 and all(r["distance_cm"] == 20 and
                  r["water_level_cm"] == 10 and r["origin"] == "simulation" for r in levels["items"]),
                  "H₀=30 cm menos distância=20 cm resulta em nível=10 cm, com origem simulação")
            check(len(tips["items"]) == 10 and len({r["event_id"] for r in tips["items"]}) == 10 and
                  all(r["origin"] == "simulation" for r in tips["items"]),
                  "cada basculada tem registro e identificador próprio")
            check(summary["rain"]["accumulated_rainfall"]["value"] == 2 and
                  summary["intensity"]["intensity"]["value"] == 24,
                  "10 × 0,2 mm = 2 mm; intensidade de 5 min = 24 mm/h")
            check(summary["level"]["elapsed_seconds"] == 299 and
                  summary["level"]["velocity"]["value"] == 0,
                  "resumo usa 299 segundos reais, sem supor leituras exatas a cada minuto")
            again = run_cli(env, "tools.simulator", "chuva-5min", "--base-url", base)
            check(again["counts"] == {"new_readings": 0, "duplicate_readings": 6,
                                      "new_tips": 0, "duplicate_tips": 10},
                  "reenvio mantém os mesmos 6 registros e 10 eventos")

            run_cli(env, "tools.simulator", "sobe-desce", "--base-url", base)
            rise = {"device_id": "simulador-01", "start": "2026-10-08T14:00:00Z",
                    "end": "2026-10-08T14:05:01Z", "window_minutes": 5}
            _, rising = request(base, "GET", "/api/v1/summary", query=rise)
            check(rising["level"]["level_change"]["value"] == 10 and
                  rising["level"]["elapsed_seconds"] == 300 and
                  rising["level"]["velocity"]["value"] == 2,
                  "subida de 10 cm em 300 s = 2 cm/min")
            falling_period = {"device_id": "simulador-01", "start": "2026-10-08T14:05:00Z",
                              "end": "2026-10-08T14:10:01Z", "window_minutes": 5}
            _, falling = request(base, "GET", "/api/v1/summary", query=falling_period)
            check(falling["level"]["level_change"]["value"] == -10 and
                  falling["level"]["elapsed_seconds"] == 300 and
                  falling["level"]["velocity"]["value"] == -2,
                  "descida de 10 cm em 300 s = -2 cm/min")

            raw = {"device_id": "sem-calibracao-7", "reading_id": "synthetic-raw-1",
                   "measured_at": "2026-10-08T13:00:00Z", "distance_cm": 17.9}
            status, saved = request(base, "POST", "/api/v1/level-readings", raw)
            check(status == 201 and saved["reading"]["water_level_cm"] is None and
                  saved["reading"]["distance_cm"] == 17.9,
                  "sem calibração a distância bruta é salva e o nível fica indisponível")
            status, raw_tip = request(base, "POST", "/api/v1/rain-tips",
                                      {"device_id": "sem-calibracao-7", "events": [
                                          {"event_id": "synthetic-tip-1", "occurred_at": "2026-10-08T13:01:00Z"}]})
            check(status == 200 and raw_tip["inserted_count"] == 1,
                  "basculada sem calibração K ainda é preservada")
            raw_period = {**period, "device_id": "sem-calibracao-7", "window_minutes": 5}
            _, raw_summary = request(base, "GET", "/api/v1/summary", query=raw_period)
            check(raw_summary["level"]["final"]["level"]["reason"] == "missing_h0" and
                  raw_summary["level"]["velocity"]["reason"] == "insufficient_level_readings" and
                  raw_summary["rain"]["accumulated_rainfall"]["reason"] == "missing_k" and
                  raw_summary["intensity"]["intensity"]["value"] is None,
                  "sem H₀/K e com uma leitura, indicadores dependentes mostram indisponibilidade")
            empty_period = {"device_id": "simulador-01", "start": "2026-10-08T16:00:00Z",
                            "end": "2026-10-08T16:05:00Z", "window_minutes": 5}
            _, empty = request(base, "GET", "/api/v1/summary", query=empty_period)
            check(empty["rain"]["tip_count"] == 0 and empty["level"]["reading_count"] == 0 and
                  empty["intensity"]["intensity"]["value"] is None,
                  "período vazio não inventa chuva zero nem nível")
            bad = {**raw, "reading_id": "synthetic-invalid", "distance_cm": -1}
            status, _ = request(base, "POST", "/api/v1/level-readings", bad)
            check(status == 422, "distância negativa é rejeitada com 422")
            status, _ = request(base, "POST", "/api/v1/rain-tips",
                                {"device_id": "simulador-01", "events": [
                                    {"event_id": "synthetic-invalid", "occurred_at": "sem-fuso"}]})
            check(status == 422, "horário inválido é rejeitado com 422")
            status, _ = request(base, "POST", "/api/v1/level-readings", raw)
            check(status == 200, "reenvio da leitura preserva o registro original")
            stop_api(process, log)
            process = log = None
            process, log = start_api(port, env, log_path)
            _, levels_after = request(base, "GET", "/api/v1/level-readings", query=period)
            _, tips_after = request(base, "GET", "/api/v1/rain-tips", query=period)
            _, summary_after = request(base, "GET", "/api/v1/summary", query={**period, "window_minutes": 5})
            check(levels_after == levels and tips_after == tips and summary_after == summary,
                  "após reiniciar a API, registros e cálculos persistem no mesmo SQLite de teste")
            site_port = available_port()
            site_process, site_log = start_site(site_port, base, Path(folder) / "site.log")
            check_ui(site_port, "data")
            stop_api(process, log)
            process = log = None
            check_ui(site_port, "offline")
            print("PASSOU: validação integrada API/SQLite/frontend em banco temporário")
        finally:
            if site_process is not None:
                stop_api(site_process, site_log)
            if process is not None:
                stop_api(process, log)


if __name__ == "__main__":
    main()
