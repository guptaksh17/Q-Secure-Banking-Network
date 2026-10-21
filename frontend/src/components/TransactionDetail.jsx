import { Card, KeyValues, Mono, StatusBadge } from "./ui.jsx";
import EventList from "./EventList.jsx";
import { bankName, dateTime, humanize, pct, shortHex } from "../lib/format.js";

/** Full transfer view: origination record, encryption fields, QKD session, event trail. */
export default function TransactionDetail({ detail }) {
  const t = detail.transaction;
  const s = detail.qkd_session;
  const enc = t.encryption ?? {};
  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center gap-3">
        <h3 className="text-lg font-semibold">{t.reference}</h3>
        <StatusBadge status={t.status} />
        {t.failure_reason && <span className="text-sm text-ink-2">{humanize(t.failure_reason)}</span>}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        <Card title="Transaction">
          <KeyValues rows={[
            ["Amount", `${t.amount} ${t.currency}`],
            ["From", `${t.sender_account} (${bankName(t.sender_bank)})`],
            ["To", `${t.receiver_account} (${bankName(t.receiver_bank)})`],
            t.memo && ["Memo", t.memo],
            ["Created", dateTime(t.created_at)],
            ["Delivered", dateTime(t.delivered_at)],
            ["Simulated attack", humanize(t.tamper_mode)],
          ]} />
        </Card>
        <Card title="QKD session" subtitle={s ? `id ${s.id.slice(0, 12)}…` : undefined}>
          {s ? (
            <KeyValues rows={[
              ["Outcome", s.accepted ? "Key accepted" : `Aborted (${humanize(s.abort_reason)})`],
              ["Qubits / sifted", `${s.n_qubits.toLocaleString()} / ${s.sifted_key_length.toLocaleString()}`],
              ["Test sample", `${s.test_sample_size} bits, ${s.test_sample_errors} errors`],
              ["Estimated QBER", `${pct(s.estimated_qber, 2)} (threshold ${pct(s.qber_threshold, 0)})`],
              ["Eve / noise", `${pct(s.eve_probability, 0)} / ${pct(s.channel_noise, 0)} ${humanize(s.noise_model)}`],
              ["Final key", `${s.final_key_length} bits`],
              ["Key id (public)", s.key_id ?? "—"],
            ]} />
          ) : <p className="text-sm text-ink-2">No session.</p>}
        </Card>
      </div>
      <Card title="Wire format (AES-256-GCM)"
            subtitle="Only these public values are stored — never the key">
        {enc.ciphertext ? (
          <div className="space-y-2 text-sm">
            <div><span className="text-ink-2">Nonce (96-bit): </span><Mono>{enc.nonce}</Mono></div>
            <div><span className="text-ink-2">Auth tag (128-bit): </span><Mono>{enc.auth_tag}</Mono></div>
            <div><span className="text-ink-2">Ciphertext: </span><Mono>{shortHex(enc.ciphertext, 24)}</Mono></div>
            <div><span className="text-ink-2">Associated data: </span><Mono>{enc.associated_data}</Mono></div>
            <div className="pt-1">
              Tag verified by receiving bank:{" "}
              <StatusBadge status={t.tag_verified ? "verified" : "rejected"}
                           label={t.tag_verified ? "Verified" : "Failed"} />
            </div>
          </div>
        ) : (
          <p className="text-sm text-ink-2">Nothing was encrypted — the transfer was blocked before any key existed.</p>
        )}
      </Card>
      <Card title="Event trail">
        <EventList events={detail.events} />
      </Card>
    </div>
  );
}
