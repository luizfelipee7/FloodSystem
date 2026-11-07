import { useEffect, useState } from "react";
import { Beaker, Download, Droplets, Moon, RefreshCw, Sun, Waves } from "lucide-react";
import { downloadExperiment, listExperiments, loadExperiment } from "../services/api";
import type { Experiment, ExperimentHour, ExperimentItem } from "../types";
import { date, fullDate, number } from "../format";
import "../experiments.css";

const hourLabel = (value: string) => new Intl.DateTimeFormat("pt-BR", {
  timeZone: "America/Sao_Paulo", day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit",
}).format(new Date(value));

function RainComparison({ hours, complete }: { hours: ExperimentHour[]; complete: boolean }) {
  const [selectedIndex, setSelectedIndex] = useState(() => Math.max(0, hours.findIndex((hour) => Number(hour.rain_mm) > 0)));
  const selectedHour = hours[selectedIndex];
  const max = Math.max(1, ...hours.flatMap((h) => [Number(h.rain_mm), complete ? Number(h.received_rain_mm) : 0]));
  const width = Math.max(760, hours.length * 27 + 80);
  const plotWidth = width - 80;
  const barWidth = Math.max(2, (plotWidth / hours.length - 3) / 2);
  const height = (value: string) => Number(value) / max * 160;
  return <><div className="experiment-chart-scroll">
    <svg viewBox={`0 0 ${width} 225`} style={{ minWidth: width }} role="img"
      aria-label="Comparação horária da chuva da fonte e da chuva representada pelas basculadas. Valores disponíveis na tabela abaixo.">
      {[0, 1, 2, 3, 4].map((tick) => <g key={tick}>
        <line x1="45" x2={width - 15} y1={185 - tick * 40} y2={185 - tick * 40} className="experiment-grid" />
        <text x="35" y={190 - tick * 40} textAnchor="end">{number(max * tick / 4, 1)}</text>
      </g>)}
      {hours.map((hour, index) => {
        const x = 48 + index * plotWidth / hours.length;
        const label = `${fullDate(hour.start_at)}: fonte ${hour.rain_mm} mm; basculadas ${complete ? hour.received_rain_mm + " mm" : "envio pendente"}`;
        return <g key={hour.interval_index} role="button" tabIndex={0}
          aria-label={label} aria-pressed={selectedIndex === index}
          className="experiment-hour-target"
          onClick={() => setSelectedIndex(index)}
          onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); setSelectedIndex(index); } }}>
          <rect x={x - 2} y="24" width={plotWidth / hours.length} height="164" fill="transparent" />
          <rect x={x} y={185 - height(hour.rain_mm)} width={barWidth} height={height(hour.rain_mm)} rx="2" fill="#377ee8"><title>{label}</title></rect>
          {complete && <rect x={x + barWidth + 1} y={185 - height(hour.received_rain_mm)} width={barWidth} height={height(hour.received_rain_mm)} rx="2" fill="#16a795"><title>{label}</title></rect>}
          {selectedIndex === index && <line x1={x - 2} x2={x + plotWidth / hours.length - 2} y1="190" y2="190" className="experiment-selected-hour" />}
          {index % Math.max(1, Math.ceil(hours.length / 10)) === 0 && <text x={x} y="208" textAnchor="middle">{hourLabel(hour.start_at)}</text>}
        </g>;
      })}
    </svg>
  </div>
    {selectedHour && <div className="experiment-hour-detail" aria-live="polite">
      <strong>{fullDate(selectedHour.start_at)} · Brasília</strong>
      <span>Fonte: {number(Number(selectedHour.rain_mm), 2)} mm</span>
      <span>Basculadas: {selectedHour.received_tip_count} ({complete ? `${number(Number(selectedHour.received_rain_mm), 2)} mm` : "envio em andamento"})</span>
      <span>Residual ao fim: {number(Number(selectedHour.residual_after_mm), 2)} mm</span>
    </div>}
    <p className="experiment-chart-instruction">Selecione uma hora no gráfico para ver os valores. A tabela abaixo apresenta todas as horas.</p>
  </>;
}

