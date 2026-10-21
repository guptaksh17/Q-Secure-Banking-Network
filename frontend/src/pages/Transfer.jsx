import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../services/api.js";
import { useAction, useLoad } from "../hooks/useApi.js";
import { Button, Card, ErrorBox, PageHeader, Select, StatusBadge, TextInput } from "../components/ui.jsx";
import ChannelControls, { DEFAULT_CHANNEL, channelPayload } from "../components/ChannelControls.jsx";
import TransactionDetail from "../components/TransactionDetail.jsx";
import { dateTime } from "../lib/format.js";

const ATTACKS = [
  { value: "none", label: "None" },
  { value: "ciphertext", label: "Flip a ciphertext bit in transit" },
  { value: "tag", label: "Flip an authentication-tag bit" },
  { value: "nonce", label: "Flip a nonce bit" },
  { value: "aad", label: "Alter the routing metadata" },
  { value: "wrong_key", label: "Receiver uses the wrong key" },
  { value: "replay", label: "Replay the message" },
];

export default function Transfer() {
  const banks = useLoad(() => api.banks(), []);
  const [form, setForm] = useState({
    sender_account: "QSB-A-1001", receiver_account: "QSB-B-2001",
    amount: "1250.00", currency: "USD", memo: "Invoice 2026-118 (fictional)",
  });
  const [channel, setChannel] = useState(DEFAULT_CHANNEL);
  const [tamper, setTamper] = useState("none");
  const submit = useAction(useCallback((body) => api.createTransfer(body), []));
  const recent = useLoad(() => api.transfers({ limit: 5 }), [submit.data]);
  const set = (k) => (v) => setForm({ ...form, [k]: v });
  const resultRef = useRef(null);
  useEffect(() => {
    if (submit.data) resultRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [submit.data]);

  const accounts = (banks.data ?? []).flatMap((b) => b.example_accounts);

  const onSubmit = (e) => {
    e.preventDefault();
    submit.run({ ...form, simulation: { ...channelPayload(channel, { includeBackend: false }), tamper } });
  };

  return (
    <div className="space-y-6">
      <PageHeader title="Transaction Transfer"
                  subtitle="Send a fictional interbank transfer. A fresh BB84 session establishes the key; AES-256-GCM seals the payload; the receiving bank verifies the tag before recording it." />
      <div className="grid gap-6 lg:grid-cols-5">
        <form onSubmit={onSubmit} className="space-y-6 lg:col-span-3">
          <Card title="Transfer details" subtitle="Accounts must be fictional identifiers (QSB-A-#### or QSB-B-####).">
            <datalist id="qsb-accounts">{accounts.map((a) => <option key={a} value={a} />)}</datalist>
            <div className="grid gap-4 sm:grid-cols-2">
              <TextInput label="From account" value={form.sender_account} onChange={set("sender_account")} list="qsb-accounts" required />
              <TextInput label="To account" value={form.receiver_account} onChange={set("receiver_account")} list="qsb-accounts" required />
              <TextInput label="Amount" value={form.amount} onChange={set("amount")} inputMode="decimal" required
                         hint="0.01 – 1,000,000.00, up to 2 decimals" />
              <Select label="Currency" value={form.currency} onChange={set("currency")}
                      options={["USD", "EUR", "GBP", "INR"].map((c) => ({ value: c, label: c }))} />
              <div className="sm:col-span-2">
                <TextInput label="Memo" value={form.memo} onChange={set("memo")} maxLength={140} />
              </div>
            </div>
          </Card>
          <Card title="Simulation conditions" subtitle="Leave at defaults for a clean channel; add Eve, noise or an in-transit attack to see the defences.">
            <ChannelControls value={channel} onChange={setChannel} showBackend={false} />
            <div className="mt-4 max-w-md">
              <Select label="Attack on the encrypted message" value={tamper} onChange={setTamper} options={ATTACKS} />
            </div>
          </Card>
          <Button type="submit" disabled={submit.running}>{submit.running ? "Securing and sending…" : "Send transfer"}</Button>
          <ErrorBox error={submit.error} />
        </form>
        <Card title="Recent transfers" className="h-fit lg:col-span-2"
              actions={<Link to="/history" className="text-sm font-medium text-accent hover:underline">History</Link>}>
          {recent.data?.items.length ? (
            <ul className="space-y-2">
              {recent.data.items.map((t) => (
                <li key={t.id} className="flex items-center justify-between gap-2 rounded-lg border border-line px-3 py-2 text-sm">
                  <div>
                    <div className="font-mono text-xs">{t.reference}</div>
                    <div className="text-ink-2">{t.amount} {t.currency} · {dateTime(t.created_at)}</div>
                  </div>
                  <StatusBadge status={t.status} />
                </li>
              ))}
            </ul>
          ) : <p className="text-sm text-ink-2">No transfers yet.</p>}
        </Card>
      </div>
      <div ref={resultRef} className="scroll-mt-4">
        {submit.data && <TransactionDetail detail={submit.data} />}
      </div>
    </div>
  );
}
