export function pct(value, digits = 1) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return `${(value * 100).toFixed(digits)}%`;
}

export function num(value) {
  if (value === null || value === undefined || Number.isNaN(value)) return "—";
  return Number(value).toLocaleString("en-US");
}

/** Compact axis/stat formatting: 950, 1.2K, 16K, 2.5M. */
export function compact(value) {
  if (value === null || value === undefined) return "—";
  const abs = Math.abs(value);
  if (abs >= 1e6) return `${+(value / 1e6).toFixed(1)}M`;
  if (abs >= 1e3) return `${+(value / 1e3).toFixed(1)}K`;
  return `${+Number(value).toFixed(2)}`;
}

export function dateTime(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString(undefined, {
    year: "numeric", month: "short", day: "2-digit",
    hour: "2-digit", minute: "2-digit", second: "2-digit",
  });
}

export function shortHex(hex, keep = 12) {
  if (!hex) return "—";
  return hex.length <= keep * 2 ? hex : `${hex.slice(0, keep)}…${hex.slice(-keep)}`;
}

export function humanize(code) {
  if (!code) return "";
  return code
    .replace(/_/g, " ")
    .replace(/\b(qber|qkd|aad|aes|gcm)\b/gi, (m) => m.toUpperCase())
    .replace(/^\w/, (c) => c.toUpperCase());
}

export function bankName(code) {
  return { bank_a: "Bank A", bank_b: "Bank B" }[code] ?? humanize(code);
}

// Every status pairs a color role with an icon and a label: never color alone.
export const STATUS_META = {
  delivered: { tone: "good", icon: "✓", label: "Delivered" },
  accepted: { tone: "good", icon: "✓", label: "Accepted" },
  verified: { tone: "good", icon: "✓", label: "Verified" },
  blocked: { tone: "warning", icon: "⏸", label: "Blocked" },
  aborted: { tone: "warning", icon: "⏸", label: "Aborted" },
  rejected: { tone: "critical", icon: "✕", label: "Rejected" },
  encrypted: { tone: "neutral", icon: "🔒", label: "Encrypted" },
  key_exchange: { tone: "neutral", icon: "⋯", label: "Key exchange" },
  created: { tone: "neutral", icon: "•", label: "Created" },
  info: { tone: "neutral", icon: "i", label: "Info" },
  warning: { tone: "warning", icon: "!", label: "Warning" },
  critical: { tone: "critical", icon: "✕", label: "Critical" },
};

export function statusMeta(status) {
  return STATUS_META[status] ?? { tone: "neutral", icon: "•", label: humanize(status) };
}

/** Rows for the "where the bits go" budget chart from a key-exchange metrics object. */
export function keyBudgetRows(metrics) {
  if (!metrics) return [];
  const rows = [
    { stage: "Qubits sent", bits: metrics.n_qubits },
    { stage: "After sifting", bits: metrics.sifted_key_length },
    { stage: "After QBER sample", bits: metrics.remaining_key_length },
  ];
  const pa = metrics.privacy_amplification;
  if (pa) {
    rows.push(
      { stage: "Eve's information bound", bits: -Math.round(pa.eve_information_bits) },
      { stage: "Reconciliation leakage", bits: -pa.reconciliation_leak_bits },
      { stage: "Verification hash", bits: -pa.verification_leak_bits },
      { stage: "Security margin", bits: -Math.round(pa.security_margin_bits) },
    );
  }
  rows.push({ stage: "Final secret key", bits: metrics.final_key_length });
  return rows;
}
