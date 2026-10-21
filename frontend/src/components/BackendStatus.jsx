import { api } from "../services/api.js";
import { useLoad } from "../hooks/useApi.js";

/** Compact header indicator: API reachability + whether Qiskit circuit simulation is available. */
export default function BackendStatus() {
  const { data, error, loading } = useLoad(() => api.health(), []);
  if (loading) return <span className="text-xs text-muted">Connecting…</span>;
  if (error) {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs text-ink" title={error.message}>
        <span aria-hidden="true" className="font-bold text-critical-ink">✕</span> Backend offline
      </span>
    );
  }
  const circuits = data.capabilities.circuit_simulation_available;
  return (
    <span className="inline-flex items-center gap-1.5 text-xs text-ink-2"
          title={`QBER threshold ${data.qkd_defaults.qber_threshold}; ${data.disclaimer}`}>
      <span aria-hidden="true" className="font-bold text-good-ink">✓</span>
      API online · {circuits ? `Qiskit Aer ${data.capabilities.qiskit_aer}` : "NumPy model only"}
    </span>
  );
}
