import { describe, expect, it } from "vitest";
import {
  PRESETS, acceptanceRows, latestByName, mergeRows, presetRequest, qberRows, siftedRows,
} from "../lib/experiments.js";

const point = (value, mean, std, expected) => ({ value, qber: { mean, std }, expected_qber: expected });

describe("experiment presets", () => {
  it("stay inside the backend's request limits", () => {
    for (const p of Object.values(PRESETS)) {
      expect(p.values.length).toBeGreaterThan(0);
      expect(p.values.length).toBeLessThanOrEqual(21);
      expect(p.trials).toBeLessThanOrEqual(50);
      const n = p.parameter === "n_qubits" ? Math.max(...p.values) : p.n_qubits;
      expect(n).toBeLessThanOrEqual(32768);
      expect(p.values.length * p.trials * n).toBeLessThanOrEqual(20_000_000);
    }
  });

  it("generates exact grid values without float drift", () => {
    expect(PRESETS.eve_vs_qber.values).toEqual([0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1]);
    expect(PRESETS.acceptance_noise.values.at(-1)).toBe(0.3);
  });

  it("builds request bodies with seed and optional noise model", () => {
    expect(presetRequest(PRESETS.eve_vs_qber, 7)).toMatchObject({ seed: 7, kind: "channel_sweep" });
    expect(presetRequest(PRESETS.eve_vs_qber, 7)).not.toHaveProperty("noise_model");
    expect(presetRequest(PRESETS.noise_bit_phase_flip, 1).noise_model).toBe("bit_phase_flip");
  });
});

describe("chart transforms", () => {
  it("maps QBER points to measured, error and theory keys", () => {
    expect(qberRows([point(0.5, 0.126, 0.005, 0.125)], "e")).toEqual([
      { x: 0.5, e: 0.126, e_err: 0.005, e_theory: 0.125 },
    ]);
  });

  it("merges series on x and sorts", () => {
    const rows = mergeRows(
      qberRows([point(0.1, 0.05, 0, 0.05), point(0, 0, 0, 0)], "a"),
      qberRows([point(0.1, 0.1, 0, 0.1)], "b"),
    );
    expect(rows.map((r) => r.x)).toEqual([0, 0.1]);
    expect(rows[1]).toMatchObject({ a: 0.05, b: 0.1 });
    expect(rows[0].b).toBeUndefined();
  });

  it("uses n/2 as the sifting expectation", () => {
    const rows = siftedRows([{ n_qubits: 1024, sifted_key_length: { mean: 510, std: 15 } }]);
    expect(rows[0]).toEqual({ x: 1024, m: 510, m_err: 15, m_theory: 512 });
  });

  it("maps acceptance rates", () => {
    expect(acceptanceRows([{ value: 0.2, acceptance_rate: 0.3 }], "eve")).toEqual([{ x: 0.2, eve: 0.3 }]);
  });

  it("picks the latest stored run per name", () => {
    const latest = latestByName([
      { name: "a", id: "1", created_at: "2026-10-01T00:00:00Z" },
      { name: "a", id: "2", created_at: "2026-10-02T00:00:00Z" },
      { name: "b", id: "3", created_at: "2026-10-01T00:00:00Z" },
    ]);
    expect(latest.a.id).toBe("2");
    expect(latest.b.id).toBe("3");
  });
});
