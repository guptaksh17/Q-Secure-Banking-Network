import { useCallback, useState } from "react";
import { api } from "../services/api.js";
import { useAction } from "../hooks/useApi.js";
import { Button, Card, ErrorBox, PageHeader, Select, StatusBadge, TextArea, TextInput } from "../components/ui.jsx";
import HorizontalBarChart from "../components/charts/HorizontalBarChart.jsx";
import { ChartWithTable } from "../components/charts/chartKit.jsx";
import { humanize, pct } from "../lib/format.js";

const SCENARIOS = [
  { name: "Clean channel", eve_probability: 0, channel_noise: 0 },
  { name: "Noise 10% (depolarizing)", eve_probability: 0, channel_noise: 0.1 },
  { name: "Eve on 25% of qubits", eve_probability: 0.25, channel_noise: 0 },
  { name: "Eve on 50% of qubits", eve_probability: 0.5, channel_noise: 0 },
  { name: "Full intercept-resend", eve_probability: 1, channel_noise: 0 },
  { name: "Noise 30% (no Eve)", eve_probability: 0, channel_noise: 0.3 },
];

export default function SecuritySimulator() {
  return (
    <div className="space-y-6">
      <PageHeader
        title="Security Simulator"
        subtitle="Two layers of defence: QBER-based detection of disturbance on the quantum channel, and AES-256-GCM authentication on the classical channel."
      />
      <EavesdropperComparison />
      <TamperLab />
    </div>
  );
}

function EavesdropperComparison() {
  const [seed, setSeed] = useState("7");
  const action = useAction(useCallback(async (seedValue) => {
    const runs = await Promise.all(
      SCENARIOS.map((s) => api.keyExchange({
        n_qubits: 8192, seed: Number(seedValue) || 0, trace_length: 0,
        eve_probability: s.eve_probability, channel_noise: s.channel_noise,
      })),
    );
    return runs.map((r, i) => ({ ...SCENARIOS[i], metrics: r.metrics, expected: r.channel.expected_qber }));
  }, []));
  const results = action.data;
  const threshold = results?.[0]?.metrics.qber_threshold ?? 0.11;

  return (
    <Card
      title="Layer 1 — Detecting disturbance on the quantum channel"
      subtitle="Six BB84 sessions (8,192 qubits each). Sessions whose estimated QBER exceeds the illustrative threshold abort; others may still abort if privacy amplification leaves too little key."
      actions={
        <div className="flex items-end gap-2">
          <div className="w-28"><TextInput label="Seed" value={seed} onChange={setSeed} inputMode="numeric" /></div>
          <Button onClick={() => action.run(seed)} disabled={action.running}>
            {action.running ? "Running…" : "Run scenarios"}
          </Button>
        </div>
      }
    >
      <ErrorBox error={action.error} />
      {!results && !action.running && <p className="text-sm text-ink-2">Run the scenarios to compare estimated QBER with the abort threshold.</p>}
      {results && (
        <div className="space-y-4">
          <ChartWithTable
            caption="Estimated QBER per scenario"
            chart={
              <HorizontalBarChart
                rows={results.map((r) => ({ label: r.name, value: r.metrics.estimated_qber }))}
                valueFormat={(v) => pct(v, 1)}
                reference={{ value: threshold, label: `threshold ${pct(threshold, 0)}` }}
              />
            }
            columns={[
              { key: "name", label: "Scenario" },
              { key: "est", label: "Estimated QBER", format: (v) => pct(v, 2) },
              { key: "expected", label: "Theory", format: (v) => pct(v, 2) },
            ]}
            rows={results.map((r) => ({ name: r.name, est: r.metrics.estimated_qber, expected: r.expected }))}
          />
          <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {results.map((r) => (
              <div key={r.name} className="flex items-center justify-between gap-2 rounded-lg border border-line px-3 py-2 text-sm">
                <span>{r.name}</span>
                <StatusBadge status={r.metrics.accepted ? "accepted" : "aborted"}
                             label={r.metrics.accepted ? `${r.metrics.final_key_length}-bit key` : humanize(r.metrics.abort_reason)} />
              </div>
            ))}
          </div>
          <p className="text-xs text-ink-2">
            Note the last scenario: noise alone can push QBER over the threshold. High QBER signals disturbance; it does not prove an eavesdropper.
          </p>
        </div>
      )}
    </Card>
  );
}

