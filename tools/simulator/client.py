"""HTTP-only transport using the same telemetry contracts as the ESP32."""

import json
import socket
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit
from urllib.request import Request, urlopen


class ApiError(RuntimeError):
    pass


class ApiClient:
    def __init__(self, base_url: str, token: str | None = None):
        parsed = urlsplit(base_url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("Use a URL da API, sem credenciais, query ou fragmento.")
        self.base_url = base_url.rstrip("/")
        self.token = token

    def url(self, path: str, parameters=None) -> str:
        return self.base_url + path + ("?" + urlencode(parameters) if parameters else "")

    def request(self, method: str, path: str, *, body=None, parameters=None):
        url = self.url(path, parameters)
        data = json.dumps(body, allow_nan=False).encode("utf-8") if body is not None else None
        headers = {
            "Accept": "application/json", "Content-Type": "application/json",
        }
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        request = Request(url, data=data, method=method, headers=headers)
        for attempt in range(3):
            try:
                with urlopen(request, timeout=10) as response:
                    return json.load(response)
            except HTTPError as exc:
                detail = exc.read().decode("utf-8", errors="replace")
                if exc.code not in (429, 500, 502, 503, 504) or attempt == 2:
                    raise ApiError(f"HTTP {exc.code} em {path}: {detail}") from exc
            except (URLError, socket.timeout, ConnectionError) as exc:
                if attempt == 2:
                    raise ApiError(f"Não foi possível acessar {url}. Confira se a API está aberta. {exc}") from exc
            except (ValueError, UnicodeError) as exc:
                raise ApiError(f"Resposta não JSON em {url}.") from exc
            # Reuse the exact payload/IDs if a response was lost after a commit.
            time.sleep(attempt + 1)

    def observations(self, path, parameters):
        offset = 0
        while True:
            page = self.request("GET", path, parameters={**parameters, "limit": 1000, "offset": offset})
            yield from page["items"]
            if not page["has_more"]:
                return
            offset += 1000


def send_scenario(client: ApiClient, scenario: dict) -> dict:
    profile = scenario["profile"]
    parameters = {"device_id": profile["device_id"], "start": scenario["start"], "end": scenario["end"]}
    prior = client.request("GET", "/api/v1/summary", parameters=parameters)
    if prior["origin"] != "simulation":
        raise ApiError("O dispositivo não tem origem simulation. Nenhum pacote foi enviado.")
    readings = scenario["level_readings"]
    events = [event for batch in scenario["rain_batches"] for event in batch["events"]]
    # Catch overlapping scenarios before writing; unchanged reruns are allowed.
    for path, expected, id_field, fields in (
        ("/api/v1/level-readings", readings, "reading_id", ("measured_at", "distance_cm")),
        ("/api/v1/rain-tips", events, "event_id", ("occurred_at",)),
    ):
        indexed = {item[id_field]: item for item in expected}
        for existing in client.observations(path, parameters):
            intended = indexed.get(existing[id_field])
            if intended is None or any(existing[field] != intended[field] for field in fields):
                raise ApiError("O período já contém outro cenário ou dados diferentes. Use --start em outro período.")
            if existing["origin"] != "simulation" or existing["calibration_version"] != 1:
                raise ApiError("Os dados existentes não usam a calibração sintética esperada (versão 1).")
    totals = {"new_readings": 0, "duplicate_readings": 0, "new_tips": 0, "duplicate_tips": 0}
    for payload in readings:
        result = client.request("POST", "/api/v1/level-readings", body=payload)
        record = result["reading"]
        expected_level = profile["h0_cm"] - payload["distance_cm"]
        if record["origin"] != "simulation" or record["calibration_version"] != 1 or record["water_level_cm"] != expected_level:
            raise ApiError("A leitura foi recebida, mas a calibração difere do perfil. Pare e confira prepare-simulator; não continue este cenário.")
        totals["new_readings" if result["created"] else "duplicate_readings"] += 1
    for payload in scenario["rain_batches"]:
        result = client.request("POST", "/api/v1/rain-tips", body=payload)
        if any(item["event"]["origin"] != "simulation" or item["event"]["calibration_version"] != 1 for item in result["results"]):
            raise ApiError("O lote foi recebido, mas origem/calibração diferem do perfil de simulação.")
        totals["new_tips"] += result["inserted_count"]
        totals["duplicate_tips"] += result["duplicate_count"]
    summary = client.request("GET", "/api/v1/summary", parameters=parameters)
    if any(group["k_mm_per_tip"] != profile["k_mm_per_tip"] for group in summary["rain"]["calibrations"]):
        raise ApiError("Os eventos foram recebidos, mas K difere do perfil. Confira a preparação do backend.")
    return {
        "notice": scenario["notice"], "run_id": scenario["run_id"],
        "scenario": scenario["scenario"], "profile": profile,
        "counts": totals, "summary": summary,
        "query_urls": {name: client.url(path, parameters) for name, path in (
            ("levels", "/api/v1/level-readings"), ("rain", "/api/v1/rain-tips"), ("summary", "/api/v1/summary"))},
    }
