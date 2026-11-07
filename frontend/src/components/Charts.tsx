import { useEffect, useState } from "react";
import { ChartNoAxesCombined, CloudRain } from "lucide-react";
import type { LevelReading, Query, RainTip } from "../types";
import { number, time } from "../format";

export function LevelChart({
  readings,
  query,
}: {
  readings: LevelReading[];
  query: Query;
}) {
  const [selected, setSelected] = useState<number | null>(null);
  const [compact, setCompact] = useState(
    () => window.matchMedia("(max-width: 680px)").matches,
  );
  useEffect(() => {
    const media = window.matchMedia("(max-width: 680px)");
    const update = () => setCompact(media.matches);
    media.addEventListener("change", update);
    return () => media.removeEventListener("change", update);
  }, []);
  const valid = readings.filter((row) => row.water_level_cm !== null);
  if (!valid.length)
    return (
      <div className="chart-empty">
        <ChartNoAxesCombined size={28} />
        <strong>Nenhum nível disponível</strong>
        <span>Leituras com calibração aparecerão aqui.</span>
      </div>
    );
  const width = compact ? 360 : 760,
    left = compact ? 37 : 45,
    right = width - 25,
    top = 20,
    bottom = 205;
  const start = Date.parse(query.start),
    span = Date.parse(query.end) - start;
  const values = valid.map((row) => row.water_level_cm!);
  const minimum = Math.min(0, Math.floor(Math.min(...values) / 5) * 5);
  const maximum = Math.max(
    minimum + 5,
    Math.ceil((Math.max(...values) + 1) / 5) * 5,
  );
  const x = (at: string) =>
    left + ((Date.parse(at) - start) / span) * (right - left);
  const y = (value: number) =>
    bottom - ((value - minimum) / (maximum - minimum)) * (bottom - top);
  const groups: LevelReading[][] = [];
  let group: LevelReading[] = [];
  for (const row of readings) {
    if (
      row.water_level_cm == null ||
      (group.length &&
        group.at(-1)!.calibration_version !== row.calibration_version)
    ) {
      if (group.length) groups.push(group);
      group = [];
    }
    if (row.water_level_cm != null) group.push(row);
  }
  if (group.length) groups.push(group);
  const current = selected !== null ? valid[selected] : undefined;
  return (
    <div className="level-chart">
      <div className="chart-readout" aria-live="polite">
        {current ? (
          <>
            <b>{number(current.water_level_cm)} cm</b>
            <span>{time(current.measured_at, true)} Brasília</span>
          </>
        ) : (
          <>
            <span className="legend-dot" /> <span>Nível da água</span>
            <span className="chart-hint">Passe sobre uma leitura</span>
          </>
        )}
      </div>
      <svg
        viewBox={`0 0 ${width} 242`}
        role="img"
        aria-label="Evolução do nível em centímetros, nos horários das medições. Valores também disponíveis na tabela."
        onMouseLeave={() => setSelected(null)}
        onMouseMove={(event) => {
          const bounds = event.currentTarget.getBoundingClientRect();
          const target = ((event.clientX - bounds.left) / bounds.width) * width;
          let closest = 0;
          valid.forEach((row, i) => {
            if (
              Math.abs(x(row.measured_at) - target) <
              Math.abs(x(valid[closest].measured_at) - target)
            )
              closest = i;
          });
          setSelected(closest);
        }}
      >
        <defs>
          <linearGradient id="level-fill" x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor="#367dea" stopOpacity=".18" />
            <stop offset="100%" stopColor="#367dea" stopOpacity=".015" />
          </linearGradient>
        </defs>
        {[0, 1, 2, 3, 4].map((tick) => {
          const value = minimum + ((maximum - minimum) * tick) / 4;
          return (
            <g key={tick}>
              <line
                x1={left}
                x2={right}
                y1={y(value)}
                y2={y(value)}
                className="grid-line"
              />
              <text x={left - 14} y={y(value) + 4} textAnchor="end">
                {number(value, Number.isInteger(value) ? 0 : 2)}
              </text>
            </g>
          );
        })}
        {groups.map((segment, i) => {
          const points = segment.map(
            (row) => `${x(row.measured_at)},${y(row.water_level_cm!)}`,
          );
          return (
            <g key={i}>
              <path
                d={`M${x(segment[0].measured_at)},${bottom} L${points.join(" L")} L${x(segment.at(-1)!.measured_at)},${bottom} Z`}
                fill="url(#level-fill)"
              />
              <polyline
                points={points.join(" ")}
                fill="none"
                stroke="#2670df"
                strokeWidth="2.8"
                strokeLinejoin="round"
              />
            </g>
          );
        })}
        {valid.map((row, i) => (
          <circle
            key={row.reading_id}
            cx={x(row.measured_at)}
            cy={y(row.water_level_cm!)}
            r={selected === i ? 5 : 3.3}
            fill="white"
            stroke="#2670df"
            strokeWidth="2"
            tabIndex={0}
            onFocus={() => setSelected(i)}
            onBlur={() => setSelected(null)}
            aria-label={`${time(row.measured_at, true)} Brasília: ${number(row.water_level_cm)} centímetros`}
          >
            <title>
              {time(row.measured_at, true)} Brasília · {number(row.water_level_cm)}{" "}
              cm
            </title>
          </circle>
        ))}
        {current && (
          <line
            x1={x(current.measured_at)}
            x2={x(current.measured_at)}
            y1={top}
            y2={bottom}
            stroke="#98b9e9"
            strokeDasharray="4 4"
            pointerEvents="none"
          />
        )}
        {[0, 1, 2, 3, 4].map((tick) => (
          <text
            key={tick}
            x={left + ((right - left) * tick) / 4}
            y="233"
            textAnchor="middle"
          >
            {time(new Date(start + (span * tick) / 4), span <= 600000)}
          </text>
        ))}
      </svg>
    </div>
  );
}

