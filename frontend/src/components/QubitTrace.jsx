/** Per-qubit walkthrough of the first pulses of a BB84 run. */
export default function QubitTrace({ rows }) {
  if (!rows?.length) return null;
  return (
    <div className="overflow-x-auto rounded-lg border border-line">
      <table className="w-full text-center text-sm">
        <caption className="sr-only">First qubits of the run, from Alice's preparation to Bob's measurement</caption>
        <thead className="bg-surface-2 text-xs text-ink-2">
          <tr>
            <th className="px-2 py-2 font-medium">#</th>
            <th className="px-2 py-2 font-medium">Alice bit</th>
            <th className="px-2 py-2 font-medium">Alice basis</th>
            <th className="px-2 py-2 font-medium">State sent</th>
            <th className="px-2 py-2 font-medium">Eve</th>
            <th className="px-2 py-2 font-medium">Noise</th>
            <th className="px-2 py-2 font-medium">Bob basis</th>
            <th className="px-2 py-2 font-medium">Bob result</th>
            <th className="px-2 py-2 font-medium">Sifting</th>
          </tr>
        </thead>
        <tbody className="tabular font-mono">
          {rows.map((r) => (
            <tr key={r.index} className={`border-t border-line ${r.bases_match ? "" : "text-muted"}`}>
              <td className="px-2 py-1.5">{r.index}</td>
              <td className="px-2 py-1.5">{r.alice_bit}</td>
              <td className="px-2 py-1.5">{r.alice_basis}</td>
              <td className="px-2 py-1.5">{r.state}</td>
              <td className="px-2 py-1.5">{r.eve_intercepted ? `${r.eve_basis}→${r.eve_result}` : "—"}</td>
              <td className="px-2 py-1.5">{r.noise_applied ? "yes" : "—"}</td>
              <td className="px-2 py-1.5">{r.bob_basis}</td>
              <td className="px-2 py-1.5">{r.bob_result}</td>
              <td className="whitespace-nowrap px-2 py-1.5 font-sans text-xs">
                {!r.bases_match && "discarded"}
                {r.bases_match && !r.error && <span><span aria-hidden="true" className="font-bold text-good-ink">✓ </span>kept</span>}
                {r.error && <span><span aria-hidden="true" className="font-bold text-critical-ink">✕ </span>kept · error</span>}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
