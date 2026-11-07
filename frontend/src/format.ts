export const BRASILIA_TIME_ZONE = "America/Sao_Paulo";

export const number = (value: number | null | undefined, digits = 1) =>
  value == null
    ? "—"
    : new Intl.NumberFormat("pt-BR", {
        maximumFractionDigits: digits,
        minimumFractionDigits: digits,
      }).format(value);
export const time = (value: string | Date, seconds = false) =>
  new Intl.DateTimeFormat("pt-BR", {
    timeZone: BRASILIA_TIME_ZONE,
    hour: "2-digit",
    minute: "2-digit",
    ...(seconds ? { second: "2-digit" } : {}),
  }).format(new Date(value));
export const date = (value: string | Date) =>
  new Intl.DateTimeFormat("pt-BR", {
    timeZone: BRASILIA_TIME_ZONE,
    day: "2-digit",
    month: "short",
    year: "numeric",
  }).format(new Date(value));
export const fullDate = (value: string) =>
  `${date(value)}, ${time(value, true)} (horário de Brasília)`;

export const brasiliaToUtc = (value: string) => {
  const instant = new Date(`${value}-03:00`);
  if (Number.isNaN(instant.getTime())) throw new Error("Horário inválido");
  return instant.toISOString();
};
const reasons: Record<string, string> = {
  no_rain_events:
    "Sem basculadas. Ausência de registros não confirma chuva zero.",
  missing_k: "A calibração de chuva (K) está incompleta.",
  missing_h0: "A referência de nível (H₀) não está calibrada.",
  insufficient_level_readings: "São necessárias ao menos duas leituras.",
  h0_changed: "A referência H₀ mudou durante o período.",
  ambiguous_endpoint: "Há leituras conflitantes no mesmo instante.",
  nonpositive_elapsed_time: "As medições precisam ter horários diferentes.",
  period_shorter_than_window:
    "A janela de chuva é maior que o período consultado.",
  numeric_overflow: "O cálculo excede o intervalo numérico permitido.",
};
export const reasonText = (reason?: string | null) =>
  reason
    ? reasons[reason] || "Cálculo indisponível."
    : "Sem leitura no período.";
