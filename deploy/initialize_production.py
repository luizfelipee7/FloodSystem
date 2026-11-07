"""Explicit first production registration; no telemetry is created."""
from backend.app.core.config import Settings
from backend.app.core.database import connection, initialize_database
from backend.app.repositories.telemetry import TelemetryRepository


def main():
    settings = Settings.from_env()
    if settings.environment != "production":
        raise RuntimeError("This command requires production configuration")
    initialize_database(settings)
    repo = TelemetryRepository(settings)
    repo.register_device("esp32-01", "Pluviômetro físico ESP32", "esp32")
    with connection(settings) as db:
        calibrations = db.execute(
            "SELECT valid_from, h0_cm, k_mm_per_tip FROM calibrations WHERE device_id=? ORDER BY version",
            ("esp32-01",),
        ).fetchall()
    expected = ("2026-10-10T05:11:14.000000Z", None, 2.17)
    if not calibrations:
        repo.add_calibration("esp32-01", valid_from=expected[0], h0_cm=None, k_mm_per_tip=2.17)
    elif tuple(calibrations[0]) != expected:
        raise RuntimeError("Existing calibration differs; review it without overwriting history")
    print("esp32-01 registered; physical K=2.17, H0 unavailable. No telemetry inserted.")


if __name__ == "__main__":
    main()
