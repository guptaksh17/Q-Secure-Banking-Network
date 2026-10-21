import { Select, Slider, TextInput } from "./ui.jsx";
import { pct } from "../lib/format.js";

export const DEFAULT_CHANNEL = {
  n_qubits: 4096,
  seed: "",
  eve_probability: 0,
  channel_noise: 0,
  noise_model: "depolarizing",
  backend: "numpy",
};

/** Builds the request fields shared by key-exchange, crypto-demo and transfer simulations. */
export function channelPayload(c, { includeBackend = true } = {}) {
  const body = {
    n_qubits: Number(c.n_qubits),
    eve_probability: c.eve_probability,
    channel_noise: c.channel_noise,
    noise_model: c.noise_model,
  };
  if (c.seed !== "" && c.seed !== null) body.seed = Number(c.seed);
  if (includeBackend) body.backend = c.backend;
  return body;
}

export default function ChannelControls({ value, onChange, showBackend = true }) {
  const set = (k) => (v) => onChange({ ...value, [k]: v });
  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <Select label="Qubits sent" value={String(value.n_qubits)} onChange={set("n_qubits")}
              options={[1024, 2048, 4096, 8192, 16384, 32768].map((n) => ({ value: String(n), label: n.toLocaleString() }))}
              hint="≈4,096 is the minimum for a 256-bit final key" />
      <TextInput label="Seed (optional)" value={value.seed} onChange={set("seed")} inputMode="numeric"
                 placeholder="random" hint="Fix to make the run reproducible" />
      <Slider label="Eve intercept probability" value={value.eve_probability} onChange={set("eve_probability")}
              format={(v) => pct(v, 0)} hint="Fraction of qubits Eve measures and resends" />
      <Slider label="Channel noise" value={value.channel_noise} onChange={set("channel_noise")} max={0.5}
              format={(v) => pct(v, 0)} />
      <Select label="Noise model" value={value.noise_model} onChange={set("noise_model")}
              options={[
                { value: "depolarizing", label: "Depolarizing (QBER ≈ p/2)" },
                { value: "bit_phase_flip", label: "Bit-phase flip (QBER ≈ q)" },
              ]} />
      {showBackend && (
        <Select label="Quantum backend" value={value.backend} onChange={set("backend")}
                options={[
                  { value: "numpy", label: "NumPy — mathematical model (fast)" },
                  { value: "qiskit", label: "Qiskit Aer — circuit simulation" },
                ]} />
      )}
    </div>
  );
}