export function Experiments() {
  const [items, setItems] = useState<ExperimentItem[]>([]);
  const [selected, setSelected] = useState("");
  const [run, setRun] = useState<Experiment | null>(null);
  const [refresh, setRefresh] = useState(0);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [exportError, setExportError] = useState("");
  const [page, setPage] = useState(0);
  const [dark, setDark] = useState(document.documentElement.dataset.theme === "dark");
  useEffect(() => {
    document.title = "FloodSystem · Ensaios meteorológicos";
    document.documentElement.dataset.theme = dark ? "dark" : "light";
    try { localStorage.setItem("floodsystem-theme", dark ? "dark" : "light"); } catch { /* Theme still applies to this page. */ }
  }, [dark]);
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError("");
    listExperiments(controller.signal).then(async (catalogue) => {
      if (controller.signal.aborted) return;
      setItems(catalogue);
      const id = catalogue.some((item) => item.run_id === selected) ? selected : catalogue[0]?.run_id;
      if (!id) { setRun(null); return; }
      const detail = await loadExperiment(id, controller.signal);
      if (!controller.signal.aborted) { setRun(detail); setPage(0); }
    }).catch((failure: unknown) => {
      if (!controller.signal.aborted) {
        setRun(null);
        setError(failure instanceof Error ? failure.message : "Não foi possível carregar os ensaios.");
      }
    }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
  }, [selected, refresh]);
  const complete = run?.status === "complete";
  const selectedValue = selected || run?.run_id || items[0]?.run_id || "";
  const visible = run?.intervals.slice(page * 24, (page + 1) * 24) ?? [];
  async function exportRun() {
    if (!run) return;
    setExporting(true); setExportError("");
    try { await downloadExperiment(run.run_id); }
    catch (failure) { setExportError(failure instanceof Error ? failure.message : "Falha na exportação."); }
    finally { setExporting(false); }
  }
  return <div className="experiments">
    <header className="experiment-topbar">
      <a href="/" className="experiment-brand"><Waves size={30} /><span>FloodSystem<small>Laboratório de ensaios</small></span></a>
      <nav className="experiment-navigation" aria-label="Navegação principal">
        <a href="/">Tempo real</a>
        <a href="/?view=history">Histórico</a>
        <a href="/ensaios/" aria-current="page">Ensaios meteorológicos</a>
      </nav>
      <div className="experiment-actions"><span className="experiment-badge"><Beaker size={16} /> SIMULAÇÃO</span>
        <button className="button" onClick={() => setDark(!dark)} aria-label={dark ? "Ativar modo claro" : "Ativar modo escuro"}>
          {dark ? <Sun size={18} /> : <Moon size={18} />}{dark ? "Claro" : "Escuro"}
        </button>
      </div>
    </header>
    <main className="experiment-main">
      <section className="experiment-hero">
        <div><span className="experiment-eyebrow">ENSAIOS CIENTÍFICOS · SÃO PAULO</span>
          <h1>Da chuva histórica<br />às basculadas.</h1>
          <p>Uma série meteorológica, um cenário reproduzível e cada milímetro acompanhado até o residual.</p>
        </div>
        <div className="experiment-hero-note"><Droplets size={34} /><strong>60 minutos</strong><span>Resolução da fonte e janela da comparação</span></div>
      </section>
      <section className="experiment-toolbar" aria-label="Selecionar ensaio">
        <label>Ensaio meteorológico
          <select value={selectedValue} disabled={loading || !items.length} onChange={(e) => { setRun(null); setSelected(e.target.value); setExportError(""); }}>
            {!items.length && <option value="">Nenhum ensaio disponível</option>}
            {items.map((item) => <option key={item.run_id} value={item.run_id}>ERA5 · {date(item.start_at)} · {item.run_id.slice(0, 8)}</option>)}
          </select>
        </label>
        <div className="experiment-actions">
          <button className="button" disabled={loading} onClick={() => setRefresh(refresh + 1)}><RefreshCw size={17} />Atualizar</button>
          <button className="button primary" disabled={!complete || exporting || loading} onClick={() => void exportRun()}><Download size={17} />{exporting ? "Exportando…" : "Exportar ensaio completo"}</button>
        </div>
      </section>
      {error && <div className="experiment-message" role="alert">{error} Este painel requer a API exclusiva dos ensaios meteorológicos.</div>}
      {exportError && <div className="experiment-message" role="alert">{exportError}</div>}
      {loading && <p role="status" className="experiment-message">Carregando o ensaio…</p>}
      {!loading && !error && !run && <p className="experiment-message">Nenhum ensaio preparado. Importe uma série meteorológica para iniciar a comparação.</p>}
      {run && !loading && <>
        <div className="experiment-notice"><Beaker size={22} /><div><strong>{complete ? "Ensaio completo · eventos simulados" : "Envio em andamento · resultados parciais"}</strong>
          <p>{run.notice} A distribuição da chuva dentro de cada hora é assumida uniforme.</p></div></div>
        <div className="experiment-period">{fullDate(run.start_at)} até {fullDate(run.end_at)} · Brasília · fim exclusivo</div>
        <section className="experiment-metrics" aria-label="Balanço de chuva">
          <article><span>Chuva da fonte</span><strong>{number(Number(run.source_total_mm), 2)} <small>mm</small></strong><p>Reanálise ERA5 · precipitação líquida</p></article>
          <article><span>Representada pelas basculadas</span><strong>{complete ? number(Number(run.received_rain_mm), 2) : "—"} <small>mm</small></strong><p>{run.received_tip_count} de {run.expected_tip_count} eventos recebidos</p></article>
          <article><span>Residual final do modelo</span><strong>{number(Number(run.final_residual_mm), 2)} <small>mm</small></strong><p>Água acumulada para a próxima virada</p></article>
          <article><span>Resolução adotada</span><strong>{number(Number(run.profile.k_mm_per_tip), 2)} <small>mm</small></strong><p>Por basculada · estimativa inicial do protótipo</p></article>
        </section>
        <p className="experiment-balance">Balanço planejado: residual inicial {number(Number(run.profile.initial_residual_mm), 2)} mm + fonte {number(Number(run.source_total_mm), 2)} mm = basculadas {number(Number(run.expected_rain_mm), 2)} mm + residual final {number(Number(run.final_residual_mm), 2)} mm.</p>
        <section className="experiment-panel">
          <div className="experiment-panel-heading"><div><span className="experiment-eyebrow">COMPARAÇÃO HORÁRIA</span><h2>O volume recebido e o volume contado</h2></div>
            <div className="experiment-legend"><span><i />Fonte · mm</span><span><i />Basculadas · mm</span></div>
          </div>
          <RainComparison key={run.run_id} hours={run.intervals} complete={Boolean(complete)} />
          <p className="experiment-help">A sobra passa de uma hora para a próxima. Por isso, uma hora pode registrar basculadas com água acumulada anteriormente. Janelas de cinco minutos seriam resultados da distribuição simulada.</p>
        </section>
        <section className="experiment-panel">
          <div className="experiment-panel-heading"><div><span className="experiment-eyebrow">RASTREABILIDADE</span><h2>Cada hora, sem perder a sobra</h2></div><span>{run.intervals.length} horas</span></div>
          <div className="experiment-table-scroll"><table><thead><tr><th scope="col">Início · Brasília</th><th scope="col">Fonte<br />mm</th><th scope="col">Basculadas<br />recebidas</th><th scope="col">Representado<br />mm</th><th scope="col">Intensidade das basculadas<br />mm/h · 60 min</th><th scope="col">Residual inicial<br />mm</th><th scope="col">Residual final<br />mm</th></tr></thead>
            <tbody>{visible.map((hour) => <tr key={hour.interval_index}><td>{fullDate(hour.start_at)}</td><td>{number(Number(hour.rain_mm), 2)}</td><td>{hour.received_tip_count}</td><td>{complete ? number(Number(hour.received_rain_mm), 2) : "—"}</td><td>{hour.tip_intensity_mm_h === null ? "—" : number(Number(hour.tip_intensity_mm_h), 2)}</td><td>{number(Number(hour.residual_before_mm), 2)}</td><td>{number(Number(hour.residual_after_mm), 2)}</td></tr>)}</tbody>
          </table></div>
          <div className="experiment-pagination"><span>Página {page + 1} de {Math.max(1, Math.ceil(run.intervals.length / 24))} · a exportação inclui todas as horas</span><div className="experiment-actions"><button className="button" disabled={page === 0} onClick={() => setPage(page - 1)}>Anterior</button><button className="button" disabled={(page + 1) * 24 >= run.intervals.length} onClick={() => setPage(page + 1)}>Próxima</button></div></div>
        </section>
        <section className="experiment-provenance">
          <article className="experiment-panel"><span className="experiment-eyebrow">FONTE PRESERVADA</span><h2>Open-Meteo · ERA5</h2>
            <dl><dt>Coordenadas solicitadas</dt><dd>{run.source.request.parameters.latitude}, {run.source.request.parameters.longitude}</dd><dt>Célula retornada</dt><dd>{run.grid.latitude}, {run.grid.longitude}</dd><dt>Obtido em</dt><dd>{fullDate(run.source.downloaded_at)} · Brasília</dd><dt>Variável</dt><dd>rain · mm · soma da hora anterior</dd><dt>Identificador do ensaio</dt><dd className="experiment-code">{run.run_id}</dd><dt>SHA-256 da resposta</dt><dd className="experiment-code">{run.source.response_sha256}</dd></dl>
            <a href="https://open-meteo.com/en/docs/historical-weather-api" target="_blank" rel="noreferrer">Documentação da fonte ↗</a>
          </article>
          <article className="experiment-panel"><span className="experiment-eyebrow">COMO INTERPRETAR</span><h2>Hipóteses à vista</h2>
            <ul><li>Distribuição uniforme dentro de cada hora; residual preservado entre horas e dias.</li><li>O zero na tabela pertence a uma simulação completa. Ausência de eventos de um sensor físico continua tendo outra interpretação.</li><li>H₀ = {number(Number(run.profile.h0_cm), 0)} cm está registrado. A simulação do nível será acrescentada após definir entrada e drenagem.</li><li>O pacote exportado contém fonte original, parâmetros, comparação horária e todos os eventos.</li></ul>
            <p className="experiment-help">{run.source.citation}</p>
          </article>
        </section>
      </>}
      <footer className="experiment-footer">FloodSystem · Ensaios computacionais para o artigo científico · Open-Meteo / Copernicus ERA5</footer>
    </main>
  </div>;
}
