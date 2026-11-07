"""HTTP contract tests against independent, temporary SQLite databases."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
import sqlite3

from fastapi.testclient import TestClient

from backend.app.core.config import Settings
from backend.app.main import create_app
from backend.app.repositories.telemetry import TelemetryRepository


class ApiTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="floodsystem-api-test-")
        self.addCleanup(self.directory.cleanup)
        self.settings = Settings.from_env({
            "FLOODSYSTEM_ENV": "test",
            "FLOODSYSTEM_TEST_DB_PATH": str(Path(self.directory.name) / "api-test.db"),
        })
        self.application = create_app(self.settings)
        self.client = TestClient(self.application)
        self.client.__enter__()
        self.addCleanup(self.client.__exit__, None, None, None)
        self.repo = self.application.state.repository
        self.repo.register_device("simulador-01", "Fixture sintética", "simulation")
        self.level = {
            "device_id": "simulador-01", "reading_id": "leitura-0001",
            "measured_at": "2026-10-06T14:05:00Z", "distance_cm": 17.9,
        }
        self.rain = {
            "device_id": "simulador-01",
            "events": [
                {"event_id": "bascula-0001", "occurred_at": "2026-10-06T14:03:12Z"},
                {"event_id": "bascula-0002", "occurred_at": "2026-10-06T14:03:48Z"},
            ],
        }
        self.period = {"device_id": "simulador-01", "start": "2026-10-06T14:00:00Z", "end": "2026-10-06T14:10:00Z"}

    def test_health_and_documented_routes(self):
        self.assertEqual(self.client.get("/health").json(), {"status": "ok", "database": "ok"})
        paths = self.client.get("/openapi.json").json()["paths"]
        self.assertEqual(set(paths), {"/health", "/api/v1/time", "/api/v1/level-readings", "/api/v1/rain-tips", "/api/v1/summary"})
        for path in ("/api/v1/level-readings", "/api/v1/rain-tips"):
            self.assertEqual(set(paths[path]), {"get", "post"})
        self.assertEqual(self.client.get("/docs").status_code, 200)

    def test_level_without_calibration_persists_and_retries_return_original(self):
        response = self.client.post("/api/v1/level-readings", json=self.level)
        self.assertEqual(response.status_code, 201, response.text)
        original = response.json()["reading"]
        self.assertTrue(response.json()["created"])
        self.assertIsNone(original["water_level_cm"])
        self.assertIsNone(original["calibration_version"])
        self.assertEqual(original["origin"], "simulation")
        self.assertTrue(original["received_at"].endswith("Z"))
        retry = self.client.post("/api/v1/level-readings", json={**self.level, "measured_at": "2026-10-06T11:05:00-03:00"})
        self.assertEqual(retry.status_code, 200, retry.text)
        self.assertFalse(retry.json()["created"])
        self.assertEqual(retry.json()["reading"], original)
        self.assertEqual(TelemetryRepository(self.settings).list_level_readings("simulador-01"), [original])

    def test_level_uses_calibration_valid_at_measurement_time(self):
        # All constants in these fixtures are synthetic, confined to the temporary DB.
        self.repo.add_calibration("simulador-01", valid_from="2026-10-06T14:00:00Z", h0_cm=30)
        self.repo.add_calibration("simulador-01", valid_from="2026-10-06T15:00:00Z", h0_cm=35)
        response = self.client.post("/api/v1/level-readings", json=self.level)
        self.assertEqual(response.status_code, 201, response.text)
        self.assertEqual(response.json()["reading"]["calibration_version"], 1)
        self.assertAlmostEqual(response.json()["reading"]["water_level_cm"], 12.1)

    def test_level_identifier_with_different_data_is_conflict(self):
        self.client.post("/api/v1/level-readings", json=self.level)
        response = self.client.post("/api/v1/level-readings", json={**self.level, "distance_cm": 20})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(self.repo.list_level_readings("simulador-01")[0]["distance_cm"], 17.9)

    def test_distance_validation_and_server_owned_fields(self):
        for invalid in (-1, True, "17.9", None):
            with self.subTest(invalid=invalid):
                response = self.client.post("/api/v1/level-readings", json={**self.level, "distance_cm": invalid})
                self.assertEqual(response.status_code, 422, response.text)
        for field, value in (("origin", "esp32"), ("water_level_cm", 42), ("received_at", "2026-10-06T14:05:00Z"), ("h0_cm", 30)):
            with self.subTest(field=field):
                self.assertEqual(self.client.post("/api/v1/level-readings", json={**self.level, field: value}).status_code, 422)
        self.assertEqual(self.repo.list_level_readings("simulador-01"), [])

    def test_nonfinite_distance_has_json_validation_response(self):
        for literal in ("NaN", "Infinity", "-Infinity", "1e999"):
            payload = json.dumps(self.level).replace('17.9', literal)
            with self.subTest(literal=literal):
                response = self.client.post("/api/v1/level-readings", content=payload, headers={"Content-Type": "application/json"})
                self.assertEqual(response.status_code, 422, response.text)
                self.assertIn("detail", response.json())

    def test_timestamp_and_identifier_validation(self):
        for timestamp in ("2026-10-06T14:05:00", "2026-10-06", 1791295500, "invalid", "2026-10-06T14:05:00.1234567Z"):
            with self.subTest(timestamp=timestamp):
                self.assertEqual(self.client.post("/api/v1/level-readings", json={**self.level, "measured_at": timestamp}).status_code, 422)
        for value in ("", " ", " padded", 123, "x" * 129):
            with self.subTest(identifier=value):
                self.assertEqual(self.client.post("/api/v1/level-readings", json={**self.level, "reading_id": value}).status_code, 422)

    def test_batch_persists_individual_events_and_supports_retries(self):
        first = self.client.post("/api/v1/rain-tips", json=self.rain)
        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual((first.json()["inserted_count"], first.json()["duplicate_count"]), (2, 0))
        second = self.client.post("/api/v1/rain-tips", json=self.rain)
        self.assertEqual((second.json()["inserted_count"], second.json()["duplicate_count"]), (0, 2))
        for original, repeated in zip(first.json()["results"], second.json()["results"]):
            self.assertEqual(original["event"], repeated["event"])
        self.assertEqual(len(self.repo.list_rain_tips("simulador-01")), 2)

    def test_mixed_batch_counts_new_events_and_retries(self):
        self.client.post("/api/v1/rain-tips", json=self.rain)
        mixed = {**self.rain, "events": [self.rain["events"][0], {"event_id": "new", "occurred_at": "2026-10-06T14:04:00Z"}]}
        response = self.client.post("/api/v1/rain-tips", json=mixed)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual((response.json()["inserted_count"], response.json()["duplicate_count"]), (1, 1))

    def test_conflict_rolls_back_new_events_in_entire_batch(self):
        self.client.post("/api/v1/rain-tips", json=self.rain)
        invalid = {**self.rain, "events": [
            {"event_id": "new-before-conflict", "occurred_at": "2026-10-06T14:04:00Z"},
            {"event_id": "bascula-0001", "occurred_at": "2026-10-06T14:09:00Z"},
        ]}
        response = self.client.post("/api/v1/rain-tips", json=invalid)
        self.assertEqual(response.status_code, 409, response.text)
        self.assertEqual([row["event_id"] for row in self.repo.list_rain_tips("simulador-01")], ["bascula-0001", "bascula-0002"])

    def test_duplicate_identifiers_within_batch_are_handled(self):
        repeated = {**self.rain, "events": [self.rain["events"][0], self.rain["events"][0]]}
        response = self.client.post("/api/v1/rain-tips", json=repeated)
        self.assertEqual((response.json()["inserted_count"], response.json()["duplicate_count"]), (1, 1))
        conflicting = {**self.rain, "events": [
            {"event_id": "internal-conflict", "occurred_at": "2026-10-06T14:04:00Z"},
            {"event_id": "internal-conflict", "occurred_at": "2026-10-06T14:06:00Z"},
        ]}
        self.assertEqual(self.client.post("/api/v1/rain-tips", json=conflicting).status_code, 409)
        self.assertEqual(len(self.repo.list_rain_tips("simulador-01")), 1)

    def test_invalid_or_oversized_batch_is_rejected_before_saving(self):
        for events in ([], self.rain["events"] * 251,
                       [self.rain["events"][0], {"event_id": "bad", "occurred_at": "no-time"}],
                       [{**self.rain["events"][0], "origin": "esp32"}]):
            with self.subTest(size=len(events)):
                response = self.client.post("/api/v1/rain-tips", json={**self.rain, "events": events})
                self.assertEqual(response.status_code, 422, response.text)
                self.assertEqual(self.repo.list_rain_tips("simulador-01"), [])

    def test_unknown_devices_return_404_and_are_not_auto_registered(self):
        for path, payload in (("/api/v1/level-readings", self.level), ("/api/v1/rain-tips", self.rain)):
            with self.subTest(path=path):
                self.assertEqual(self.client.post(path, json={**payload, "device_id": "unknown"}).status_code, 404)
                self.assertEqual(self.client.get(path, params={**self.period, "device_id": "unknown"}).status_code, 404)

    def test_period_boundaries_pagination_and_device_isolation(self):
        self.repo.register_device("other-sim", "Outra fixture", "simulation")
        for index, timestamp in enumerate(("2026-10-06T14:00:00Z", "2026-10-06T14:05:00Z", "2026-10-06T14:10:00Z")):
            self.client.post("/api/v1/level-readings", json={**self.level, "reading_id": str(index), "measured_at": timestamp})
            self.client.post("/api/v1/rain-tips", json={**self.rain, "events": [{"event_id": str(index), "occurred_at": timestamp}]})
        self.repo.save_rain_tip("other-sim", "other", occurred_at="2026-10-06T14:05:00Z")
        for path, id_field in (("/api/v1/level-readings", "reading_id"), ("/api/v1/rain-tips", "event_id")):
            with self.subTest(path=path):
                full = self.client.get(path, params=self.period)
                self.assertEqual(full.status_code, 200, full.text)
                self.assertEqual([row[id_field] for row in full.json()["items"]], ["0", "1"])
                first = self.client.get(path, params={**self.period, "limit": 1}).json()
                second = self.client.get(path, params={**self.period, "limit": 1, "offset": 1}).json()
                self.assertTrue(first["has_more"])
                self.assertFalse(second["has_more"])
                self.assertEqual(second["items"][0][id_field], "1")

    def test_query_normalizes_timezone_and_returns_empty_period(self):
        params = {**self.period, "start": "2026-10-06T11:00:00-03:00", "end": "2026-10-06T11:10:00-03:00"}
        response = self.client.get("/api/v1/level-readings", params=params)
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["start"], "2026-10-06T14:00:00.000000Z")
        self.assertEqual(response.json()["items"], [])
        self.assertFalse(response.json()["has_more"])

    def test_invalid_queries_return_422(self):
        for changes in ({"start": self.period["end"]}, {"end": "2026-10-06T13:00:00Z"},
                        {"start": "2026-10-06T14:00:00"}, {"limit": 0}, {"limit": 1001},
                        {"offset": -1}, {"unexpected": "value"}):
            with self.subTest(changes=changes):
                response = self.client.get("/api/v1/rain-tips", params={**self.period, **changes})
                self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(self.client.get("/api/v1/rain-tips", params={"device_id": "simulador-01"}).status_code, 422)

    def test_data_survives_application_recreation(self):
        self.client.post("/api/v1/level-readings", json=self.level)
        self.client.post("/api/v1/rain-tips", json=self.rain)
        with TestClient(create_app(self.settings)) as second_client:
            self.assertEqual(len(second_client.get("/api/v1/level-readings", params=self.period).json()["items"]), 1)
            self.assertEqual(len(second_client.get("/api/v1/rain-tips", params=self.period).json()["items"]), 2)

    def test_database_operational_failure_has_safe_retry_response(self):
        with self.assertLogs("backend.app.main", level="ERROR"), patch.object(self.repo, "save_level_reading", side_effect=sqlite3.OperationalError("database is locked")):
            response = self.client.post("/api/v1/level-readings", json=self.level)
        self.assertEqual(response.status_code, 503)
        self.assertEqual(response.headers["Retry-After"], "5")
        self.assertNotIn(str(self.settings.database_path), response.text)


if __name__ == "__main__":
    unittest.main()
