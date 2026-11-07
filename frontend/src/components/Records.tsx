import { useMemo } from "react";
import { ArrowDown, Database } from "lucide-react";
import type { DashboardData } from "../types";
import { fullDate, number, time } from "../format";

export type RecordTab = "levels" | "tips";
const showRawDistance = import.meta.env.DEV;

export function Records({
  data,
  tab,
  onTab,
}: {
  data: DashboardData | null;
  tab: RecordTab;
  onTab: (tab: RecordTab) => void;
}) {
  const levels = useMemo(() => [...(data?.levels || [])].reverse(), [data]);
  const tips = useMemo(() => [...(data?.tips || [])].reverse(), [data]);
  const rows = tab === "levels" ? levels : tips;
  const total =
    tab === "levels"
      ? data?.summary.level.reading_count
      : data?.summary.rain.tip_count;
  return (
    <section
      className="panel records"
      id="registros"
      aria-labelledby="records-heading"
    >
      <div className="panel-heading">
        <div>
          <div className="eyebrow">DADOS DO PERÍODO</div>
          <h2 id="records-heading">Cada registro conta.</h2>
        </div>
        <span className="muted-label">
          <Database size={14} /> {total ?? "—"} registros
        </span>
      </div>
      <div className="record-toolbar">
        <span className="order-label">
          <ArrowDown size={13} /> Mais recentes primeiro
        </span>
      </div>
      <div
        className="table-scroll"
        role="region"
        id="record-panel"
        aria-label={tab === "levels" ? "Leituras de nível" : "Basculadas"}
        tabIndex={0}
      >
        <table>
          <thead>
            <tr>
              <th>
                HORÁRIO <span>Brasília</span>
              </th>
              {tab === "levels" ? (
                <>
                  {showRawDistance && <th>DISTÂNCIA BRUTA</th>}
                  <th>NÍVEL DA ÁGUA</th>
                </>
              ) : (
                <th>RECEBIDO EM</th>
              )}
              <th>CALIBRAÇÃO</th>
              <th>ORIGEM</th>
            </tr>
          </thead>
          <tbody>
            {tab === "levels"
              ? levels.map((row) => (
                  <tr key={row.reading_id}>
                    <td title={fullDate(row.measured_at)} className="mono">
                      {time(row.measured_at, true)}
                    </td>
                    {showRawDistance && <td>
                      {number(row.distance_cm)} <span className="unit">cm</span>
                    </td>}
                    <td className="table-value">
                      {number(row.water_level_cm)}{" "}
                      <span className="unit">cm</span>
                    </td>
                    <td>
                      {row.calibration_version == null
                        ? "Não calibrada"
                        : `Versão ${row.calibration_version}`}
                    </td>
                    <td>
                      <span className={`source-pill ${row.origin}`}>
                        {row.origin === "simulation" ? "Simulação" : "ESP32"}
                      </span>
                    </td>
                  </tr>
                ))
              : tips.map((row) => (
                  <tr key={row.event_id}>
                    <td title={fullDate(row.occurred_at)} className="mono">
                      {time(row.occurred_at, true)}
                    </td>
                    <td title={fullDate(row.received_at)} className="mono">
                      {time(row.received_at, true)}
                    </td>
                    <td>
                      {row.calibration_version == null
                        ? "Não calibrada"
                        : `Versão ${row.calibration_version}`}
                    </td>
                    <td>
                      <span className={`source-pill ${row.origin}`}>
                        {row.origin === "simulation" ? "Simulação" : "ESP32"}
                      </span>
                    </td>
                  </tr>
                ))}
            {!rows.length && (
              <tr>
                <td colSpan={tab === "levels" && showRawDistance ? 5 : 4} className="empty-cell">
                  {data
                    ? "Nenhum registro deste tipo no período selecionado."
                    : "Os registros aparecerão depois da consulta à API."}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <div className="table-footer">
        <div className="record-footer-left">
          <div className="record-switch" aria-label="Tipo de registro">
            <button
              type="button"
              aria-pressed={tab === "levels"}
              className={tab === "levels" ? "active" : ""}
              onClick={() => onTab("levels")}
            >
              Leituras de nível{" "}
              <span>{data?.summary.level.reading_count ?? "—"}</span>
            </button>
            <button
              type="button"
              aria-pressed={tab === "tips"}
              className={tab === "tips" ? "active" : ""}
              onClick={() => onTab("tips")}
            >
              Basculadas <span>{data?.summary.rain.tip_count ?? "—"}</span>
            </button>
          </div>
          <span>
            {rows.length
              ? `${rows.length} registro${rows.length === 1 ? "" : "s"} carregado${rows.length === 1 ? "" : "s"}`
              : "Nenhum registro carregado"}
          </span>
        </div>
      </div>
    </section>
  );
}
