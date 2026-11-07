interface WaterTankProps {
  levelCm: number | null;
  stale: boolean;
  residualReference: boolean;
}

export function WaterTank({ levelCm, stale, residualReference }: WaterTankProps) {
  const maxLevelCm = residualReference ? 19 : 20;
  const available = levelCm !== null && Number.isFinite(levelCm);
  const fillPercent = available
    ? Math.max(0, Math.min(100, (levelCm / maxLevelCm) * 100))
    : 0;

  return (
    <div className={`water-tank-visual${stale ? " is-stale" : ""}`} aria-hidden="true">
      <div className="water-tank-scale">
        <span>{maxLevelCm}</span>
        <span>0</span>
      </div>
      <div className={`water-tank-window${available ? "" : " is-empty"}`}>
        <div className="water-tank-fill" style={{ height: `${fillPercent}%`, opacity: fillPercent > 0 ? 1 : 0 }}>
          <svg className="water-tank-wave" viewBox="0 0 240 20" preserveAspectRatio="none" focusable="false">
            <path d="M0 10 Q15 2 30 10 T60 10 T90 10 T120 10 T150 10 T180 10 T210 10 T240 10 L240 20 H0 Z" />
          </svg>
        </div>
        {!available && <span className="water-tank-empty">Sem leitura</span>}
      </div>
      <span className="water-tank-caption">
        {residualReference ? "acima da água residual · cm" : "escala provisória · cm"}
      </span>
    </div>
  );
}
