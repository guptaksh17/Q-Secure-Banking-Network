// Experiment presets (all run on the backend, stored, and re-loadable) and the pure
// transforms from stored experiment points to chart rows.

const range = (start, stop, step) => {
  const out = [];
  for (let i = 0; start + i * step <= stop + 1e-9; i++) out.push(+(start + i * step).toFixed(4));
  return out;
};

export const PRESETS = {
  eve_vs_qber: {
    name: "eve_vs_qber", kind: "channel_sweep", parameter: "eve_probability",
    values: range(0, 1, 0.1), n_qubits: 4096, trials: 20,
  },
  noise_depolarizing: {
    name: "noise_vs_qber_depolarizing", kind: "channel_sweep", parameter: "noise",
    values: range(0, 0.5, 0.05), n_qubits: 4096, trials: 20, noise_model: "depolarizing",
  },
  noise_bit_phase_flip: {
    name: "noise_vs_qber_bit_phase_flip", kind: "channel_sweep", parameter: "noise",
    values: range(0, 0.5, 0.05), n_qubits: 4096, trials: 20, noise_model: "bit_phase_flip",
  },
  qubits_vs_sifted: {
    name: "qubits_vs_sifted_length", kind: "channel_sweep", parameter: "n_qubits",
    values: [256, 512, 1024, 2048, 4096, 8192, 16384], n_qubits: 4096, trials: 20,
  },
  acceptance_eve: {
    name: "acceptance_vs_eve", kind: "key_exchange_sweep", parameter: "eve_probability",
    values: range(0, 0.5, 0.05), n_qubits: 8192, trials: 10,
  },
  acceptance_noise: {
    name: "acceptance_vs_depolarizing_noise", kind: "key_exchange_sweep", parameter: "noise",
    values: range(0, 0.3, 0.03), n_qubits: 8192, trials: 10, noise_model: "depolarizing",
  },
};

/** Request body for POST /api/experiments. */
export function presetRequest(preset, seed) {
  const { noise_model, ...rest } = preset;
  return { ...rest, seed, ...(noise_model ? { noise_model } : {}) };
}

/** QBER-vs-parameter rows for one measured series (mean, ±sd, closed-form theory). */
export function qberRows(points, key = "m") {
  return points.map((p) => ({
    x: p.value,
    [key]: p.qber.mean,
    [`${key}_err`]: p.qber.std,
    [`${key}_theory`]: p.expected_qber,
  }));
}

/** Merge several single-series row sets on x. */
export function mergeRows(...rowSets) {
  const byX = new Map();
  rowSets.flat().forEach((r) => byX.set(r.x, { ...(byX.get(r.x) ?? {}), ...r }));
  return [...byX.values()].sort((a, b) => a.x - b.x);
}

/** Sifted-key length vs qubits sent, with the n/2 expectation. */
export function siftedRows(points) {
  return points.map((p) => ({
    x: p.n_qubits,
    m: p.sifted_key_length.mean,
    m_err: p.sifted_key_length.std,
    m_theory: p.n_qubits / 2,
  }));
}

/** Acceptance rate rows for a key-exchange sweep. */
export function acceptanceRows(points, key = "m") {
  return points.map((p) => ({ x: p.value, [key]: p.acceptance_rate }));
}

/** Latest stored experiment per preset name from a list response. */
export function latestByName(items) {
  const out = {};
  for (const it of items) {
    if (!out[it.name] || it.created_at > out[it.name].created_at) out[it.name] = it;
  }
  return out;
}
