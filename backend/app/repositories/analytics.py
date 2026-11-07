"""Read a consistent SQLite snapshot without the telemetry pagination limit."""

from ..core.database import connection
from .telemetry import TelemetryRepository, identifier, utc_timestamp


class AnalyticsRepository:
    def __init__(self, settings):
        self.settings = settings

    @staticmethod
    def _rain(db, device_id, start, end):
        # Count per recorded calibration, including the uncalibrated group.
        return [dict(row) for row in db.execute("""
            SELECT e.calibration_version, c.k_mm_per_tip, COUNT(*) AS tip_count
            FROM rain_tip_events e
            LEFT JOIN calibrations c
              ON c.device_id = e.device_id AND c.version = e.calibration_version
            WHERE e.device_id = ? AND e.occurred_at >= ? AND e.occurred_at < ?
            GROUP BY e.calibration_version, c.k_mm_per_tip
            ORDER BY e.calibration_version
        """, (device_id, start, end))]

    @staticmethod
    def _endpoint(db, device_id, timestamp):
        if timestamp is None:
            return None
        row = dict(db.execute("""
            SELECT l.reading_id, l.measured_at, l.distance_cm,
                   l.calibration_version, c.h0_cm
            FROM level_readings l
            LEFT JOIN calibrations c
              ON c.device_id = l.device_id AND c.version = l.calibration_version
            WHERE l.device_id = ? AND l.measured_at = ?
            ORDER BY l.reading_id LIMIT 1
        """, (device_id, timestamp)).fetchone())
        variants = db.execute("""
            SELECT COUNT(*) FROM (
                SELECT DISTINCT distance_cm, calibration_version
                FROM level_readings WHERE device_id = ? AND measured_at = ?
            )
        """, (device_id, timestamp)).fetchone()[0]
        row["ambiguous"] = variants > 1
        return row

    def summary_snapshot(self, device_id, *, start, end, window_start):
        identifier(device_id, "device_id")
        start, end, window_start = map(utc_timestamp, (start, end, window_start))
        if start >= end or window_start >= end:
            raise ValueError("Intervalo de cálculo inválido.")
        with connection(self.settings) as db:
            # All queries see the same committed state, even during new arrivals.
            db.execute("BEGIN")
            device = TelemetryRepository._device(db, device_id)
            levels = dict(db.execute("""
                SELECT COUNT(*) AS reading_count,
                       COUNT(*) - COUNT(c.h0_cm) AS uncalibrated_count,
                       COUNT(DISTINCT c.h0_cm) AS h0_count,
                       MIN(l.measured_at) AS first_at, MAX(l.measured_at) AS last_at
                FROM level_readings l
                LEFT JOIN calibrations c
                  ON c.device_id = l.device_id AND c.version = l.calibration_version
                WHERE l.device_id = ? AND l.measured_at >= ? AND l.measured_at < ?
            """, (device_id, start, end)).fetchone())
            levels["initial"] = self._endpoint(db, device_id, levels["first_at"])
            levels["final"] = self._endpoint(db, device_id, levels["last_at"])
            return {
                "origin": device["origin"],
                "levels": levels,
                "rain": self._rain(db, device_id, start, end),
                "window_rain": self._rain(db, device_id, window_start, end)
                if window_start >= start else None,
            }
