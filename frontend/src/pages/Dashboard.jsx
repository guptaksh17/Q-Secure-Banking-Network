import { Link } from "react-router-dom";
import { api } from "../services/api.js";
import { useLoad } from "../hooks/useApi.js";
import { Button, Card, ErrorBox, Loading, PageHeader, Stat, StatusBadge } from "../components/ui.jsx";
import EventList from "../components/EventList.jsx";
import HorizontalBarChart from "../components/charts/HorizontalBarChart.jsx";
import { num, pct, statusMeta } from "../lib/format.js";

const TONE_COLOR = { good: "var(--good)", warning: "var(--warning)", critical: "var(--critical)", neutral: "var(--axis)" };
const SHOWN_STATUSES = ["delivered", "blocked", "rejected"];

export default function Dashboard() {
  const { data, error, loading, reload } = useLoad(() => api.dashboard(), []);

  return (
    <div className="space-y-6">
      <PageHeader
        title="Dashboard"
        subtitle="Interbank activity between two fictional banks, each transfer protected by its own BB84-derived AES-256-GCM key."
        actions={<Button variant="secondary" onClick={reload}>Refresh</Button>}
      />
      <ErrorBox error={error} />
      {loading && !data && <Loading />}
      {data && <DashboardBody data={data} />}
    </div>
  );
}

function DashboardBody({ data }) {
  const t = data.transactions;
  const q = data.qkd_sessions;
  const ev = data.security_events;
  const statusRows = SHOWN_STATUSES.map((s) => {
    const meta = statusMeta(s);
    return { label: `${meta.icon}  ${meta.label}`, value: t.by_status[s] ?? 0, color: TONE_COLOR[meta.tone] };
  });

  if (t.total === 0 && q.total === 0) {
    return (
      <Card>
        <div className="flex flex-col items-start gap-3">
          <p className="text-ink-2">No activity yet. Send a fictional transfer or run a QKD experiment to populate the dashboard.</p>
          <div className="flex gap-2">
            <Link to="/transfer"><Button>New transfer</Button></Link>
            <Link to="/qkd-lab"><Button variant="secondary">Open QKD Laboratory</Button></Link>
          </div>
        </div>
      </Card>
    );
  }

  return (
    <>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <Stat label="Transfers" value={num(t.total)}
              hint={`${num(t.by_status.delivered)} delivered · ${num(t.by_status.blocked)} blocked · ${num(t.by_status.rejected)} rejected`} />
        <Stat label="QKD key acceptance" value={pct(q.acceptance_rate, 0)}
              hint={`${num(q.accepted)} of ${num(q.total)} sessions (transfers + lab)`} />
        <Stat label="Mean estimated QBER" value={pct(q.mean_estimated_qber, 2)} hint="Across all stored sessions" />
        <Stat label="Critical security events" value={num(ev.critical)}
              hint={`${num(ev.warning)} warnings · ${num(ev.info)} info`} />
      </div>

      <div className="grid gap-6 lg:grid-cols-5">
        <Card title="Transfers by outcome" subtitle="Blocked = QKD aborted before encryption; rejected = tag check failed"
              className="lg:col-span-2">
          <HorizontalBarChart rows={statusRows} valueFormat={(v) => num(v)} labelWidth={100} integer />
          <div className="mt-3 flex flex-wrap gap-2">
            {SHOWN_STATUSES.map((s) => <StatusBadge key={s} status={s} />)}
          </div>
        </Card>
        <Card title="Recent security events" className="lg:col-span-3"
              actions={<Link to="/history" className="text-sm font-medium text-accent hover:underline">View all</Link>}>
          <EventList events={data.recent_events.slice(0, 6)} compact />
        </Card>
      </div>
    </>
  );
}
