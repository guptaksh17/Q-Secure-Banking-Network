// Thin fetch wrapper. In development, Vite proxies /api to http://127.0.0.1:8000.
const BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api";

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

// FastAPI returns {detail: "msg"} or {detail: [{loc, msg}, ...]} for validation errors.
export function errorMessage(body, status) {
  const detail = body?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d) => {
        const field = (d.loc || []).filter((p) => p !== "body").join(".");
        return field ? `${field}: ${d.msg}` : d.msg;
      })
      .join("; ");
  }
  return `Request failed (${status})`;
}

async function request(method, path, body) {
  let response;
  try {
    response = await fetch(`${BASE_URL}${path}`, {
      method,
      headers: body === undefined ? undefined : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError("Cannot reach the backend. Is it running on port 8000?", 0);
  }
  const data = await response.json().catch(() => null);
  if (!response.ok) throw new ApiError(errorMessage(data, response.status), response.status);
  return data;
}

export function query(params) {
  const q = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") q.set(k, String(v));
  });
  const s = q.toString();
  return s ? `?${s}` : "";
}

export const api = {
  health: () => request("GET", "/health"),
  banks: () => request("GET", "/banks"),
  dashboard: () => request("GET", "/dashboard/summary"),
  keyExchange: (body) => request("POST", "/qkd/key-exchange", body),
  cryptoDemo: (body) => request("POST", "/crypto/demo", body),
  createTransfer: (body) => request("POST", "/transfers", body),
  transfers: (params = {}) => request("GET", `/transfers${query(params)}`),
  transfer: (id) => request("GET", `/transfers/${encodeURIComponent(id)}`),
  sessions: (params = {}) => request("GET", `/qkd/sessions${query(params)}`),
  session: (id) => request("GET", `/qkd/sessions/${encodeURIComponent(id)}`),
  events: (params = {}) => request("GET", `/security-events${query(params)}`),
  runExperiment: (body) => request("POST", "/experiments", body),
  experiments: (params = {}) => request("GET", `/experiments${query(params)}`),
  experiment: (id) => request("GET", `/experiments/${encodeURIComponent(id)}`),
};
