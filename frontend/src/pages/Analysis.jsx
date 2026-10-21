import { useCallback, useEffect, useState } from "react";
import { api } from "../services/api.js";
import { Button, Card, ErrorBox, Loading, PageHeader, TextInput } from "../components/ui.jsx";
import MeasuredVsTheoryChart from "../components/charts/MeasuredVsTheoryChart.jsx";
import { ChartWithTable, SERIES } from "../components/charts/chartKit.jsx";
import {
  PRESETS, acceptanceRows, latestByName, mergeRows, presetRequest, qberRows, siftedRows,
} from "../lib/experiments.js";
import { compact, dateTime, num, pct } from "../lib/format.js";

const CHARTS = [
  { id: "eve", title: "Eve intercept probability vs QBER", presets: ["eve_vs_qber"] },
  { id: "noise", title: "Channel noise vs QBER", presets: ["noise_depolarizing", "noise_bit_phase_flip"] },
  { id: "qubits", title: "Qubits sent vs sifted-key length", presets: ["qubits_vs_sifted"] },
  { id: "acceptance", title: "Key acceptance rate under attack and noise", presets: ["acceptance_eve", "acceptance_noise"] },
];

export default function Analysis() {
  const [seed, setSeed] = useState("2024");
  const [results, setResults] = useState({});   // preset id -> stored experiment (with points)
  const [busy, setBusy] = useState({});         // chart id -> bool
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);

  // Load the most recent stored run of each preset.
  useEffect(() => {
    (async () => {
      try {
        const list = await api.experiments({ limit: 200 });
        const latest = latestByName(list.items);
        const entries = await Promise.all(
          Object.entries(PRESETS)
            .filter(([, p]) => latest[p.name])
            .map(async ([id, p]) => [id, await api.experiment(latest[p.name].id)]),
        );
        setResults(Object.fromEntries(entries));
      } catch (e) {
        setError(e);
      } finally {
        setLoading(false);
      }
    })();
  }, []);

  const runChart = useCallback(async (chart) => {
    setBusy((b) => ({ ...b, [chart.id]: true }));
    setError(null);
    try {
      const done = await Promise.all(
        chart.presets.map(async (id) => [id, await api.runExperiment(presetRequest(PRESETS[id], Number(seed) || 0))]),
      );
      setResults((r) => ({ ...r, ...Object.fromEntries(done) }));
    } catch (e) {
      setError(e);
    } finally {
      setBusy((b) => ({ ...b, [chart.id]: false }));
    }
  }, [seed]);

  const runAll = async () => {
    for (const c of CHARTS) await runChart(c); // sequential: keeps the server responsive
  };
  const anyBusy = Object.values(busy).some(Boolean);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Experimental Analysis"
        subtitle="Every point below is measured by running the simulator — mean ± 1 standard deviation over repeated trials, with independent seeded streams. Dashed lines are closed-form theory. Nothing is hand-entered."
        actions={
          <div className="flex items-end gap-2">
            <div className="w-28"><TextInput label="Root seed" value={seed} onChange={setSeed} inputMode="numeric" /></div>
            <Button onClick={runAll} disabled={anyBusy}>{anyBusy ? "Running…" : "Run all experiments"}</Button>
          </div>
        }
      />
      <ErrorBox error={error} />
      {loading && <Loading label="Loading stored experiments…" />}
      <div className="grid gap-6 xl:grid-cols-2">
        {CHARTS.map((c) => (
          <ExperimentCard key={c.id} chart={c} results={results} busy={busy[c.id]} onRun={() => runChart(c)} />
        ))}
      </div>
    </div>
  );
}

function Meta({ experiments }) {
  const x = experiments[0];
  if (!x) return null;
  const cfg = x.config;
  return (
    <p className="mt-3 text-xs text-muted">
      {num(cfg.trials)} trials per point · {x.parameter === "n_qubits" ? "256–16,384" : num(cfg.n_qubits)} qubits ·
      seed {cfg.seed} · {cfg.simulation_kind === "circuit_simulation" ? "circuit-simulated" : "mathematically modelled"} ·
      run {dateTime(x.created_at)}
    </p>
  );
}

function ExperimentCard({ chart, results, busy, onRun }) {
  const exps = chart.presets.map((id) => results[id]).filter(Boolean);
  const complete = exps.length === chart.presets.length;
  return (
    <Card title={chart.title}
          actions={<Button variant="secondary" onClick={onRun} disabled={busy}>{busy ? "Running…" : complete ? "Re-run" : "Run"}</Button>}>
      {complete ? <ChartBody id={chart.id} results={results} /> : (
        <p className="py-10 text-center text-sm text-ink-2">{busy ? "Running experiment…" : "No stored run yet — press Run."}</p>
      )}
      {complete && <Meta experiments={exps} />}
    </Card>
  );
}

