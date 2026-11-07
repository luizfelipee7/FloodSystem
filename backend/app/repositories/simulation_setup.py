"""Explicit backend administration; the HTTP simulator never calls this module."""

from ..core.database import connection
from .telemetry import DuplicateConflict, measurement, now_utc, utc_timestamp


def prepare_simulation(settings, profile):
    if settings.environment == "production":
        raise ValueError("A preparação sintética é exclusiva dos ambientes development e test.")
    if profile.device_id != "simulador-01" or profile.origin != "simulation" or profile.simulation_only is not True:
        raise ValueError("Perfil exclusivo para simulador-01 com origem simulation.")
    valid_from = utc_timestamp(profile.valid_from)
    h0 = measurement(profile.h0_cm, "h0_cm", positive=True)
    k = measurement(profile.k_mm_per_tip, "k_mm_per_tip", positive=True)
    with connection(settings, write=True) as db:
        device = db.execute("SELECT * FROM devices WHERE device_id = ?", (profile.device_id,)).fetchone()
        if device and device["origin"] != "simulation":
            raise DuplicateConflict("simulador-01 já existe com origem física. Nenhum cadastro foi alterado.")
        calibrations = db.execute("SELECT * FROM calibrations WHERE device_id = ? ORDER BY version",
                                  (profile.device_id,)).fetchall()
        if calibrations and (len(calibrations) != 1 or calibrations[0]["version"] != 1 or
                             calibrations[0]["valid_from"] != valid_from or
                             calibrations[0]["h0_cm"] != h0 or calibrations[0]["k_mm_per_tip"] != k):
            raise DuplicateConflict("simulador-01 já possui outra calibração. Use um banco de simulação separado; o histórico foi preservado.")
        for table in ("level_readings", "rain_tip_events"):
            invalid = db.execute(f"""
                SELECT 1 FROM {table} WHERE device_id = ?
                AND (calibration_version IS NULL OR calibration_version != 1) LIMIT 1
            """, (profile.device_id,)).fetchone()
            if invalid:
                raise DuplicateConflict("Há observações anteriores sem a calibração esperada. Use um banco separado; não há recálculo retroativo automático.")
        device_created = device is None
        calibration_created = not calibrations
        if device_created:
            db.execute("INSERT INTO devices (device_id, name, origin, created_at) VALUES (?, ?, ?, ?)",
                       (profile.device_id, "Simulador do MVP (dados sintéticos)", "simulation", now_utc()))
        if calibration_created:
            db.execute("""
                INSERT INTO calibrations (device_id, version, valid_from, received_at, h0_cm, k_mm_per_tip)
                VALUES (?, 1, ?, ?, ?, ?)
            """, (profile.device_id, valid_from, now_utc(), h0, k))
        calibration = dict(db.execute("SELECT * FROM calibrations WHERE device_id = ? AND version = 1",
                                      (profile.device_id,)).fetchone())
    return {
        "notice": "Calibração SINTÉTICA, exclusiva do simulador. Não é calibração física do protótipo.",
        "profile_id": profile.profile_id, "device_created": device_created,
        "calibration_created": calibration_created, "calibration": calibration,
        "database_path": str(settings.database_path),
    }