export function RainChart({ tips, query }: { tips: RainTip[]; query: Query }) {
  if (!tips.length)
    return (
      <div className="chart-empty rain-empty">
        <CloudRain size={28} />
        <strong>Sem basculadas registradas</strong>
        <span>Isso não confirma ausência de chuva.</span>
      </div>
    );
  const start = Date.parse(query.start),
    end = Date.parse(query.end),
    bins = 10;
  const counts = Array.from({ length: bins }, () => 0);
  for (const tip of tips) {
    const bucket = Math.min(
      bins - 1,
      Math.max(
        0,
        Math.floor(
          ((Date.parse(tip.occurred_at) - start) / (end - start)) * bins,
        ),
      ),
    );
    counts[bucket]++;
  }
  const max = Math.max(...counts, 1);
  return (
    <div className="rain-chart">
      <svg
        viewBox="0 0 330 150"
        role="img"
        aria-label="Contagem de basculadas em dez intervalos iguais do período. Eventos individuais disponíveis na tabela."
      >
        {[0, 1, 2].map((i) => (
          <line
            key={i}
            x1="12"
            x2="318"
            y1={12 + i * 47}
            y2={12 + i * 47}
            className="grid-line"
          />
        ))}
        {counts.map((count, i) => (
          <rect
            key={i}
            x={16 + i * 30}
            y={111 - (count / max) * 90}
            width="18"
            height={(count / max) * 90}
            rx="4"
            fill={i === counts.indexOf(max) ? "#2167d2" : "#a4c1ed"}
            tabIndex={count ? 0 : undefined}
            aria-label={`${time(new Date(start + ((end - start) * i) / bins), true)}: ${count} basculadas`}
          >
            <title>
              {time(new Date(start + ((end - start) * i) / bins), true)} a{" "}
              {time(new Date(start + ((end - start) * (i + 1)) / bins), true)}{" "}
              horário de Brasília: {count} basculadas
            </title>
          </rect>
        ))}
        <text x="14" y="139">
          {time(query.start)}
        </text>
        <text x="315" y="139" textAnchor="end">
          {time(query.end)}
        </text>
      </svg>
      <p className="chart-caption">Basculadas por intervalo · horário de Brasília</p>
    </div>
  );
}
