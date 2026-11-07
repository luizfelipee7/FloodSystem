"""Behavior tests in temporary SQLite files; never populate the development DB."""

import sqlite3
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from backend.app.core.config import PROJECT_ROOT, Settings
from backend.app.core.database import connection, initialize_database
from backend.app.repositories.telemetry import DuplicateConflict, TelemetryRepository


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory(prefix="floodsystem-test-")
        self.addCleanup(self.directory.cleanup)
        self.settings = Settings.from_env({
            "FLOODSYSTEM_ENV": "test",
            "FLOODSYSTEM_TEST_DB_PATH": str(Path(self.directory.name) / "test.db"),
        })
        initialize_database(self.settings)
        self.repo = TelemetryRepository(self.settings)
        self.repo.register_device("sim-01", "Dispositivo de teste sintético", "simulation")

    def test_raw_records_without_calibration_persist_after_reopen(self):
        reading = self.repo.save_level_reading("sim-01", "r1", measured_at="2026-10-06T10:00:00-03:00", distance_cm=18)
        self.repo.save_rain_tip("sim-01", "e1", occurred_at="2026-10-06T13:00:00Z")
        reopened = TelemetryRepository(self.settings)
        self.assertEqual(reopened.list_level_readings("sim-01"), [reading.record])
        self.assertEqual(reading.record["measured_at"], "2026-10-06T13:00:00.000000Z")
        self.assertTrue(reading.record["received_at"].endswith("Z"))
        self.assertEqual(reading.record["origin"], "simulation")
        self.assertIsNone(reading.record["water_level_cm"])
        self.assertIsNone(reading.record["calibration_version"])
        self.assertIsNone(reopened.list_rain_tips("sim-01")[0]["calibration_version"])

    def test_identical_retries_preserve_records_and_receipt_time(self):
        original = self.repo.save_level_reading("sim-01", "r1", measured_at="2026-10-06T13:00:00Z", distance_cm=18)
        retry = self.repo.save_level_reading("sim-01", "r1", measured_at="2026-10-06T10:00:00-03:00", distance_cm=18.0)
        tip = self.repo.save_rain_tip("sim-01", "e1", occurred_at="2026-10-06T13:00:00Z")
        repeated_tip = self.repo.save_rain_tip("sim-01", "e1", occurred_at="2026-10-06T13:00:00Z")
        self.assertTrue(original.created)
        self.assertFalse(retry.created)
        self.assertFalse(repeated_tip.created)
        self.assertEqual(original.record, retry.record)
        self.assertEqual(tip.record, repeated_tip.record)
        self.assertEqual(len(self.repo.list_level_readings("sim-01")), 1)
        self.assertEqual(len(self.repo.list_rain_tips("sim-01")), 1)

    def test_identifier_conflicts_do_not_overwrite_original_data(self):
        original = self.repo.save_level_reading("sim-01", "r1", measured_at="2026-10-06T13:00:00Z", distance_cm=18)
        self.repo.save_rain_tip("sim-01", "e1", occurred_at="2026-10-06T13:00:00Z")
        with self.assertRaises(DuplicateConflict):
            self.repo.save_level_reading("sim-01", "r1", measured_at="2026-10-06T13:00:00Z", distance_cm=19)
        with self.assertRaises(DuplicateConflict):
            self.repo.save_rain_tip("sim-01", "e1", occurred_at="2026-10-06T13:01:00Z")
        self.assertEqual(self.repo.list_level_readings("sim-01"), [original.record])

    def test_identifiers_are_scoped_to_devices_and_origin_is_inherited(self):
        self.repo.register_device("esp32-test", "Cadastro sem dados físicos", "esp32")
        self.repo.save_rain_tip("sim-01", "e1", occurred_at="2026-10-06T13:00:00Z")
        result = self.repo.save_rain_tip("esp32-test", "e1", occurred_at="2026-10-06T13:00:00Z")
        self.assertTrue(result.created)
        self.assertEqual(result.record["origin"], "esp32")
        self.assertEqual(len(self.repo.list_rain_tips("sim-01")), 1)

    def test_calibration_versions_use_measurement_time_for_delayed_data(self):
        # Deliberately synthetic fixtures, only in a temporary test database.
        first = self.repo.add_calibration("sim-01", valid_from="2026-10-06T12:00:00Z", h0_cm=30, k_mm_per_tip=0.2)
        second = self.repo.add_calibration("sim-01", valid_from="2026-10-06T14:00:00Z", h0_cm=32, k_mm_per_tip=0.3)
        old = self.repo.save_level_reading("sim-01", "old", measured_at="2026-10-06T13:00:00Z", distance_cm=18)
        new = self.repo.save_level_reading("sim-01", "new", measured_at="2026-10-06T14:00:00Z", distance_cm=18)
        prior = self.repo.save_level_reading("sim-01", "prior", measured_at="2026-10-06T11:00:00Z", distance_cm=18)
        tip = self.repo.save_rain_tip("sim-01", "e1", occurred_at="2026-10-06T13:00:00Z")
        self.assertEqual((first["version"], second["version"]), (1, 2))
        self.assertEqual((old.record["calibration_version"], old.record["water_level_cm"]), (1, 12))
        self.assertEqual((new.record["calibration_version"], new.record["water_level_cm"]), (2, 14))
        self.assertEqual(tip.record["calibration_version"], 1)
        self.assertIsNone(prior.record["water_level_cm"])
        self.assertIsNone(prior.record["calibration_version"])

    def test_partial_calibration_does_not_invent_missing_h0(self):
        self.repo.add_calibration("sim-01", valid_from="2026-10-06T12:00:00Z", k_mm_per_tip=0.2)
        result = self.repo.save_level_reading("sim-01", "r1", measured_at="2026-10-06T13:00:00Z", distance_cm=18)
        self.assertEqual(result.record["calibration_version"], 1)
        self.assertIsNone(result.record["water_level_cm"])

    def test_new_calibration_does_not_change_previously_saved_reading(self):
        before = self.repo.save_level_reading("sim-01", "r1", measured_at="2026-10-06T13:00:00Z", distance_cm=18)
        self.repo.add_calibration("sim-01", valid_from="2026-10-06T12:00:00Z", h0_cm=30)
        after = self.repo.save_level_reading("sim-01", "r1", measured_at="2026-10-06T13:00:00Z", distance_cm=18)
        self.assertEqual(before.record, after.record)
        self.assertFalse(after.created)

    def test_calibration_history_cannot_be_changed_or_deleted(self):
        self.repo.add_calibration("sim-01", valid_from="2026-10-06T12:00:00Z", h0_cm=30)
        for sql in ("UPDATE calibrations SET h0_cm = 40", "DELETE FROM calibrations"):
            with self.subTest(sql=sql), self.assertRaises(sqlite3.IntegrityError):
                with connection(self.settings, write=True) as db:
                    db.execute(sql)
        with self.assertRaises(ValueError):
            self.repo.add_calibration("sim-01", valid_from="2026-10-06T11:00:00Z", h0_cm=32)

    def test_invalid_input_is_rejected_without_partial_inserts(self):
        for value in (-1, float("nan"), float("inf"), True, "18"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.repo.save_level_reading("sim-01", "invalid", measured_at="2026-10-06T13:00:00Z", distance_cm=value)
        with self.assertRaises(ValueError):
            self.repo.save_rain_tip("sim-01", "e1", occurred_at="2026-10-06T13:00:00")
        with self.assertRaises(ValueError):
            self.repo.save_rain_tip("missing", "e1", occurred_at="2026-10-06T13:00:00Z")
        with self.assertRaises(ValueError):
            self.repo.add_calibration("sim-01", valid_from="2026-10-06T13:00:00Z")
        with self.assertRaises(ValueError):
            self.repo.add_calibration("sim-01", valid_from="2026-10-06T13:00:00Z", h0_cm=0)
        self.assertEqual(self.repo.list_level_readings("sim-01"), [])
        self.assertEqual(self.repo.list_rain_tips("sim-01"), [])

    def test_sql_constraints_protect_against_duplicates_and_wrong_device_origin(self):
        self.repo.save_rain_tip("sim-01", "e1", occurred_at="2026-10-06T13:00:00Z")
        with self.assertRaises(sqlite3.IntegrityError):
            with connection(self.settings, write=True) as db:
                db.execute("INSERT INTO rain_tip_events SELECT * FROM rain_tip_events")
        with self.assertRaises(sqlite3.IntegrityError):
            with connection(self.settings, write=True) as db:
                db.execute("UPDATE rain_tip_events SET origin = 'esp32'")
        with connection(self.settings) as db:
            self.assertEqual(db.execute("PRAGMA foreign_key_check").fetchall(), [])

    def test_concurrent_retries_insert_only_once(self):
        def send(_):
            return self.repo.save_rain_tip("sim-01", "same-event", occurred_at="2026-10-06T13:00:00Z")
        with ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(send, range(8)))
        self.assertEqual(sum(result.created for result in results), 1)
        self.assertEqual(len(self.repo.list_rain_tips("sim-01")), 1)

    def test_repeated_initialization_preserves_data(self):
        self.repo.save_rain_tip("sim-01", "e1", occurred_at="2026-10-06T13:00:00Z")
        initialize_database(self.settings)
        self.assertEqual(len(self.repo.list_rain_tips("sim-01")), 1)
        with connection(self.settings) as db:
            self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 1)
            self.assertEqual(db.execute("PRAGMA integrity_check").fetchone()[0], "ok")


