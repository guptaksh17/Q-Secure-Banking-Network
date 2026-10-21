// Shared chart chrome: recessive hairline grid/axes, text in ink tokens, data in series tokens.
import { useState } from "react";

export const SERIES = ["var(--series-1)", "var(--series-2)", "var(--series-3)"];

export const axisProps = {
  stroke: "var(--axis)",
  tick: { fill: "var(--muted)", fontSize: 12 },
  tickLine: false,
};

export const gridProps = { stroke: "var(--line)", strokeDasharray: "0", vertical: false };

export function ChartTooltip({ active, payload, label, labelFormatter, valueFormatter }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="rounded-lg border border-line bg-surface px-3 py-2 text-xs shadow-md">
      <div className="mb-1 font-medium text-ink">{labelFormatter ? labelFormatter(label) : label}</div>
      {payload
        .filter((p) => p.value !== null && p.value !== undefined)
        .map((p) => (
          <div key={p.dataKey} className="flex items-center gap-2 text-ink-2">
            <span className="inline-block h-2 w-2 rounded-full" style={{ background: p.color }} aria-hidden="true" />
            <span>{p.name}</span>
            <span className="tabular ml-auto pl-3 font-medium text-ink">
              {valueFormatter ? valueFormatter(p.value, p) : p.value}
            </span>
          </div>
        ))}
    </div>
  );
}

/** Legend rendered as HTML (text in ink tokens; color only on the key mark). */
export function Legend({ items }) {
  return (
    <ul className="mb-2 flex flex-wrap gap-x-5 gap-y-1 text-xs text-ink-2">
      {items.map((it) => (
        <li key={it.name} className="flex items-center gap-2">
          {it.swatch ? (
            <svg width="10" height="10" aria-hidden="true"><rect width="10" height="10" rx="2" fill={it.color} /></svg>
          ) : (
            <svg width="22" height="10" aria-hidden="true">
              <line x1="1" x2="21" y1="5" y2="5" stroke={it.color} strokeWidth="2"
                    strokeDasharray={it.dashed ? "4 3" : undefined} strokeLinecap="round" />
              {!it.dashed && !it.noMarker && <circle cx="11" cy="5" r="3.5" fill={it.color} />}
            </svg>
          )}
          {it.name}
        </li>
      ))}
    </ul>
  );
}

/** Chart with a toggle to an equivalent data table (accessibility + contrast relief). */
export function ChartWithTable({ chart, columns, rows, caption }) {
  const [showTable, setShowTable] = useState(false);
  return (
    <div>
      <div className="mb-2 flex justify-end">
        <button type="button" onClick={() => setShowTable((v) => !v)}
                className="text-xs font-medium text-accent hover:underline" aria-pressed={showTable}>
          {showTable ? "Show chart" : "Show data table"}
        </button>
      </div>
      {showTable ? (
        <div className="max-h-80 overflow-auto rounded-lg border border-line">
          <table className="w-full text-left text-xs">
            <caption className="sr-only">{caption}</caption>
            <thead className="sticky top-0 bg-surface-2">
              <tr>{columns.map((c) => <th key={c.key} className="px-3 py-2 font-medium">{c.label}</th>)}</tr>
            </thead>
            <tbody className="tabular">
              {rows.map((r, i) => (
                <tr key={i} className="border-t border-line">
                  {columns.map((c) => (
                    <td key={c.key} className="px-3 py-1.5">{c.format ? c.format(r[c.key], r) : r[c.key]}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        chart
      )}
    </div>
  );
}
