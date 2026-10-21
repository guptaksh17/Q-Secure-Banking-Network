import { useCallback, useState } from "react";
import { api } from "../services/api.js";
import { useAction } from "../hooks/useApi.js";
import { Button, Card, ErrorBox, KeyValues, PageHeader, StatusBadge } from "../components/ui.jsx";
import ChannelControls, { DEFAULT_CHANNEL, channelPayload } from "../components/ChannelControls.jsx";
import QberMeter from "../components/QberMeter.jsx";
import QubitTrace from "../components/QubitTrace.jsx";
import HorizontalBarChart from "../components/charts/HorizontalBarChart.jsx";
import { humanize, keyBudgetRows, num, pct } from "../lib/format.js";

export default function QkdLab() {
  const [channel, setChannel] = useState({ ...DEFAULT_CHANNEL, seed: "1" });
  const action = useAction(useCallback((body) => api.keyExchange(body), []));
  const result = action.data;

  return (
    <div className="space-y-6">
      <PageHeader
        title="QKD Laboratory"
        subtitle="Run one BB84 session end to end: preparation, optional eavesdropping and noise, sifting, QBER sampling, the abort decision, Cascade reconciliation and Toeplitz privacy amplification."
      />
      <Card title="Session parameters">
        <ChannelControls value={channel} onChange={setChannel} />
        <div className="mt-5 flex items-center gap-3">
          <Button onClick={() => action.run({ ...channelPayload(channel), trace_length: 24 })} disabled={action.running}>
            {action.running ? "Running…" : "Run key exchange"}
          </Button>
          <span className="text-xs text-muted">Final key bits are discarded — only metrics are returned and stored.</span>
        </div>
      </Card>
      <ErrorBox error={action.error} />
      {result && <LabResult result={result} />}
    </div>
  );
}

function Step({ n, title, children }) {
  return (
    <div className="rounded-xl border border-line bg-surface p-4">
      <div className="text-xs font-medium uppercase tracking-wide text-muted">Step {n}</div>
      <div className="mb-2 font-semibold">{title}</div>
      <div className="text-sm">{children}</div>
    </div>
  );
}

function LabResult({ result }) {
  const m = result.metrics;
  const rec = m.reconciliation;
  const pa = m.privacy_amplification;
  const budget = keyBudgetRows(m).map((r) => ({
    label: r.stage,
    value: Math.abs(r.bits),
    color: r.bits < 0 ? "var(--series-2)" : "var(--series-1)",
  }));

  return (
    <div className="space-y-6">
      <Card>
        <div className="flex flex-wrap items-center gap-3">
          <StatusBadge status={m.accepted ? "accepted" : "aborted"}
                       label={m.accepted ? "Key accepted" : `Aborted: ${humanize(m.abort_reason)}`} />
          <span className="text-sm text-ink-2">
            {m.accepted
              ? `${num(m.final_key_length)}-bit shared secret established; Alice's and Bob's keys ${m.final_keys_match ? "match" : "DIFFER"}.`
              : "No key was produced; a bank would block any transaction relying on this session."}
          </span>
          <span className="ml-auto text-xs text-muted">
            {m.simulation_kind === "circuit_simulation" ? "Circuit-simulated on Qiskit Aer" : "Mathematically modelled (NumPy Born-rule sampling)"}
            {m.seed !== null && ` · seed ${m.seed}`}
          </span>
        </div>
      </Card>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        <Step n={1} title="Transmission & sifting">
          <KeyValues rows={[
            ["Qubits sent", num(m.n_qubits)],
            ["Eve intercepted", num(m.eve_intercepted)],
            ["Noise-affected qubits", num(m.noise_affected_qubits)],
            ["Basis matches", `${num(m.basis_matches)} (${pct(m.sifting_ratio)})`],
          ]} />
        </Step>
        <Step n={2} title="QBER estimation">
          <KeyValues rows={[
            ["Test sample disclosed", `${num(m.test_sample_size)} bits`],
            ["Errors in sample", num(m.test_sample_errors)],
            ["Upper bound (99.9%)", pct(m.qber_upper_bound, 2)],
            ["True QBER (simulator only)", pct(m.true_sifted_error_rate, 2)],
          ]} />
        </Step>
        <Step n={3} title="Accept / abort decision">
          <QberMeter qber={m.estimated_qber} upper={m.qber_upper_bound} threshold={m.qber_threshold} />
          <p className="mt-2 text-xs text-ink-2">
            Expected QBER for this channel: {pct(result.channel.expected_qber, 1)}. High QBER signals disturbance — from Eve <em>or</em> noise.
          </p>
        </Step>
        <Step n={4} title="Cascade reconciliation">
          {rec ? (
            <KeyValues rows={[
              ["Errors before", num(m.errors_before_reconciliation)],
              ["Errors corrected", num(rec.errors_corrected)],
              ["Parity bits leaked", num(rec.parity_bits_leaked)],
              ["Block sizes", rec.block_sizes.join(" → ")],
              ["Hash verification", rec.verified ? "✓ keys equal" : "✕ mismatch"],
            ]} />
          ) : <p className="text-ink-2">Skipped — session aborted before reconciliation.</p>}
        </Step>
        <Step n={5} title="Privacy amplification">
          {pa ? (
            <KeyValues rows={[
              ["Input bits", num(pa.input_bits)],
              ["Eve information bound", `−${num(Math.round(pa.eve_information_bits))}`],
              ["Leakage (EC + hash)", `−${num(pa.reconciliation_leak_bits + pa.verification_leak_bits)}`],
              ["Security margin", `−${num(Math.round(pa.security_margin_bits))}`],
              ["Toeplitz output", `${num(pa.output_bits)} bits`],
            ]} />
          ) : <p className="text-ink-2">Not reached.</p>}
        </Step>
        <Step n={6} title="Result">
          <KeyValues rows={[
            ["Final key length", `${num(m.final_key_length)} bits`],
            ["Minimum for AES-256", "256 bits"],
            ["Keys match", m.final_keys_match === null ? "—" : m.final_keys_match ? "✓ yes" : "✕ no"],
            ["Stored session id", result.session_id.slice(0, 12) + "…"],
          ]} />
        </Step>
      </div>

      <Card title="Where the bits go" subtitle="From qubits sent to final secret key; orange bars are subtracted during privacy amplification">
        <HorizontalBarChart rows={budget} valueFormat={(v) => num(v)}
                            groups={[{ name: "Bits remaining", color: "var(--series-1)" },
                                     { name: "Bits removed", color: "var(--series-2)" }]} />
      </Card>

      <Card title="First qubits, step by step"
            subtitle="Rows in grey were discarded at sifting (bases differ). Errors among kept bits come from Eve or noise.">
        <QubitTrace rows={result.trace} />
      </Card>
    </div>
  );
}
