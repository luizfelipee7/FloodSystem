CREATE TABLE weather_datasets (
    dataset_id TEXT PRIMARY KEY NOT NULL,
    manifest_json TEXT NOT NULL,
    raw_response BLOB NOT NULL,
    response_sha256 TEXT NOT NULL,
    imported_at TEXT NOT NULL
);

CREATE TABLE weather_intervals (
    dataset_id TEXT NOT NULL REFERENCES weather_datasets(dataset_id) ON DELETE RESTRICT,
    interval_index INTEGER NOT NULL,
    start_at TEXT NOT NULL,
    end_at TEXT NOT NULL,
    source_time TEXT NOT NULL,
    rain_mm TEXT NOT NULL,
    PRIMARY KEY (dataset_id, interval_index),
    UNIQUE (dataset_id, start_at)
);

CREATE TABLE simulation_runs (
    run_id TEXT PRIMARY KEY NOT NULL,
    dataset_id TEXT NOT NULL REFERENCES weather_datasets(dataset_id) ON DELETE RESTRICT,
    device_id TEXT NOT NULL UNIQUE REFERENCES devices(device_id) ON DELETE RESTRICT,
    start_at TEXT NOT NULL,
    end_at TEXT NOT NULL,
    profile_json TEXT NOT NULL,
    grid_json TEXT NOT NULL,
    source_total_mm TEXT NOT NULL,
    final_residual_mm TEXT NOT NULL,
    expected_tip_count INTEGER NOT NULL,
    expected_rain_mm TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE simulation_steps (
    run_id TEXT NOT NULL REFERENCES simulation_runs(run_id) ON DELETE RESTRICT,
    interval_index INTEGER NOT NULL,
    residual_before_mm TEXT NOT NULL,
    residual_after_mm TEXT NOT NULL,
    expected_tip_count INTEGER NOT NULL,
    expected_rain_mm TEXT NOT NULL,
    cumulative_source_mm TEXT NOT NULL,
    PRIMARY KEY (run_id, interval_index)
);

CREATE TABLE simulation_expected_tips (
    run_id TEXT NOT NULL,
    interval_index INTEGER NOT NULL,
    event_id TEXT NOT NULL,
    occurred_at TEXT NOT NULL,
    PRIMARY KEY (run_id, event_id),
    FOREIGN KEY (run_id, interval_index) REFERENCES simulation_steps(run_id, interval_index) ON DELETE RESTRICT
);

CREATE INDEX idx_simulation_expected_time ON simulation_expected_tips(run_id, occurred_at);

CREATE TRIGGER weather_datasets_no_update BEFORE UPDATE ON weather_datasets
BEGIN SELECT RAISE(ABORT, 'Source snapshots are immutable.'); END;
CREATE TRIGGER weather_datasets_no_delete BEFORE DELETE ON weather_datasets
BEGIN SELECT RAISE(ABORT, 'Preserve source snapshots.'); END;
CREATE TRIGGER weather_intervals_no_update BEFORE UPDATE ON weather_intervals
BEGIN SELECT RAISE(ABORT, 'Source intervals are immutable.'); END;
CREATE TRIGGER simulation_runs_no_update BEFORE UPDATE ON simulation_runs
BEGIN SELECT RAISE(ABORT, 'Create a new run for different parameters.'); END;
CREATE TRIGGER simulation_steps_no_update BEFORE UPDATE ON simulation_steps
BEGIN SELECT RAISE(ABORT, 'Simulation ledger is immutable.'); END;
CREATE TRIGGER simulation_expected_tips_no_update BEFORE UPDATE ON simulation_expected_tips
BEGIN SELECT RAISE(ABORT, 'Expected events are immutable.'); END;
