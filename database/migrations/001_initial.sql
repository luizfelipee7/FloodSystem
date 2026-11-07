CREATE TABLE devices (
    device_id TEXT PRIMARY KEY NOT NULL CHECK (length(trim(device_id)) > 0),
    name TEXT NOT NULL CHECK (length(trim(name)) > 0),
    origin TEXT NOT NULL CHECK (origin IN ('simulation', 'esp32')),
    created_at TEXT NOT NULL,
    UNIQUE (device_id, origin)
);

CREATE TABLE calibrations (
    device_id TEXT NOT NULL REFERENCES devices(device_id) ON DELETE RESTRICT,
    version INTEGER NOT NULL CHECK (typeof(version) = 'integer' AND version > 0),
    valid_from TEXT NOT NULL,
    received_at TEXT NOT NULL,
    h0_cm REAL CHECK (h0_cm IS NULL OR (typeof(h0_cm) IN ('real', 'integer') AND h0_cm > 0 AND h0_cm < 1e308)),
    k_mm_per_tip REAL CHECK (k_mm_per_tip IS NULL OR (typeof(k_mm_per_tip) IN ('real', 'integer') AND k_mm_per_tip > 0 AND k_mm_per_tip < 1e308)),
    CHECK (h0_cm IS NOT NULL OR k_mm_per_tip IS NOT NULL),
    PRIMARY KEY (device_id, version),
    UNIQUE (device_id, valid_from)
);

CREATE TABLE level_readings (
    device_id TEXT NOT NULL,
    reading_id TEXT NOT NULL CHECK (length(trim(reading_id)) > 0),
    measured_at TEXT NOT NULL,
    received_at TEXT NOT NULL,
    distance_cm REAL NOT NULL CHECK (typeof(distance_cm) IN ('real', 'integer') AND distance_cm >= 0 AND distance_cm < 1e308),
    water_level_cm REAL CHECK (water_level_cm IS NULL OR (typeof(water_level_cm) IN ('real', 'integer') AND abs(water_level_cm) < 1e308)),
    origin TEXT NOT NULL CHECK (origin IN ('simulation', 'esp32')),
    calibration_version INTEGER,
    CHECK (water_level_cm IS NULL OR calibration_version IS NOT NULL),
    PRIMARY KEY (device_id, reading_id),
    FOREIGN KEY (device_id, origin) REFERENCES devices(device_id, origin) ON DELETE RESTRICT,
    FOREIGN KEY (device_id, calibration_version) REFERENCES calibrations(device_id, version) ON DELETE RESTRICT
);

CREATE TABLE rain_tip_events (
    device_id TEXT NOT NULL,
    event_id TEXT NOT NULL CHECK (length(trim(event_id)) > 0),
    occurred_at TEXT NOT NULL,
    received_at TEXT NOT NULL,
    origin TEXT NOT NULL CHECK (origin IN ('simulation', 'esp32')),
    calibration_version INTEGER,
    PRIMARY KEY (device_id, event_id),
    FOREIGN KEY (device_id, origin) REFERENCES devices(device_id, origin) ON DELETE RESTRICT,
    FOREIGN KEY (device_id, calibration_version) REFERENCES calibrations(device_id, version) ON DELETE RESTRICT
);

CREATE INDEX idx_level_readings_device_time ON level_readings(device_id, measured_at);
CREATE INDEX idx_rain_tip_events_device_time ON rain_tip_events(device_id, occurred_at);

CREATE TRIGGER calibrations_no_update BEFORE UPDATE ON calibrations
BEGIN
    SELECT RAISE(ABORT, 'Calibrations are immutable; append a new version.');
END;

CREATE TRIGGER calibrations_no_delete BEFORE DELETE ON calibrations
BEGIN
    SELECT RAISE(ABORT, 'Calibrations are immutable; preserve the history.');
END;
