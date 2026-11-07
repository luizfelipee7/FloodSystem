export type Origin = "simulation" | "esp32";
export interface ExperimentItem {
  run_id: string;
  device_id: string;
  start_at: string;
  end_at: string;
  source_total_mm: string;
  expected_tip_count: number;
  created_at: string;
}
export interface ExperimentHour {
  interval_index: number;
  start_at: string;
  end_at: string;
  source_time: string;
  rain_mm: string;
  expected_tip_count: number;
  received_tip_count: number;
  received_rain_mm: string;
  source_intensity_mm_h: string;
  tip_intensity_mm_h: string | null;
  residual_before_mm: string;
  residual_after_mm: string;
}
export interface Experiment extends ExperimentItem {
  dataset_id: string;
  status: "complete" | "pending";
  received_tip_count: number;
  received_rain_mm: string;
  final_residual_mm: string;
  expected_rain_mm: string;
  notice: string;
  profile: {
    generator_version: string;
    h0_cm: string;
    k_mm_per_tip: string;
    initial_residual_mm: string;
    distribution: string;
    analysis_window_minutes: number;
  };
  source: {
    model: string;
    variable: string;
    downloaded_at: string;
    response_sha256: string;
    request_url: string;
    citation: string;
    license: string;
    request: { parameters: { latitude: number; longitude: number } };
  };
  grid: { latitude: string; longitude: string; elevation: string };
  intervals: ExperimentHour[];
}
export interface Metric {
  value: number | null;
  unit: "cm" | "mm" | "mm/h" | "cm/min";
  status: "available" | "unavailable";
  reason: string | null;
}
export interface Observation {
  device_id: string;
  received_at: string;
  origin: Origin;
  calibration_version: number | null;
}
export interface LevelReading extends Observation {
  reading_id: string;
  measured_at: string;
  distance_cm: number;
  water_level_cm: number | null;
}
export interface RainTip extends Observation {
  event_id: string;
  occurred_at: string;
}
export interface RainSummary {
  tip_count: number;
  uncalibrated_tip_count: number;
  calibrations: {
    calibration_version: number | null;
    k_mm_per_tip: number | null;
    tip_count: number;
  }[];
  accumulated_rainfall: Metric;
}
export interface LevelEndpoint {
  reading_id: string | null;
  measured_at: string;
  distance_cm: number | null;
  calibration_version: number | null;
  h0_cm: number | null;
  level: Metric;
}
export interface Summary {
  device_id: string;
  origin: Origin;
  start: string;
  end: string;
  rain: RainSummary;
  intensity: {
    window_minutes: number;
    start: string;
    end: string;
    rain: RainSummary | null;
    intensity: Metric;
  };
  level: {
    reading_count: number;
    uncalibrated_reading_count: number;
    initial: LevelEndpoint | null;
    final: LevelEndpoint | null;
    elapsed_seconds: number | null;
    level_change: Metric;
    velocity: Metric;
  };
}
export interface Query {
  device_id: string;
  start: string;
  end: string;
  window_minutes: number;
}
export interface Page<T> {
  items: T[];
  has_more: boolean;
  limit: number;
  offset: number;
}
export interface DashboardData {
  summary: Summary;
  recentLevel: Summary["level"] | null;
  levels: LevelReading[];
  tips: RainTip[];
  levelsTruncated: boolean;
  tipsTruncated: boolean;
  fetchedAt: Date;
}
