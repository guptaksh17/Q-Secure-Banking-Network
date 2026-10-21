import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { StatusBadge } from "../components/ui.jsx";
import QubitTrace from "../components/QubitTrace.jsx";
import QberMeter from "../components/QberMeter.jsx";
import { ChartWithTable } from "../components/charts/chartKit.jsx";
import { channelPayload } from "../components/ChannelControls.jsx";

describe("StatusBadge", () => {
  it("shows an icon and a text label, not color alone", () => {
    render(<StatusBadge status="rejected" />);
    const badge = screen.getByText("Rejected");
    expect(badge).toBeInTheDocument();
    expect(badge.textContent).toContain("✕");
  });
  it("accepts a custom label", () => {
    render(<StatusBadge status="accepted" label="1228-bit key" />);
    expect(screen.getByText("1228-bit key")).toBeInTheDocument();
  });
});

describe("QubitTrace", () => {
  const row = (over) => ({
    index: 0, alice_bit: 1, alice_basis: "X", state: "|->", eve_intercepted: false, eve_basis: null,
    eve_result: null, noise_applied: false, bob_basis: "X", bob_result: 1, bases_match: true, error: false, ...over,
  });

  it("labels kept, discarded and erroneous qubits in words", () => {
    render(<QubitTrace rows={[
      row({ index: 0 }),
      row({ index: 1, bob_basis: "Z", bases_match: false }),
      row({ index: 2, bob_result: 0, error: true, eve_intercepted: true, eve_basis: "Z", eve_result: 0 }),
    ]} />);
    expect(screen.getByText("kept")).toBeInTheDocument();
    expect(screen.getByText("discarded")).toBeInTheDocument();
    expect(screen.getByText("kept · error")).toBeInTheDocument();
    expect(screen.getByText("Z→0")).toBeInTheDocument();
  });

  it("renders nothing without rows", () => {
    const { container } = render(<QubitTrace rows={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
});

describe("QberMeter", () => {
  it("announces QBER against the threshold", () => {
    render(<QberMeter qber={0.2491} upper={0.27} threshold={0.11} />);
    expect(screen.getByRole("img")).toHaveAccessibleName("QBER 24.91% versus threshold 11%");
  });
});

describe("ChartWithTable", () => {
  it("toggles between chart and an equivalent data table", () => {
    render(<ChartWithTable caption="cap" chart={<div>CHART</div>}
                           columns={[{ key: "x", label: "X" }, { key: "y", label: "Y", format: (v) => `${v}%` }]}
                           rows={[{ x: 1, y: 2 }]} />);
    expect(screen.getByText("CHART")).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Show data table" }));
    expect(screen.queryByText("CHART")).not.toBeInTheDocument();
    expect(screen.getByRole("table")).toBeInTheDocument();
    expect(screen.getByText("2%")).toBeInTheDocument();
  });
});

describe("channelPayload", () => {
  it("omits an empty seed and converts types", () => {
    const base = { n_qubits: "8192", seed: "", eve_probability: 0.5, channel_noise: 0, noise_model: "depolarizing", backend: "qiskit" };
    expect(channelPayload(base)).toEqual({
      n_qubits: 8192, eve_probability: 0.5, channel_noise: 0, noise_model: "depolarizing", backend: "qiskit",
    });
    expect(channelPayload({ ...base, seed: "42" }, { includeBackend: false })).toEqual({
      n_qubits: 8192, seed: 42, eve_probability: 0.5, channel_noise: 0, noise_model: "depolarizing",
    });
  });
});
