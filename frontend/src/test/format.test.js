import { describe, expect, it } from "vitest";
import { bankName, compact, humanize, keyBudgetRows, pct, shortHex, statusMeta } from "../lib/format.js";

describe("format helpers", () => {
  it("formats percentages and missing values", () => {
    expect(pct(0.25)).toBe("25.0%");
    expect(pct(0.1234, 2)).toBe("12.34%");
    expect(pct(null)).toBe("—");
    expect(pct(NaN)).toBe("—");
  });

  it("compacts large numbers", () => {
    expect(compact(950)).toBe("950");
    expect(compact(16384)).toBe("16.4K");
    expect(compact(2_500_000)).toBe("2.5M");
    expect(compact(0.25)).toBe("0.25");
  });

  it("shortens long hex but keeps short hex", () => {
    expect(shortHex("abcd")).toBe("abcd");
    expect(shortHex("a".repeat(40), 4)).toBe("aaaa…aaaa");
    expect(shortHex(null)).toBe("—");
  });

  it("humanizes snake_case codes", () => {
    expect(humanize("qber_above_threshold")).toBe("QBER above threshold");
    expect(humanize("qkd_session_accepted")).toBe("QKD session accepted");
    expect(humanize("insufficient_key")).toBe("Insufficient key");
  });

  it("names fictional banks", () => {
    expect(bankName("bank_a")).toBe("Bank A");
    expect(bankName("bank_b")).toBe("Bank B");
  });

  it("gives every status an icon and label, never color alone", () => {
    for (const s of ["delivered", "blocked", "rejected", "critical", "warning", "info", "unknown_state"]) {
      const m = statusMeta(s);
      expect(m.icon).toBeTruthy();
      expect(m.label).toBeTruthy();
    }
    expect(statusMeta("rejected").tone).toBe("critical");
    expect(statusMeta("delivered").tone).toBe("good");
  });
});

describe("keyBudgetRows", () => {
  const metrics = {
    n_qubits: 4096, sifted_key_length: 2048, remaining_key_length: 1536, final_key_length: 1200,
    privacy_amplification: {
      eve_information_bits: 150.4, reconciliation_leak_bits: 40, verification_leak_bits: 64,
      security_margin_bits: 66.4,
    },
  };

  it("lists stages from qubits to final key, deductions negative", () => {
    const rows = keyBudgetRows(metrics);
    expect(rows[0]).toEqual({ stage: "Qubits sent", bits: 4096 });
    expect(rows.at(-1)).toEqual({ stage: "Final secret key", bits: 1200 });
    expect(rows.filter((r) => r.bits < 0).map((r) => r.bits)).toEqual([-150, -40, -64, -66]);
  });

  it("omits deductions for aborted sessions", () => {
    const rows = keyBudgetRows({ ...metrics, privacy_amplification: null, final_key_length: 0 });
    expect(rows.map((r) => r.stage)).toEqual(["Qubits sent", "After sifting", "After QBER sample", "Final secret key"]);
  });

  it("handles missing metrics", () => {
    expect(keyBudgetRows(null)).toEqual([]);
  });
});
