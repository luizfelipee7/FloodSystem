"""Production auth and backup/restore checks, using isolated temporary databases."""
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from fastapi.testclient import TestClient
from backend.app.core.config import Settings
from backend.app.core.database import initialize_database
from backend.app.main import create_app
from backend.app.repositories.telemetry import TelemetryRepository
from deploy.sqlite_backup import snapshot, verify


class DeploymentTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "source.db"
        self.settings = Settings("production", self.path, True, {"simulation-check": "a" * 48, "other": "b" * 48})
        initialize_database(self.settings)
        self.repo = TelemetryRepository(self.settings)
        self.repo.register_device("simulation-check", "Isolated deployment fixture", "simulation")

    def test_https_and_device_token_required_without_duplicate_writes(self):
        payload = {"device_id": "simulation-check", "events": [{"event_id": "tip-1", "occurred_at": "2026-10-10T12:00:00Z"}]}
        with TestClient(create_app(self.settings), base_url="https://testserver") as client:
            for headers in ({}, {"Authorization": "Bearer " + "b" * 48}):
                self.assertEqual(client.post("/api/v1/rain-tips", json=payload, headers=headers).status_code, 401)
            self.assertEqual(self.repo.list_rain_tips("simulation-check"), [])
            headers = {"Authorization": "Bearer " + "a" * 48}
            self.assertEqual(client.post("/api/v1/rain-tips", json=payload, headers=headers).json()["inserted_count"], 1)
            self.assertEqual(client.post("/api/v1/rain-tips", json=payload, headers=headers).json()["duplicate_count"], 1)
        with TestClient(create_app(self.settings), base_url="http://testserver") as client:
            self.assertEqual(client.post("/api/v1/rain-tips", json=payload, headers=headers).status_code, 403)

    def test_snapshot_includes_wal_and_restore_refuses_existing_target(self):
        # Keep a connection open so committed records may still be in WAL.
        writer = sqlite3.connect(self.path)
        self.addCleanup(writer.close)
        writer.execute("PRAGMA journal_mode=WAL")
        writer.execute("PRAGMA wal_autocheckpoint=0")
        self.repo.save_rain_tips("simulation-check", [("tip-1", "2026-10-10T12:00:00Z")])
        backup = Path(self.temp.name) / "backup.db"
        self.assertEqual(snapshot(self.path, backup)["rain_tip_events"], 1)
        self.repo.save_rain_tips("simulation-check", [("tip-2", "2026-10-10T12:01:00Z")])
        restored = Path(self.temp.name) / "restored.db"
        self.assertEqual(snapshot(backup, restored)["rain_tip_events"], 1)
        self.assertEqual(verify(self.path)["rain_tip_events"], 2)
        with self.assertRaises(ValueError):
            snapshot(backup, self.path)
        self.assertEqual(verify(self.path)["rain_tip_events"], 2)

    def test_invalid_backup_and_missing_source_leave_no_destination(self):
        invalid = Path(self.temp.name) / "invalid.db"
        invalid.write_text("not a database")
        target = Path(self.temp.name) / "restore.db"
        with self.assertRaises(sqlite3.DatabaseError):
            snapshot(invalid, target)
        self.assertFalse(target.exists())
        with self.assertRaises(ValueError):
            snapshot(Path(self.temp.name) / "missing.db", target)


if __name__ == "__main__":
    unittest.main()
