import type {
  DashboardData,
  LevelReading,
  Page,
  Query,
  RainTip,
  Summary,
  Experiment,
  ExperimentItem,
} from "../types";

const BASE_URL = (import.meta.env.VITE_API_BASE_URL || "").replace(/\/$/, "");
const EXPERIMENTS_PATH = "/article-api/v1/experiments";
const PAGE_SIZE = 1000;
const MAX_ITEMS = 10000;

export class ApiError extends Error {
  constructor(
    message: string,
    public status?: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function get<T>(
  path: string,
  params: Record<string, string>,
  signal: AbortSignal,
  baseUrl = BASE_URL,
): Promise<T> {
  const controller = new AbortController();
  const onAbort = () => controller.abort();
  if (signal.aborted) controller.abort();
  signal.addEventListener("abort", onAbort, { once: true });
  const timeout = window.setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch(
      `${baseUrl}${path}?${new URLSearchParams(params)}`,
      {
        signal: controller.signal,
        cache: "no-store",
        headers: { Accept: "application/json" },
      },
    );
    if (!response.ok) {
      const messages: Record<number, string> = {
        404: "Dispositivo ou rota não encontrado. Confira o identificador e se a API foi atualizada.",
        422: "A API não aceitou o período ou a janela. Confira os filtros.",
        503: "O serviço de dados está temporariamente indisponível.",
      };
      throw new ApiError(
        messages[response.status] ||
          `A API retornou um erro (${response.status}).`,
        response.status,
      );
    }
    if (!response.headers.get("content-type")?.includes("application/json")) {
      throw new ApiError(
        "O endereço configurado não retornou os dados da API. Confira o proxy do frontend.",
      );
    }
    return (await response.json()) as T;
  } catch (error) {
    if (signal.aborted)
      throw new DOMException("Consulta cancelada", "AbortError");
    if (error instanceof ApiError) throw error;
    throw new ApiError(
      controller.signal.aborted
        ? "A API demorou mais de 15 segundos para responder. Tente novamente."
        : "Não foi possível conectar à API. Confira se o backend está em execução.",
    );
  } finally {
    clearTimeout(timeout);
    signal.removeEventListener("abort", onAbort);
  }
}

async function allPages<T>(
  path: string,
  params: Record<string, string>,
  signal: AbortSignal,
) {
  const items: T[] = [];
  for (let offset = 0; offset < MAX_ITEMS; offset += PAGE_SIZE) {
    const page = await get<Page<T>>(
      path,
      { ...params, limit: String(PAGE_SIZE), offset: String(offset) },
      signal,
    );
    items.push(...page.items);
    if (!page.has_more) return { items, truncated: false };
  }
  return { items, truncated: true };
}

export async function loadDashboard(
  query: Query,
  signal: AbortSignal,
  live = false,
): Promise<DashboardData> {
  let effectiveQuery = query;
  if (live) {
    const before = Date.now();
    const serverTime = await get<{ unix_ms: number }>("/api/v1/time", {}, signal);
    const after = Date.now();
    if (!Number.isFinite(serverTime.unix_ms))
      throw new ApiError("A API não retornou um horário válido.");
    const end = serverTime.unix_ms + (after - before) / 2;
    const duration = Date.parse(query.end) - Date.parse(query.start);
    effectiveQuery = {
      ...query,
      start: new Date(end - duration).toISOString(),
      end: new Date(end).toISOString(),
    };
  }
  const period = {
    device_id: effectiveQuery.device_id,
    start: effectiveQuery.start,
    end: effectiveQuery.end,
  };
  const periodMinutes = (Date.parse(effectiveQuery.end) - Date.parse(effectiveQuery.start)) / 60000;
  const summaryWindow = Math.min(effectiveQuery.window_minutes, periodMinutes);
  // The API requires its intensity window to fit inside the summary period.
  // For a 30-minute graph and a 60-minute rain window, fetch intensity separately.
  const extraIntensity = live && effectiveQuery.window_minutes > periodMinutes
    ? get<Summary>(
        "/api/v1/summary",
        {
          device_id: effectiveQuery.device_id,
          start: new Date(Date.parse(effectiveQuery.end) - effectiveQuery.window_minutes * 60000).toISOString(),
          end: effectiveQuery.end,
          window_minutes: String(effectiveQuery.window_minutes),
        },
        signal,
      )
    : Promise.resolve(null);
  const recentLevel = live
    ? get<Summary>(
        "/api/v1/summary",
        {
          device_id: effectiveQuery.device_id,
          start: new Date(Date.parse(effectiveQuery.end) - 5 * 60000).toISOString(),
          end: effectiveQuery.end,
          window_minutes: "5",
        },
        signal,
      )
    : Promise.resolve(null);
  const [summary, intensitySummary, recentSummary, levels, tips] = await Promise.all([
    get<Summary>(
      "/api/v1/summary",
      { ...period, window_minutes: String(summaryWindow) },
      signal,
    ),
    extraIntensity,
    recentLevel,
    allPages<LevelReading>("/api/v1/level-readings", period, signal),
    allPages<RainTip>("/api/v1/rain-tips", period, signal),
  ]);
  return {
    summary: intensitySummary ? { ...summary, intensity: intensitySummary.intensity } : summary,
    recentLevel: recentSummary?.level ?? null,
    levels: levels.items,
    tips: tips.items,
    levelsTruncated: levels.truncated,
    tipsTruncated: tips.truncated,
    fetchedAt: new Date(),
  };
}

export function latestRainTip(deviceId: string, signal: AbortSignal): Promise<RainTip | null> {
  return get<RainTip | null>("/api/v1/rain-tips/latest", { device_id: deviceId }, signal);
}

export function latestLevelReading(deviceId: string, signal: AbortSignal): Promise<LevelReading | null> {
  return get<LevelReading | null>("/api/v1/level-readings/latest", { device_id: deviceId }, signal);
}

export async function listExperiments(signal: AbortSignal): Promise<ExperimentItem[]> {
  const status = await get<{ purpose: string }>(`${EXPERIMENTS_PATH}/status`, {}, signal, "");
  if (status.purpose !== "article-simulations") throw new ApiError("Selecione a API exclusiva dos ensaios.");
  const result = await get<{ items: ExperimentItem[] }>(EXPERIMENTS_PATH, {}, signal, "");
  return result.items;
}

export function loadExperiment(id: string, signal: AbortSignal): Promise<Experiment> {
  return get<Experiment>(`${EXPERIMENTS_PATH}/${encodeURIComponent(id)}`, {}, signal, "");
}

export async function downloadExperiment(id: string): Promise<void> {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 60000);
  try {
    const response = await fetch(`${EXPERIMENTS_PATH}/${encodeURIComponent(id)}/export`, {
      signal: controller.signal, cache: "no-store",
    });
    if (!response.ok) throw new ApiError("Não foi possível exportar. Confira se o envio do ensaio foi concluído.");
    if (!response.headers.get("content-type")?.includes("application/zip"))
      throw new ApiError("A API não retornou o pacote de exportação.");
    const url = URL.createObjectURL(await response.blob());
    const link = document.createElement("a");
    link.href = url;
    link.download = `floodsystem-ensaio-${id}.zip`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  } finally {
    clearTimeout(timeout);
  }
}
