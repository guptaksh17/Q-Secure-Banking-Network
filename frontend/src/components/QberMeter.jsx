import { pct } from "../lib/format.js";

/** Meter: estimated QBER against the abort threshold, scaled to 0–30%. */
export default function QberMeter({ qber, upper, threshold }) {
  const max = 0.3;
  const pos = (v) => `${Math.min(100, (v / max) * 100)}%`;
  const over = qber > threshold;
  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between text-sm">
        <span className="text-ink-2">Estimated QBER</span>
        <span className="tabular text-2xl font-semibold">{pct(qber, 2)}</span>
      </div>
      <div className="relative h-3 rounded-full bg-accent-soft" role="img"
           aria-label={`QBER ${pct(qber, 2)} versus threshold ${pct(threshold, 0)}`}>
        <div className="absolute inset-y-0 left-0 rounded-full"
             style={{ width: pos(qber), background: over ? "var(--critical)" : "var(--series-1)" }} />
        {upper !== undefined && (
          <div className="absolute -top-1 h-5 w-0.5 bg-ink-2" style={{ left: pos(upper) }} title="Upper confidence bound" />
        )}
        <div className="absolute -top-1.5 h-6 w-0.5 bg-critical" style={{ left: pos(threshold) }} />
      </div>
      <div className="mt-1.5 flex justify-between text-xs text-muted">
        <span>0%</span>
        <span>
          threshold {pct(threshold, 0)}
          {upper !== undefined && <> · upper bound {pct(upper, 1)}</>}
        </span>
        <span>30%</span>
      </div>
    </div>
  );
}