const TAMPER_OPTIONS = [
  { value: "none", label: "No attack" },
  { value: "ciphertext", label: "Flip a ciphertext bit" },
  { value: "tag", label: "Flip an authentication-tag bit" },
  { value: "nonce", label: "Flip a nonce bit" },
  { value: "aad", label: "Alter the associated metadata" },
  { value: "wrong_key", label: "Receiver uses the wrong key" },
  { value: "replay", label: "Replay the same message twice" },
];

function TamperLab() {
  const [plaintext, setPlaintext] = useState('{"from":"QSB-A-1001","to":"QSB-B-2001","amount":"1000.00","currency":"USD"}');
  const [aad, setAad] = useState("txn=DEMO-1|from=bank_a|to=bank_b");
  const [tamper, setTamper] = useState("ciphertext");
  const action = useAction(useCallback((body) => api.cryptoDemo(body), []));
  const r = action.data;

  return (
    <Card title="Layer 2 — Authenticated encryption on the classical channel"
          subtitle="Bank A encrypts with a fresh QKD-derived AES-256-GCM key; an attacker modifies the message in transit; Bank B verifies the tag.">
      <div className="grid gap-4 lg:grid-cols-2">
        <TextArea label="Fictional message (plaintext)" value={plaintext} onChange={setPlaintext} rows={3} maxLength={4096} />
        <div className="space-y-4">
          <TextInput label="Associated data (authenticated, not encrypted)" value={aad} onChange={setAad} maxLength={512} />
          <Select label="Attack in transit" value={tamper} onChange={setTamper} options={TAMPER_OPTIONS} />
        </div>
      </div>
      <div className="mt-4">
        <Button disabled={action.running || !plaintext}
                onClick={() => action.run({ plaintext, associated_data: aad, tamper })}>
          {action.running ? "Running…" : "Send message"}
        </Button>
      </div>
      <div className="mt-4"><ErrorBox error={action.error} /></div>
      {r && <TamperResult r={r} />}
    </Card>
  );
}

function TamperResult({ r }) {
  if (r.status === "blocked") {
    return (
      <div className="mt-4 flex items-center gap-3">
        <StatusBadge status="blocked" />
        <span className="text-sm text-ink-2">{r.detail}</span>
      </div>
    );
  }
  const fields = ["nonce", "ciphertext", "tag", "aad"];
  return (
    <div className="mt-5 space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <StatusBadge status={r.status} label={r.status === "verified" ? "Tag verified — message accepted" : "Rejected"} />
        {r.decryption.error_type && <span className="text-sm text-ink-2">{r.decryption.error_type}: {r.decryption.detail}</span>}
        {r.decryption.first_delivery && <span className="text-sm text-ink-2">(first delivery was {r.decryption.first_delivery}; the replay was refused)</span>}
      </div>
      <div className="overflow-x-auto rounded-lg border border-line">
        <table className="w-full text-left text-xs">
          <thead className="bg-surface-2 text-ink-2">
            <tr><th className="px-3 py-2 font-medium">Field</th><th className="px-3 py-2 font-medium">Sent by Bank A</th><th className="px-3 py-2 font-medium">Delivered to Bank B</th></tr>
          </thead>
          <tbody className="font-mono">
            {fields.map((f) => {
              const changed = r.sent[f] !== r.delivered[f];
              return (
                <tr key={f} className={`border-t border-line ${changed ? "bg-critical-soft" : ""}`}>
                  <td className="whitespace-nowrap px-3 py-1.5 font-sans">
                    {f}{changed && <span className="ml-1 font-bold text-critical-ink" title="modified in transit"> ✕ modified</span>}
                  </td>
                  <td className="break-all px-3 py-1.5">{r.sent[f]}</td>
                  <td className="break-all px-3 py-1.5">{r.delivered[f]}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {r.decryption.plaintext && (
        <div className="text-sm"><span className="text-ink-2">Decrypted by Bank B: </span><code className="font-mono">{r.decryption.plaintext}</code></div>
      )}
      <p className="text-xs text-muted">Session key id {r.key_id} · {r.algorithm}</p>
    </div>
  );
}
