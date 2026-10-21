import { useState } from "react";
import { api } from "../services/api.js";
import { useLoad } from "../hooks/useApi.js";
import { Button, Card, Empty, ErrorBox, Loading, PageHeader, Select, StatusBadge, Tabs } from "../components/ui.jsx";
import EventList from "../components/EventList.jsx";
import TransactionDetail from "../components/TransactionDetail.jsx";
import { dateTime, humanize, pct } from "../lib/format.js";

const PAGE = 15;

export default function History() {
  return (
    <div className="space-y-6">
      <PageHeader title="History & Security Logs"
                  subtitle="Every transfer, QKD session and security event stored by the backend. No key material is ever stored." />
      <Tabs tabs={[
        { id: "transactions", label: "Transactions" },
        { id: "events", label: "Security events" },
        { id: "sessions", label: "QKD sessions" },
      ]}>
        {(tab) => (
          <>
            {tab === "transactions" && <Transactions />}
            {tab === "events" && <Events />}
            {tab === "sessions" && <Sessions />}
          </>
        )}
      </Tabs>
    </div>
  );
}

function Pager({ offset, total, onChange }) {
  if (!total) return null;
  return (
    <div className="mt-3 flex items-center justify-between text-sm text-ink-2">
      <span>{offset + 1}–{Math.min(offset + PAGE, total)} of {total}</span>
      <div className="flex gap-2">
        <Button variant="secondary" disabled={offset === 0} onClick={() => onChange(Math.max(0, offset - PAGE))}>Previous</Button>
        <Button variant="secondary" disabled={offset + PAGE >= total} onClick={() => onChange(offset + PAGE)}>Next</Button>
      </div>
    </div>
  );
}

function Table({ head, children }) {
  return (
    <div className="overflow-x-auto rounded-lg border border-line">
      <table className="w-full text-left text-sm">
        <thead className="bg-surface-2 text-ink-2">
          <tr>{head.map((h) => <th key={h} className="whitespace-nowrap px-3 py-2 font-medium">{h}</th>)}</tr>
        </thead>
        <tbody className="tabular">{children}</tbody>
      </table>
    </div>
  );
}

function Transactions() {
  const [status, setStatus] = useState("");
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState(null);
  const list = useLoad(() => api.transfers({ status, limit: PAGE, offset }), [status, offset]);
  const detail = useLoad(() => (selected ? api.transfer(selected) : Promise.resolve(null)), [selected]);

  return (
    <div className="space-y-4">
      <Card>
        <div className="mb-4 max-w-xs">
          <Select label="Status" value={status} onChange={(v) => { setStatus(v); setOffset(0); }}
                  options={[{ value: "", label: "All" }, ...["delivered", "blocked", "rejected"].map((s) => ({ value: s, label: humanize(s) }))]} />
        </div>
        <ErrorBox error={list.error} />
        {list.loading && !list.data && <Loading />}
        {list.data && (list.data.items.length === 0 ? <Empty>No transactions match.</Empty> : (
          <>
            <Table head={["Reference", "Created", "From → To", "Amount", "Status", ""]}>
              {list.data.items.map((t) => (
                <tr key={t.id} className={`border-t border-line ${selected === t.id ? "bg-accent-soft" : ""}`}>
                  <td className="px-3 py-2 font-mono text-xs">{t.reference}</td>
                  <td className="whitespace-nowrap px-3 py-2 text-ink-2">{dateTime(t.created_at)}</td>
                  <td className="whitespace-nowrap px-3 py-2">{t.sender_account} → {t.receiver_account}</td>
                  <td className="whitespace-nowrap px-3 py-2 text-right">{t.amount} {t.currency}</td>
                  <td className="px-3 py-2"><StatusBadge status={t.status} /></td>
                  <td className="px-3 py-2 text-right">
                    <button type="button" className="text-sm font-medium text-accent hover:underline"
                            onClick={() => setSelected(t.id)}>Details</button>
                  </td>
                </tr>
              ))}
            </Table>
            <Pager offset={offset} total={list.data.total} onChange={setOffset} />
          </>
        ))}
      </Card>
      {selected && (
        <div>
          <ErrorBox error={detail.error} />
          {detail.loading && <Loading />}
          {detail.data && <TransactionDetail detail={detail.data} />}
        </div>
      )}
    </div>
  );
}

function Events() {
  const [severity, setSeverity] = useState("");
  const [offset, setOffset] = useState(0);
  const list = useLoad(() => api.events({ severity, limit: PAGE, offset }), [severity, offset]);
  return (
    <Card>
      <div className="mb-4 max-w-xs">
        <Select label="Severity" value={severity} onChange={(v) => { setSeverity(v); setOffset(0); }}
                options={[{ value: "", label: "All" }, { value: "critical", label: "Critical" },
                          { value: "warning", label: "Warning" }, { value: "info", label: "Info" }]} />
      </div>
      <ErrorBox error={list.error} />
      {list.loading && !list.data && <Loading />}
      {list.data && (
        <>
          <EventList events={list.data.items} />
          <Pager offset={offset} total={list.data.total} onChange={setOffset} />
        </>
      )}
    </Card>
  );
}

function Sessions() {
  const [purpose, setPurpose] = useState("");
  const [offset, setOffset] = useState(0);
  const list = useLoad(() => api.sessions({ purpose, limit: PAGE, offset }), [purpose, offset]);
  return (
    <Card>
      <div className="mb-4 max-w-xs">
        <Select label="Purpose" value={purpose} onChange={(v) => { setPurpose(v); setOffset(0); }}
                options={[{ value: "", label: "All" }, { value: "transfer", label: "Transfers" }, { value: "lab", label: "Laboratory" }]} />
      </div>
      <ErrorBox error={list.error} />
      {list.loading && !list.data && <Loading />}
      {list.data && (list.data.items.length === 0 ? <Empty>No QKD sessions yet.</Empty> : (
        <>
          <Table head={["Created", "Purpose", "Qubits", "Eve", "Noise", "Est. QBER", "True QBER", "Final key", "Outcome"]}>
            {list.data.items.map((s) => (
              <tr key={s.id} className="border-t border-line">
                <td className="whitespace-nowrap px-3 py-2 text-ink-2">{dateTime(s.created_at)}</td>
                <td className="px-3 py-2">{humanize(s.purpose)}</td>
                <td className="px-3 py-2 text-right">{s.n_qubits.toLocaleString()}</td>
                <td className="px-3 py-2 text-right">{pct(s.eve_probability, 0)}</td>
                <td className="px-3 py-2 text-right">{pct(s.channel_noise, 0)}</td>
                <td className="px-3 py-2 text-right">{pct(s.estimated_qber, 2)}</td>
                <td className="px-3 py-2 text-right">{pct(s.true_qber, 2)}</td>
                <td className="px-3 py-2 text-right">{s.final_key_length}</td>
                <td className="px-3 py-2">
                  <StatusBadge status={s.accepted ? "accepted" : "aborted"}
                               label={s.accepted ? "Accepted" : humanize(s.abort_reason)} />
                </td>
              </tr>
            ))}
          </Table>
          <Pager offset={offset} total={list.data.total} onChange={setOffset} />
        </>
      ))}
    </Card>
  );
}
