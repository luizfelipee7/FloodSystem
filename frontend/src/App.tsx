import { useEffect, useMemo, useRef, useState } from "react";
import type { ReactNode } from "react";
import {
  Activity,
  ArrowDownToLine,
  ArrowRight,
  ArrowUpRight,
  Beaker,
  BookOpen,
  CalendarDays,
  ChevronDown,
  ChevronRight,
  CircleHelp,
  Clock3,
  CloudRain,
  Database,
  Droplets,
  Gauge,
  Menu,
  Moon,
  Radio,
  RefreshCw,
  Settings2,
  Sun,
  Waves,
  WifiOff,
  X,
} from "lucide-react";
import { latestLevelReading, latestRainTip, loadDashboard } from "./services/api";
import type { DashboardData, Metric, Query } from "./types";
import {
  brasiliaToUtc,
  date,
  number,
  reasonText,
  time,
} from "./format";
import { LevelChart, RainChart } from "./components/Charts";
import { Records } from "./components/Records";
import type { RecordTab } from "./components/Records";
import { WaterTank } from "./components/WaterTank";

const periods = {
  rain: {
    label: "Simulação · chuva em 5 min",
    start: "2026-10-08T13:00:00Z",
    end: "2026-10-08T13:05:00Z",
  },
  dry: {
    label: "Simulação · sem chuva",
    start: "2026-10-08T12:00:00Z",
    end: "2026-10-08T12:05:00Z",
  },
  rise: {
    label: "Simulação · subida e descida",
    start: "2026-10-08T14:00:00Z",
    end: "2026-10-08T14:10:01Z",
  },
  delay: {
    label: "Simulação · chuva com atraso de 2 min",
    start: "2026-10-08T15:00:00Z",
    end: "2026-10-08T15:14:01Z",
  },
};
type View = "live" | "history";
type Theme = "light" | "dark";
type HistoryMode = keyof typeof periods | "day" | "custom";
interface Filters {
  device: string;
  liveRangeMinutes: number;
  window: number;
  historyMode: HistoryMode;
  day: string;
  start: string;
  end: string;
}
function brasiliaDay(value: Date) {
  const parts = new Intl.DateTimeFormat("en-US", {
    timeZone: "America/Sao_Paulo",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(value);
  const field = (type: string) => parts.find((part) => part.type === type)?.value;
  return `${field("year")}-${field("month")}-${field("day")}`;
}

function nextDay(day: string) {
  const date = new Date(`${day}T12:00:00Z`);
  if (Number.isNaN(date.getTime()) || date.toISOString().slice(0, 10) !== day)
    throw new Error("Data inválida");
  return new Date(date.getTime() + 86400000).toISOString().slice(0, 10);
}

const initial: Filters = {
  device: import.meta.env.VITE_DEFAULT_DEVICE_ID || (import.meta.env.PROD ? "esp32-01" : "simulador-01"),
  liveRangeMinutes: 30,
  window: 5,
  historyMode: "day",
  day: brasiliaDay(new Date()),
  start: "2026-10-08T10:00:00",
  end: "2026-10-08T10:05:00",
};

function makeQuery(view: View, filters: Filters): Query {
  let start: string, end: string;
  if (view === "live") {
    const now = Date.now();
    start = new Date(now - filters.liveRangeMinutes * 60000).toISOString();
    end = new Date(now).toISOString();
  } else if (filters.historyMode === "day") {
    start = brasiliaToUtc(`${filters.day}T00:00:00`);
    end = brasiliaToUtc(`${nextDay(filters.day)}T00:00:00`);
  } else if (filters.historyMode === "custom") {
    start = brasiliaToUtc(filters.start);
    end = brasiliaToUtc(filters.end);
  } else ({ start, end } = periods[filters.historyMode]);
  return {
    device_id: filters.device,
    start,
    end,
    window_minutes: filters.window,
  };
}

function MetricCard({
  icon,
  label,
  metric,
  unit,
  foot,
  tag,
  loading,
  visual,
}: {
  icon: ReactNode;
  label: string;
  metric?: Metric;
  unit: string;
  foot: string;
  tag?: string;
  loading: boolean;
  visual?: ReactNode;
}) {
  const value = loading ? (
    <div className="skeleton metric-skeleton" />
  ) : (
    <div className="metric-value">
      {number(metric?.value)}
      <span>{unit}</span>
    </div>
  );
  return (
    <article className={`metric-card${visual ? " metric-card--visual" : ""}`}>
      <div className="metric-top">
        <span className="metric-icon">{icon}</span>
        {tag && <span className="metric-tag">{tag}</span>}
      </div>
      <h2>{label}</h2>
      {visual ? <div className="water-metric-layout">{value}{visual}</div> : value}
      <div className="metric-foot">
        {!loading && metric?.value == null ? (
          <span className="unavailable" title={reasonText(metric?.reason)}>
            {reasonText(metric?.reason)}
          </span>
        ) : (
          foot
        )}
      </div>
    </article>
  );
}

function exportRecords(data: DashboardData) {
  const rows: (string | number | null)[][] = [
    [
      "tipo",
      "dispositivo",
      "id",
      "medido_em_utc",
      "recebido_em_utc",
      "distancia_cm",
      "nivel_cm",
      "origem",
      "calibracao",
    ],
  ];
  data.levels.forEach((r) =>
    rows.push([
      "leitura",
      r.device_id,
      r.reading_id,
      r.measured_at,
      r.received_at,
      r.distance_cm,
      r.water_level_cm,
      r.origin,
      r.calibration_version,
    ]),
  );
  data.tips.forEach((r) =>
    rows.push([
      "basculada",
      r.device_id,
      r.event_id,
      r.occurred_at,
      r.received_at,
      null,
      null,
      r.origin,
      r.calibration_version,
    ]),
  );
  const csv = rows
    .map((row) =>
      row
        .map((value) => {
          let cell = value == null ? "" : String(value);
          if (typeof value === "string" && /^[=+\-@\t\r]/.test(cell))
            cell = "'" + cell;
          return `"${cell.replace(/"/g, '""')}"`;
        })
        .join(";"),
    )
    .join("\r\n");
  const url = URL.createObjectURL(
    new Blob(["\uFEFF" + csv], { type: "text/csv;charset=utf-8" }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = `floodsystem-${data.summary.origin}-${data.summary.start.slice(0, 10)}.csv`;
  link.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export default function App() {
  const [theme, setTheme] = useState<Theme>(() =>
    document.documentElement.dataset.theme === "dark" ? "dark" : "light",
  );
  const [view, setView] = useState<View>(() =>
    new URLSearchParams(window.location.search).get("view") === "history" ? "history" : "live",
  );
  const [filters, setFilters] = useState<Filters>(initial);
  const [draft, setDraft] = useState<Filters>(initial);
  const [refresh, setRefresh] = useState(0);
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterError, setFilterError] = useState("");
  const [tab, setTab] = useState<RecordTab>("levels");
  const [mobileMenu, setMobileMenu] = useState(false);
  const [auto, setAuto] = useState(true);
  const [advanced, setAdvanced] = useState(false);
  const dialog = useRef<HTMLDialogElement>(null);
  const latestTipSeen = useRef<string | null | undefined>(undefined);
  const latestLevelSeen = useRef<string | null | undefined>(undefined);
  const dashboardLoading = useRef(true);
  const pendingTelemetryRefresh = useRef(false);
  const query = useMemo(() => makeQuery(view, filters), [view, filters, refresh]);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem("floodsystem-theme", theme);
    } catch {
      // The choice still works for this page when browser storage is unavailable.
    }
  }, [theme]);

  const live = view === "live";
  const dirty = live
    ? draft.device !== filters.device || draft.liveRangeMinutes !== filters.liveRangeMinutes || draft.window !== filters.window
    : draft.device !== filters.device || draft.historyMode !== filters.historyMode || draft.day !== filters.day || draft.start !== filters.start || draft.end !== filters.end;

  useEffect(() => {
    const controller = new AbortController();
    dashboardLoading.current = true;
    setLoading(true);
    setError(null);
    loadDashboard(query, controller.signal, live)
      .then((result) => {
        if (!controller.signal.aborted) setData(result);
      })
      .catch((failure: unknown) => {
        if (!controller.signal.aborted)
          setError(
            failure instanceof Error
              ? failure.message
              : "Não foi possível carregar os dados.",
          );
      })
      .finally(() => {
        if (!controller.signal.aborted) {
          dashboardLoading.current = false;
          setLoading(false);
        }
      });
    return () => controller.abort();
  }, [query, live]);
  useEffect(() => {
    if (loading || !pendingTelemetryRefresh.current) return;
    pendingTelemetryRefresh.current = false;
    setRefresh((value) => value + 1);
  }, [loading]);
  useEffect(() => {
    if (!live || !auto) return;
    const refreshVisible = () => {
      if (document.visibilityState === "visible")
        setRefresh((value) => value + 1);
    };
    const timer = window.setInterval(refreshVisible, 15000);
    document.addEventListener("visibilitychange", refreshVisible);
    return () => {
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", refreshVisible);
    };
  }, [live, auto]);

  useEffect(() => {
    if (!live || !auto) return;
    const controller = new AbortController();
    let checking = false;
    latestTipSeen.current = undefined;
    latestLevelSeen.current = undefined;
    pendingTelemetryRefresh.current = false;

    const refreshDashboard = () => {
      if (dashboardLoading.current) pendingTelemetryRefresh.current = true;
      else setRefresh((value) => value + 1);
    };
    const checkTelemetry = async () => {
      if (document.visibilityState !== "visible" || checking) return;
      checking = true;
      try {
        const [tipResult, levelResult] = await Promise.allSettled([
          latestRainTip(filters.device, controller.signal),
          latestLevelReading(filters.device, controller.signal),
        ]);
        if (controller.signal.aborted) return;
        let changed = false;
        if (tipResult.status === "fulfilled") {
          const tip = tipResult.value;
          const fingerprint = tip ? `${tip.event_id}:${tip.received_at}` : null;
          if (latestTipSeen.current !== fingerprint) {
            changed ||= latestTipSeen.current !== undefined || fingerprint !== null;
            latestTipSeen.current = fingerprint;
          }
        }
        if (levelResult.status === "fulfilled") {
          const level = levelResult.value;
          const fingerprint = level ? `${level.reading_id}:${level.received_at}` : null;
          if (latestLevelSeen.current !== fingerprint) {
            changed ||= latestLevelSeen.current !== undefined || fingerprint !== null;
            latestLevelSeen.current = fingerprint;
          }
        }
        if (changed) refreshDashboard();
      } catch {
        // A consulta completa continua sendo feita a cada 15 segundos.
      } finally {
        checking = false;
      }
    };
    const timer = window.setInterval(checkTelemetry, 2000);
    document.addEventListener("visibilitychange", checkTelemetry);
    void checkTelemetry();
    return () => {
      controller.abort();
      window.clearInterval(timer);
      document.removeEventListener("visibilitychange", checkTelemetry);
      pendingTelemetryRefresh.current = false;
    };
  }, [live, auto, filters.device]);

  useEffect(() => {
    if (!dirty) {
      setFilterError("");
      return;
    }

    setFilterError("");
    const candidate: Filters = live
      ? { ...filters, device: draft.device.trim(), liveRangeMinutes: draft.liveRangeMinutes, window: draft.window }
      : { ...filters, device: draft.device.trim(), historyMode: draft.historyMode,
          day: draft.day, start: draft.start, end: draft.end };
    const delay = draft.device !== filters.device ? 550
      : !live && draft.historyMode === "custom" && (draft.start !== filters.start || draft.end !== filters.end) ? 350
      : 0;
    const timer = window.setTimeout(() => {
      if (!candidate.device || candidate.device.length > 128) {
        setFilterError("Informe um dispositivo com 1 a 128 caracteres.");
        return;
      }
      try {
        const next = makeQuery(view, candidate);
        const start = Date.parse(next.start);
        const end = Date.parse(next.end);
        if (!Number.isFinite(start) || !Number.isFinite(end) || start >= end) throw new Error();
      } catch {
        setFilterError("Informe datas válidas no horário de Brasília, com o início anterior ao fim.");
        return;
      }
      setData(null);
      setDraft(candidate);
      setFilters(candidate);
    }, delay);
    return () => window.clearTimeout(timer);
  }, [dirty, draft, filters, live, view]);
  function navigate(tabName?: RecordTab) {
    if (tabName) setTab(tabName);
    setMobileMenu(false);
  }
  function switchView(next: View) {
    if (view === next) {
      setMobileMenu(false);
      return;
    }
    setView(next);
    window.history.replaceState(null, "", next === "history" ? "/?view=history" : "/");
    setDraft(filters);
    setData(null);
    setError(null);
    setLoading(true);
    setFilterError("");
    setMobileMenu(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }
  function openSimulatedHistory() {
    const next = { ...filters, device: "simulador-01", historyMode: "rain" as const };
    setDraft(next);
    setFilters(next);
    setView("history");
    setData(null);
    setError(null);
    setLoading(true);
    setMobileMenu(false);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }
  const summary = data?.summary;
  const displayedStart = summary?.start ?? query.start;
  const displayedEnd = summary?.end ?? query.end;
  const isSimulation = summary?.origin === "simulation";
  const noData =
    summary?.level.reading_count === 0 && summary?.rain.tip_count === 0;
  const speed = live ? data?.recentLevel?.velocity.value : summary?.level.velocity.value;
  const movement =
    speed == null
      ? "Sem tendência calculável"
      : speed > 0
        ? "Subida no período"
        : speed < 0
          ? "Descida no período"
          : "Extremos no mesmo nível";
  const ageMinutes = summary?.level.final
    ? Math.max(0, Math.floor((Date.now() - Date.parse(summary.level.final.measured_at)) / 60000))
    : null;
  const stale = live && ageMinutes !== null && ageMinutes >= 5;
  const latestReading = data?.levels.find(
    (reading) => reading.reading_id === summary?.level.final?.reading_id,
  );

  return (
    <div className="app-shell">
      <a className="skip-link" href="#conteudo">
        Ir para o conteúdo
      </a>
      <aside className={`sidebar ${mobileMenu ? "open" : ""}`}>
        <a href="#conteudo" className="brand" onClick={() => navigate()}>
          <span className="brand-mark">
            <Waves size={24} />
          </span>
          <span>
            Flood<span className="brand-light">System</span>
            <small>OBSERVAR. COMPREENDER.</small>
          </span>
        </a>
        <div className="nav-label">WORKSPACE</div>
        <nav aria-label="Navegação principal">
          <button
            type="button"
            className={`nav-item ${live ? "selected" : ""}`}
            aria-current={live ? "page" : undefined}
            onClick={() => switchView("live")}
          >
            <Radio size={18} /> Tempo real
            {live && <span className="nav-active-dot" />}
          </button>
          <button
            type="button"
            className={`nav-item ${!live ? "selected" : ""}`}
            aria-current={!live ? "page" : undefined}
            onClick={() => switchView("history")}
          >
            <CalendarDays size={18} /> Histórico
            {!live && <span className="nav-active-dot" />}
          </button>
          {import.meta.env.VITE_EXPERIMENTS_ENABLED === "true" && <a
            className="nav-item"
            href="/ensaios/"
            onClick={() => setMobileMenu(false)}
          >
            <Beaker size={18} /> Ensaios meteorológicos
          </a>}
          <a
            className="nav-item"
            href="#registros"
            onClick={() => navigate("levels")}
          >
            <Activity size={18} /> Leituras de nível
          </a>
          <a
            className="nav-item"
            href="#registros"
            onClick={() => navigate("tips")}
          >
            <CloudRain size={18} /> Basculadas
          </a>
        </nav>
        <div className="sidebar-divider" />
        <div className="nav-label">SOBRE O PROJETO</div>
        <button
          className="nav-item"
          onClick={() => {
            dialog.current?.showModal();
            setMobileMenu(false);
          }}
        >
          <BookOpen size={18} /> Como interpretar{" "}
          <ArrowUpRight size={14} className="nav-end" />
        </button>
        <div className="sidebar-bottom">
          <div className="project-note">
            <span className="project-note-icon">
              <Droplets size={21} />
            </span>
            <h3>Da leitura ao entendimento.</h3>
            <p>Um olhar sobre o comportamento da chuva e da água.</p>
            <span>MVP · Engenharia da Computação</span>
          </div>
          <div className="sidebar-device">
            <span className="device-dot" />
            <div>
              <strong>{filters.device}</strong>
              <span>
                {summary
                  ? isSimulation
                    ? "Dispositivo de simulação"
                    : "Dispositivo ESP32"
                  : "Dispositivo selecionado"}
              </span>
            </div>
            <ChevronRight size={15} />
          </div>
        </div>
      </aside>
      {mobileMenu && (
        <button
          className="mobile-backdrop"
          aria-label="Fechar menu"
          onClick={() => setMobileMenu(false)}
        />
      )}
      <div className="workspace">
        <header className="topbar">
          <div className="breadcrumbs">
            <button
              className="icon-button mobile-menu-button"
              aria-label="Abrir menu"
              aria-expanded={mobileMenu}
              onClick={() => setMobileMenu(!mobileMenu)}
            >
              <Menu size={21} />
            </button>
            <span>Monitoramento</span>
            <ChevronRight size={12} />
            <strong>{live ? "Tempo real" : "Histórico"}</strong>
          </div>
          <div className="topbar-right">
            <button
              type="button"
              className="theme-toggle"
              onClick={() => setTheme(theme === "light" ? "dark" : "light")}
              aria-label={theme === "light" ? "Ativar modo escuro" : "Ativar modo claro"}
              title={theme === "light" ? "Ativar modo escuro" : "Ativar modo claro"}
            >
              {theme === "light" ? <Moon size={17} /> : <Sun size={17} />}
              <span>{theme === "light" ? "Modo escuro" : "Modo claro"}</span>
            </button>
            <span
              className={`connection ${error ? "offline" : loading ? "pending" : ""}`}
            >
              <i />
              {error
                ? "Consulta indisponível"
                : loading
                  ? "Conectando"
                  : "API conectada"}
            </span>
            <span className="topbar-divider" />
            <span className="project-avatar">FS</span>
            <div className="project-title">
              <strong>Projeto FloodSystem</strong>
              <span>Painel de monitoramento</span>
            </div>
          </div>
        </header>
        <main id="conteudo">
          <section className="page-heading">
            <div>
              <div className="eyebrow">{live ? "ACOMPANHAMENTO RECENTE" : "CONSULTA POR DATA"}</div>
              <h1>
                {live ? "O que chega agora" : "O que aconteceu no dia"}<span>.</span>
              </h1>
              <p>
                {live
                  ? "Últimas medições, com atualização automática e horário de recebimento."
                  : import.meta.env.DEV
                    ? "Explore um dia no horário de Brasília ou revisite um cenário simulado."
                    : "Explore os registros de um dia ou intervalo no horário de Brasília."}
              </p>
            </div>
            <button
              className="button export-button"
              disabled={!data || loading}
              onClick={() => data && exportRecords(data)}
              title="Exporta os registros carregados, identificando a origem"
            >
              <ArrowDownToLine size={16} /> Exportar dados
            </button>
          </section>

          <div
            className={`context-banner ${isSimulation ? "simulation-banner" : ""}`}
            aria-live="polite"
          >
            <span className="context-icon">
              {isSimulation ? <Beaker size={19} /> : <Radio size={19} />}
            </span>
            <div>
              <strong>
                {loading
                  ? "Consultando os registros do dispositivo"
                  : error
                    ? "Aguardando conexão com o serviço de dados"
                    : isSimulation
                      ? "Ambiente de simulação"
                      : "Dispositivo ESP32 selecionado"}
              </strong>
              <p>
                {isSimulation
                  ? live
                    ? "Dados sintéticos. Cenários com horários antigos aparecem no Histórico, não como medições de agora."
                    : "Dados sintéticos para desenvolvimento. Não representam medições reais do protótipo."
                  : live
                    ? "A API pode estar conectada mesmo sem leituras recentes do sensor. Confira o horário da última medição."
                    : "Os indicadores refletem apenas os registros do período selecionado."}
              </p>
            </div>
            <span className="context-label">
              {isSimulation ? "DADOS SINTÉTICOS" : "PROJETO MVP"}
            </span>
          </div>

          <div className="filters">
            <div className="filter-main">
              {live ? (
                <>
                  <label className="filter-field period-field">
                    <span><Clock3 size={13} /> INTERVALO DOS GRÁFICOS</span>
                    <div className="select-wrap">
                      <select
                        aria-label="Intervalo dos gráficos"
                        value={draft.liveRangeMinutes}
                        onChange={(event) => setDraft({ ...draft, liveRangeMinutes: Number(event.target.value) })}
                      >
                        <option value={30}>Últimos 30 minutos</option>
                        <option value={60}>Última hora</option>
                        <option value={1440}>Últimas 24 horas</option>
                      </select>
                      <ChevronDown size={14} />
                    </div>
                  </label>
                  <label className="filter-field window-field">
                    <span><CloudRain size={13} /> JANELA DA INTENSIDADE</span>
                    <div className="select-wrap">
                      <select
                        aria-label="Janela de intensidade da chuva"
                        value={draft.window}
                        onChange={(event) => setDraft({ ...draft, window: Number(event.target.value) })}
                      >
                        {[1, 5, 10, 15, 30, 60].map((value) => (
                          <option key={value} value={value}>
                            {value} {value === 1 ? "minuto" : "minutos"}
                          </option>
                        ))}
                      </select>
                      <ChevronDown size={14} />
                    </div>
                  </label>
                </>
              ) : (
                <>
                  <label className="filter-field period-field">
                    <span><CalendarDays size={13} /> CONSULTA HISTÓRICA</span>
                    <div className="select-wrap">
                      <select
                        aria-label="Tipo de consulta histórica"
                        value={draft.historyMode}
                        onChange={(event) => setDraft({ ...draft, historyMode: event.target.value as HistoryMode })}
                      >
                        <option value="day">Dia completo</option>
                        {import.meta.env.DEV && <optgroup label="Cenários de simulação já armazenados">
                          {Object.entries(periods).map(([id, period]) => (
                            <option key={id} value={id}>{period.label}</option>
                          ))}
                        </optgroup>}
                        <option value="custom">Intervalo personalizado</option>
                      </select>
                      <ChevronDown size={14} />
                    </div>
                  </label>
                  {draft.historyMode === "day" && (
                    <label className="filter-field day-field">
                      <span><CalendarDays size={13} /> ANO, MÊS E DIA · BRASÍLIA</span>
                      <input
                        type="date"
                        aria-label="Data do histórico em Brasília"
                        value={draft.day}
                        onChange={(event) => setDraft({ ...draft, day: event.target.value })}
                        required
                      />
                    </label>
                  )}
                </>
              )}
              <button
                type="button"
                className={`button filters-toggle ${advanced ? "pressed" : ""}`}
                onClick={() => setAdvanced(!advanced)}
                aria-expanded={advanced}
              >
                <Settings2 size={16} /> Dispositivo
              </button>
            </div>
            {(advanced || (!live && draft.historyMode === "custom")) && (
              <div className="advanced-filters">
                <label>
                  Identificador do dispositivo
                  <input
                    value={draft.device}
                    onChange={(event) =>
                      setDraft({ ...draft, device: event.target.value })
                    }
                    maxLength={128}
                    required
                  />
                </label>
                {!live && draft.historyMode === "custom" && (
                  <>
                    <label>
                      Início (horário de Brasília)
                      <input
                        type="datetime-local"
                        step="1"
                        value={draft.start}
                        onChange={(event) =>
                          setDraft({ ...draft, start: event.target.value })
                        }
                        required
                      />
                    </label>
                    <label>
                      Fim, exclusivo (horário de Brasília)
                      <input
                        type="datetime-local"
                        step="1"
                        value={draft.end}
                        onChange={(event) =>
                          setDraft({ ...draft, end: event.target.value })
                        }
                        required
                      />
                    </label>
                  </>
                )}
              </div>
            )}
            {filterError && (
              <p className="form-error" role="alert">
                {filterError}
              </p>
            )}
            {!filterError && (
              <p className={`filter-feedback${dirty || loading ? " is-updating" : ""}`} role="status">
                <span className="filter-feedback-dot" />
                {dirty ? "Aplicando filtros automaticamente..." : loading ? "Consultando dados..." : "Filtros aplicados automaticamente"}
              </p>
            )}
          </div>

          <div className="period-status">
            <span>
              <span className="period-tag">
                {live ? "TEMPO REAL" : "HISTÓRICO"}
              </span>
              {live
                ? `Gráficos: últimos ${filters.liveRangeMinutes === 1440 ? "24 horas" : `${filters.liveRangeMinutes} minutos`} · ${date(displayedEnd)}`
                : filters.historyMode === "day"
                  ? `Dia ${date(displayedStart)} · 00:00 até 00:00 do dia seguinte`
                  : `${date(displayedStart)} — ${date(new Date(Date.parse(displayedEnd) - 1))}`}
              <span className="status-dot">·</span>
              {live ? `Até ${time(displayedEnd, true)}` : filters.historyMode === "day" ? "" : `${time(displayedStart, true)} — ${time(displayedEnd, true)}`} · Brasília
            </span>
            <div>
              {live && (
                <label className="auto-label">
                  <input
                    type="checkbox"
                    checked={auto}
                    onChange={(event) => setAuto(event.target.checked)}
                  />{" "}
                  Ao vivo · 2 s
                </label>
              )}
              <button
                className="refresh-button"
                onClick={() => setRefresh((value) => value + 1)}
                disabled={loading}
              >
                <RefreshCw size={13} className={loading ? "spinning" : ""} />
                {loading ? "Atualizando" : "Atualizar"}
              </button>
            </div>
          </div>

          {error && (
            <section className="error-state" role="alert">
              <WifiOff size={25} />
              <div>
                <h2>Não conseguimos buscar as leituras.</h2>
                <p>{error}</p>
                <p>
                  Se for a primeira execução, prepare o dispositivo no backend
                  antes de consultar.
                </p>
              </div>
              <button
                className="button"
                onClick={() => setRefresh((value) => value + 1)}
              >
                Tentar novamente
              </button>
            </section>
          )}
          {noData && (
            <section className="empty-notice">
              <Database size={20} />
              <div>
                <strong>Este período ainda não tem registros.</strong>
                <p>
                  {live
                    ? "Nenhuma medição recente chegou para este dispositivo. Para acompanhar o ESP32, informe seu identificador em Dispositivo."
                    : "Escolha outra data ou intervalo. Nenhum valor foi preenchido automaticamente."}
                </p>
                {import.meta.env.DEV && live && isSimulation && (
                  <button type="button" className="inline-action" onClick={openSimulatedHistory}>
                    Ver cenário simulado no Histórico <ArrowRight size={13} />
                  </button>
                )}
              </div>
            </section>
          )}
          {stale && (
            <p className="stale-notice">
              <Clock3 size={15} /> A última leitura foi medida há cerca de {ageMinutes} minutos.
              O nível exibido não confirma a condição atual.
            </p>
          )}
          {(data?.levelsTruncated || data?.tipsTruncated) && (
            <p className="stale-notice">
              Gráficos, tabelas e exportação limitados aos primeiros 10.000
              registros por tipo. Reduza o período. Os indicadores resumem todo
              o intervalo.
            </p>
          )}

          <section
            className="metrics-grid"
            aria-label={live ? "Indicadores recentes" : "Resumo histórico"}
            aria-busy={loading}
          >
            <MetricCard
              icon={<Waves size={22} />}
              label={live ? "Nível mais recente da água" : "Nível da água"}
              metric={summary?.level.final?.level}
              unit="cm"
              tag={live ? "ÚLTIMA LEITURA" : "FIM DO PERÍODO"}
              foot={
                summary?.level.final
                  ? live
                    ? latestReading
                      ? `Medida às ${time(latestReading.measured_at, true)} · recebida às ${time(latestReading.received_at, true)} · Brasília`
                      : `Medida às ${time(summary.level.final.measured_at, true)} · Brasília`
                    : `Medição às ${time(summary.level.final.measured_at, true)} · inicial: ${number(summary.level.initial?.level.value)} cm`
                  : "Última leitura do período"
              }
              loading={loading && !data}
              visual={live ? <WaterTank levelCm={summary?.level.final?.level.value ?? null} stale={stale} residualReference={filters.device === "esp32-01"} /> : undefined}
            />
            <MetricCard
              icon={<CloudRain size={22} />}
              label={live ? "Intensidade da chuva" : "Chuva acumulada"}
              metric={live ? summary?.intensity.intensity : summary?.rain.accumulated_rainfall}
              unit={live ? "mm/h" : "mm"}
              tag={live ? `JANELA DE ${filters.window} MIN` : "TOTAL DO PERÍODO"}
              foot={live ? `Janela encerrada às ${time(summary?.intensity.end ?? displayedEnd)} · Brasília` : `${summary?.rain.tip_count ?? "—"} basculadas registradas`}
              loading={loading && !data}
            />
            <MetricCard
              icon={<Gauge size={22} />}
              label={live ? "Velocidade recente do nível" : "Velocidade média no período"}
              metric={live ? data?.recentLevel?.velocity : summary?.level.velocity}
              unit="cm/min"
              tag={live ? "ÚLTIMOS 5 MIN" : "PRIMEIRA À ÚLTIMA LEITURA"}
              foot={live ? movement : `${movement} · variação: ${number(summary?.level.level_change.value)} cm`}
              loading={loading && !data}
            />
          </section>

          <section
            className="visuals-grid"
            aria-label="Gráficos de nível e basculadas"
          >
            <article className="panel level-panel">
              <div className="panel-heading">
                <div>
                  <div className="eyebrow">COMPORTAMENTO DA ÁGUA</div>
                  <h2>Evolução do nível</h2>
                </div>
                <span className="chart-unit">
                  cm <span>/ Brasília</span>
                </span>
              </div>
              {loading && !data ? (
                <div className="skeleton chart-skeleton" />
              ) : (
                <LevelChart readings={data?.levels || []} query={query} />
              )}
              <div className="chart-footer">
                <span>
                  <span className="legend-dot" /> Leituras registradas no
                  período
                </span>
                <span>
                  {summary?.level.reading_count ?? "—"} observações{" "}
                  <span className="status-dot">·</span> intervalos reais
                </span>
              </div>
            </article>
            <article className="panel rain-panel">
              <div className="panel-heading">
                <div>
                  <div className="eyebrow">PRECIPITAÇÃO</div>
                  <h2>A chuva em detalhe</h2>
                </div>
                <CloudRain size={20} className="subtle-icon" />
              </div>
              <div className="rain-total">
                <span>
                  {loading && !data
                    ? "—"
                    : number(summary?.rain.accumulated_rainfall.value)}
                  <small>mm</small>
                </span>
                <p>Acumulado no período</p>
              </div>
              {loading && !data ? (
                <div className="skeleton rain-skeleton" />
              ) : (
                <RainChart tips={data?.tips || []} query={query} />
              )}
              <div className="rain-count">
                <span>
                  <Droplets size={15} /> Basculadas registradas
                </span>
                <strong>{summary?.rain.tip_count ?? "—"}</strong>
              </div>
              {summary?.rain.accumulated_rainfall.reason && (
                <p className="rain-unavailable">
                  {reasonText(summary.rain.accumulated_rainfall.reason)}
                </p>
              )}
            </article>
          </section>

          <Records data={data} tab={tab} onTab={setTab} />
          <div className="interpretation">
            <span className="info-icon">
              <CircleHelp size={19} />
            </span>
            <p>
              <strong>Observação antes de conclusão.</strong> Chuva e nível são
              grandezas distintas. Este MVP não classifica risco de inundação.
            </p>
            <button onClick={() => dialog.current?.showModal()}>
              Entenda os indicadores <ArrowUpRight size={14} />
            </button>
          </div>
          <footer className="page-footer">
            <span>
              <Waves size={15} /> FloodSystem{" "}
              <span className="status-dot">/</span> Monitoramento com contexto.
            </span>
            <span>
              {data
                ? `Consulta recebida às ${time(data.fetchedAt, true)} · Brasília`
                : "Aguardando dados da API"}
              <span className="footer-version">MVP 0.6</span>
            </span>
          </footer>
        </main>
      </div>
      <dialog ref={dialog} className="method-dialog">
        <div className="dialog-heading">
          <span className="eyebrow">GUIA DE LEITURA</span>
          <button
            className="icon-button"
            aria-label="Fechar guia"
            onClick={() => dialog.current?.close()}
          >
            <X size={19} />
          </button>
        </div>
        <h2>Os dados contam uma parte da história.</h2>
        <p>
          Os cálculos são feitos pelo backend a partir dos registros
          armazenados. Os horários aparecem em Brasília (UTC−3); a API e o banco
          mantêm os instantes em UTC.
        </p>
        <dl>
          <dt>Tempo real e Histórico</dt>
          <dd>
            Tempo real verifica novas basculadas e leituras de nível a cada 2 segundos e atualiza o painel quando a API as recebe. A consulta completa também se repete a cada 15 segundos.
            Histórico consulta o dia escolhido, das 00:00 às 00:00 do dia seguinte,
            ou um cenário antigo. Não há cópia diária do banco.
          </dd>
          <dt>Nível · cm</dt>
          <dd>
            H₀ menos a distância do sensor. No dispositivo físico, H₀ é a leitura
            com a água residual depois que a mangueira inferior para de drenar;
            o indicador mostra a subida acima dela. O cartão apresenta a última
            leitura do intervalo e informa quando ela foi medida. No Tempo real,
            informa também quando a leitura chegou à API.
          </dd>
          <dt>Intensidade · mm/h</dt>
          <dd>
            No Tempo real, a janela de chuva é independente do intervalo dos
            gráficos: por exemplo, gráfico de 30 minutos e intensidade dos
            últimos 5 minutos. O Histórico mostra a chuva acumulada no período.
          </dd>
          <dt>Velocidade · cm/min</dt>
          <dd>
            Variação entre o primeiro e o último nível, dividida pelo tempo real
            entre essas medições. No Tempo real, considera os últimos 5 minutos,
            independente do gráfico; no Histórico, o período selecionado. É uma média,
            não um valor instantâneo.
          </dd>
          <dt>Sem dados não significa zero</dt>
          <dd>
            Sem calibração, medições suficientes ou cobertura conhecida, o
            cálculo pode ficar indisponível. A API informa o motivo.
          </dd>
          <dt>Simulação identificada</dt>
          <dd>
            Registros com origem “Simulação” são sintéticos. Os atalhos de
            cenários apenas consultam dados já enviados; não geram novas
            medições.
          </dd>
        </dl>
        <button
          className="button primary"
          onClick={() => dialog.current?.close()}
        >
          Entendi <ArrowRight size={15} />
        </button>
      </dialog>
    </div>
  );
}