function ChartBody({ id, results }) {
  if (id === "eve") {
    const rows = qberRows(results.eve_vs_qber.points);
    return (
      <ChartWithTable caption="QBER versus Eve intercept probability" rows={rows}
        columns={[{ key: "x", label: "Eve probability", format: (v) => pct(v, 0) },
                  { key: "m", label: "Mean QBER", format: (v) => pct(v, 2) },
                  { key: "m_err", label: "± sd", format: (v) => pct(v, 2) },
                  { key: "m_theory", label: "Theory p/4", format: (v) => pct(v, 2) }]}
        chart={<MeasuredVsTheoryChart rows={rows} xLabel="Eve intercept probability" yLabel="Sifted-key QBER"
                 xFormat={(v) => pct(v, 0)} yFormat={(v) => pct(v, 0)}
                 yDomain={[0, 0.3]} yTicks={[0, 0.05, 0.1, 0.15, 0.2, 0.25, 0.3]}
                 series={[{ key: "m", errKey: "m_err", theoryKey: "m_theory", name: "Intercept-resend", color: SERIES[0] }]}
                 reference={{ value: 0.11, label: "11% threshold" }} />} />
    );
  }
  if (id === "noise") {
    const rows = mergeRows(qberRows(results.noise_depolarizing.points, "dep"),
                           qberRows(results.noise_bit_phase_flip.points, "bpf"));
    return (
      <ChartWithTable caption="QBER versus channel noise" rows={rows}
        columns={[{ key: "x", label: "Noise p", format: (v) => pct(v, 0) },
                  { key: "dep", label: "Depolarizing", format: (v) => pct(v, 2) },
                  { key: "dep_theory", label: "Theory p/2", format: (v) => pct(v, 2) },
                  { key: "bpf", label: "Bit-phase flip", format: (v) => pct(v, 2) },
                  { key: "bpf_theory", label: "Theory q", format: (v) => pct(v, 2) }]}
        chart={<MeasuredVsTheoryChart rows={rows} xLabel="Noise probability per qubit" yLabel="Sifted-key QBER"
                 xFormat={(v) => pct(v, 0)} yFormat={(v) => pct(v, 0)}
                 yDomain={[0, 0.6]} yTicks={[0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6]}
                 series={[{ key: "dep", errKey: "dep_err", theoryKey: "dep_theory", name: "Depolarizing", color: SERIES[0] },
                          { key: "bpf", errKey: "bpf_err", theoryKey: "bpf_theory", name: "Bit-phase flip", color: SERIES[1] }]}
                 reference={{ value: 0.11, label: "11% threshold" }} />} />
    );
  }
  if (id === "qubits") {
    const rows = siftedRows(results.qubits_vs_sifted.points);
    return (
      <ChartWithTable caption="Sifted-key length versus qubits sent" rows={rows}
        columns={[{ key: "x", label: "Qubits", format: num },
                  { key: "m", label: "Mean sifted length", format: (v) => num(Math.round(v)) },
                  { key: "m_err", label: "± sd", format: (v) => v.toFixed(1) },
                  { key: "m_theory", label: "Theory n/2", format: num }]}
        chart={<MeasuredVsTheoryChart rows={rows} xLabel="Qubits sent (log scale)" yLabel="Sifted-key length (bits, log)"
                 xScale="log" yScale="log" yDomain={[64, 16384]} yTicks={[64, 256, 1024, 4096, 16384]}
                 xFormat={compact} yFormat={compact}
                 series={[{ key: "m", errKey: "m_err", theoryKey: "m_theory", name: "Sifted length", color: SERIES[0] }]} />} />
    );
  }
  const rows = mergeRows(acceptanceRows(results.acceptance_eve.points, "eve"),
                         acceptanceRows(results.acceptance_noise.points, "noise"));
  return (
    <ChartWithTable caption="Key acceptance rate under attack and noise" rows={rows}
      columns={[{ key: "x", label: "Probability", format: (v) => pct(v, 0) },
                { key: "eve", label: "Accepted (Eve)", format: (v) => (v === undefined ? "—" : pct(v, 0)) },
                { key: "noise", label: "Accepted (depolarizing)", format: (v) => (v === undefined ? "—" : pct(v, 0)) }]}
      chart={<>
        <MeasuredVsTheoryChart rows={rows} xLabel="Eve intercept probability / depolarizing noise p"
          yLabel="Sessions accepted" xFormat={(v) => pct(v, 0)} yFormat={(v) => pct(v, 0)}
          yDomain={[0, 1]} yTicks={[0, 0.25, 0.5, 0.75, 1]} xTicks={[0, 0.1, 0.2, 0.3, 0.4, 0.5]}
          series={[{ key: "eve", name: "Eve intercept-resend", color: SERIES[0] },
                   { key: "noise", name: "Depolarizing noise", color: SERIES[1] }]} />
        <p className="mt-2 text-xs text-ink-2">
          Keys stop surviving below the 11% QBER threshold: Cascade leakage and finite-sample bounds make privacy amplification the binding constraint.
        </p>
      </>} />
  );
}
