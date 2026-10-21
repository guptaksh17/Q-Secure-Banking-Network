import { StatusBadge } from "./ui.jsx";
import { dateTime, humanize } from "../lib/format.js";

export default function EventList({ events, compact = false }) {
  if (!events?.length) return <p className="text-sm text-ink-2">No security events yet.</p>;
  return (
    <ol className="space-y-2">
      {events.map((e) => (
        <li key={e.id} className="flex flex-col gap-1 rounded-lg border border-line px-3 py-2 sm:flex-row sm:items-start sm:gap-3">
          <div className="shrink-0 pt-0.5">
            <StatusBadge status={e.severity} />
          </div>
          <div className="min-w-0 flex-1">
            <div className="text-sm font-medium">{humanize(e.event_type)}</div>
            <div className="text-sm text-ink-2">{e.message}</div>
          </div>
          {!compact && <time className="shrink-0 text-xs text-muted">{dateTime(e.created_at)}</time>}
        </li>
      ))}
    </ol>
  );
}
