import { useId, useState } from "react";
import { statusMeta } from "../lib/format.js";

export function PageHeader({ title, subtitle, actions }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-3">
      <div>
        <h2 className="text-2xl font-semibold tracking-tight">{title}</h2>
        {subtitle && <p className="mt-1 max-w-3xl text-sm text-ink-2">{subtitle}</p>}
      </div>
      {actions}
    </div>
  );
}

export function Card({ title, subtitle, actions, children, className = "" }) {
  return (
    <section className={`rounded-xl border border-line bg-surface p-5 ${className}`}>
      {(title || actions) && (
        <div className="mb-4 flex flex-wrap items-start justify-between gap-2">
          <div>
            {title && <h3 className="text-base font-semibold">{title}</h3>}
            {subtitle && <p className="mt-0.5 text-sm text-ink-2">{subtitle}</p>}
          </div>
          {actions}
        </div>
      )}
      {children}
    </section>
  );
}

export function Stat({ label, value, hint }) {
  return (
    <div className="rounded-xl border border-line bg-surface p-4">
      <div className="text-sm text-ink-2">{label}</div>
      <div className="mt-1 text-2xl font-semibold">{value}</div>
      {hint && <div className="mt-1 text-xs text-muted">{hint}</div>}
    </div>
  );
}

const TONE = {
  good: "bg-good-soft text-ink border-good",
  warning: "bg-warning-soft text-ink border-warning",
  critical: "bg-critical-soft text-ink border-critical",
  neutral: "bg-surface-2 text-ink border-line",
};
const ICON_TONE = {
  good: "text-good-ink",
  warning: "text-ink",
  critical: "text-critical-ink",
  neutral: "text-ink-2",
};

/** Status chip: colored border + icon + text label (never color alone). */
export function StatusBadge({ status, label }) {
  const meta = statusMeta(status);
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs font-medium ${TONE[meta.tone]}`}
    >
      <span aria-hidden="true" className={`font-bold ${ICON_TONE[meta.tone]}`}>
        {meta.icon}
      </span>
      {label ?? meta.label}
    </span>
  );
}

export function Button({ children, variant = "primary", className = "", ...props }) {
  const styles = {
    primary: "bg-button text-white hover:bg-button-hover disabled:opacity-50",
    secondary: "border border-line bg-surface text-ink hover:bg-surface-2 disabled:opacity-50",
  };
  return (
    <button
      type="button"
      className={`inline-flex items-center justify-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors disabled:cursor-not-allowed ${styles[variant]} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}

export function Field({ label, hint, children }) {
  const id = useId();
  return (
    <div className="space-y-1">
      <label htmlFor={id} className="block text-sm font-medium">
        {label}
      </label>
      {typeof children === "function" ? children(id) : children}
      {hint && <p className="text-xs text-muted">{hint}</p>}
    </div>
  );
}

const inputClass =
  "w-full rounded-lg border border-line bg-surface px-3 py-2 text-sm text-ink focus:border-accent focus:outline-none focus:ring-2 focus:ring-accent-soft";

export function TextInput({ label, hint, value, onChange, ...props }) {
  return (
    <Field label={label} hint={hint}>
      {(id) => (
        <input id={id} className={inputClass} value={value}
               onChange={(e) => onChange(e.target.value)} {...props} />
      )}
    </Field>
  );
}

export function TextArea({ label, hint, value, onChange, ...props }) {
  return (
    <Field label={label} hint={hint}>
      {(id) => (
        <textarea id={id} className={`${inputClass} font-mono`} value={value}
                  onChange={(e) => onChange(e.target.value)} {...props} />
      )}
    </Field>
  );
}

export function Select({ label, hint, value, onChange, options }) {
  return (
    <Field label={label} hint={hint}>
      {(id) => (
        <select id={id} className={inputClass} value={value} onChange={(e) => onChange(e.target.value)}>
          {options.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      )}
    </Field>
  );
}

export function Slider({ label, hint, value, onChange, min = 0, max = 1, step = 0.01, format }) {
  return (
    <Field label={`${label}: ${format ? format(value) : value}`} hint={hint}>
      {(id) => (
        <input id={id} type="range" className="w-full" min={min} max={max} step={step}
               value={value} onChange={(e) => onChange(Number(e.target.value))} />
      )}
    </Field>
  );
}

export function ErrorBox({ error }) {
  if (!error) return null;
  return (
    <div role="alert" className="flex gap-2 rounded-lg border border-critical bg-critical-soft p-3 text-sm">
      <span aria-hidden="true" className="font-bold text-critical-ink">✕</span>
      <span>{error.message ?? String(error)}</span>
    </div>
  );
}

export function Loading({ label = "Loading…" }) {
  return (
    <div className="flex items-center gap-2 text-sm text-ink-2" role="status">
      <span className="inline-block h-3 w-3 animate-spin rounded-full border-2 border-line border-t-accent" />
      {label}
    </div>
  );
}

export function Empty({ children }) {
  return <p className="rounded-lg border border-dashed border-line p-6 text-center text-sm text-ink-2">{children}</p>;
}

/** Two-column definition list for metric/value pairs. */
export function KeyValues({ rows }) {
  return (
    <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-1.5 text-sm">
      {rows.filter(Boolean).map(([k, v]) => (
        <div key={k} className="contents">
          <dt className="text-ink-2">{k}</dt>
          <dd className="tabular text-right font-medium">{v}</dd>
        </div>
      ))}
    </dl>
  );
}

export function Tabs({ tabs, initial, children }) {
  const [active, setActive] = useState(initial ?? tabs[0].id);
  return (
    <div>
      <div role="tablist" className="mb-4 flex gap-1 border-b border-line">
        {tabs.map((t) => (
          <button
            key={t.id}
            role="tab"
            type="button"
            aria-selected={active === t.id}
            onClick={() => setActive(t.id)}
            className={`-mb-px border-b-2 px-4 py-2 text-sm font-medium ${
              active === t.id ? "border-accent text-ink" : "border-transparent text-ink-2 hover:text-ink"
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>
      {children(active)}
    </div>
  );
}

export function Mono({ children }) {
  return <code className="break-all rounded bg-surface-2 px-1.5 py-0.5 font-mono text-xs">{children}</code>;
}