class ConfigurationAndMigrationTests(unittest.TestCase):
    def test_defaults_are_separate_and_paths_are_relative_to_project(self):
        self.assertEqual(PROJECT_ROOT, Path(__file__).resolve().parents[2])
        dev = Settings.from_env({})
        test = Settings.from_env({"FLOODSYSTEM_ENV": "test"})
        self.assertEqual(dev.database_path, PROJECT_ROOT / "database" / "development.db")
        self.assertEqual(test.database_path, PROJECT_ROOT / "database" / "test.db")
        self.assertNotEqual(dev.database_path, test.database_path)

    def test_test_environment_does_not_reuse_custom_application_database(self):
        config = {"FLOODSYSTEM_ENV": "test", "FLOODSYSTEM_DB_PATH": "database/custom.db"}
        self.assertEqual(Settings.from_env(config).database_path.name, "test.db")
        config["FLOODSYSTEM_TEST_DB_PATH"] = "database/custom.db"
        with self.assertRaises(ValueError):
            Settings.from_env(config)
        with self.assertRaises(ValueError):
            Settings.from_env({"FLOODSYSTEM_ENV": "test", "FLOODSYSTEM_TEST_DB_PATH": "database/development.db"})

    def test_invalid_environment_or_production_without_path_fails(self):
        for config in ({"FLOODSYSTEM_ENV": "unknown"}, {"FLOODSYSTEM_ENV": "production"}, {"FLOODSYSTEM_DB_PATH": ""}):
            with self.subTest(config=config), self.assertRaises(ValueError):
                Settings.from_env(config)

    def test_failed_migration_is_atomic(self):
        with tempfile.TemporaryDirectory(prefix="floodsystem-test-") as directory:
            settings = Settings.from_env({"FLOODSYSTEM_ENV": "test", "FLOODSYSTEM_TEST_DB_PATH": str(Path(directory) / "test.db")})
            migration = Path(directory) / "broken.sql"
            migration.write_text("CREATE TABLE partial (id INTEGER);\nINVALID SQL;\n", encoding="utf-8")
            with patch("backend.app.core.database.MIGRATIONS", (migration,)):
                with self.assertRaises(sqlite3.OperationalError):
                    initialize_database(settings)
            with connection(settings) as db:
                self.assertEqual(db.execute("PRAGMA user_version").fetchone()[0], 0)
                self.assertEqual(db.execute("SELECT name FROM sqlite_master WHERE type = 'table'").fetchall(), [])


if __name__ == "__main__":
    unittest.main()
