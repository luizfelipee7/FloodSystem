"""Read-only public deployment checks; rejected POST uses an unregistered device."""
from datetime import datetime, timedelta, timezone
import json
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

BASE = "https://floodsystem.duckdns.org"


def request(path, body=None):
    headers = {"Content-Type": "application/json"} if body is not None else {}
    req = Request(BASE + path, data=json.dumps(body).encode() if body is not None else None, headers=headers)
    try:
        with urlopen(req, timeout=20) as response:
            return response.status, response.read()
    except HTTPError as error:
        return error.code, error.read()


def main():
    status, body = request("/")
    assert status == 200 and b'<div id="root"' in body
    print("HTTPS frontend: OK")
    status, body = request("/health")
    assert status == 200 and json.loads(body) == {"status": "ok", "database": "ok"}
    print("API and SQLite health: OK")
    status, body = request("/api/v1/time")
    assert status == 200 and isinstance(json.loads(body)["unix_ms"], int)
    end = datetime.now(timezone.utc)
    params = urlencode({"device_id": "esp32-01", "start": (end - timedelta(hours=1)).isoformat(), "end": end.isoformat(), "window_minutes": 5})
    status, body = request("/api/v1/summary?" + params)
    assert status == 200 and json.loads(body)["origin"] == "esp32"
    print("Public summary for physical device: OK")
    # No such device is registered by this deployment: even with misconfigured auth,
    # repository validation rejects the request rather than storing fake telemetry.
    status, _ = request("/api/v1/rain-tips", {"device_id": "unregistered-security-probe", "events": [{"event_id": "synthetic-rejected-probe", "occurred_at": end.isoformat()}]})
    assert status == 401, status
    print("Write without token: HTTP 401")
    for path in ("/.env", "/database/production.db", "/PrivateKey/test.key"):
        status, _ = request(path)
        assert status in (403, 404), (path, status)
    print("Private files/database unavailable over HTTP: OK")


if __name__ == "__main__":
    main()
