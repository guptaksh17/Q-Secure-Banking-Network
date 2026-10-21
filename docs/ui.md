# User Interface (Phase 7)

React 18 + Vite 6 + Tailwind CSS 4 + Recharts 3, talking to the FastAPI backend through
`/api` (proxied by Vite in development). Code: `frontend/src/`.

## Pages

| Page | What it shows | Backend calls |
|---|---|---|
| Dashboard | Transfer outcomes, QKD acceptance rate, mean QBER, critical events, recent events | `GET /dashboard/summary` |
| QKD Laboratory | One full key exchange: six pipeline steps, QBER meter vs threshold, "where the bits go" budget, per-qubit trace (Alice → Eve → noise → Bob → sifting) | `POST /qkd/key-exchange` (stored as a lab session) |
| Security Simulator | Layer 1: six fixed-seed scenarios (clean, noise, partial/full Eve, noise-only over threshold) vs the threshold. Layer 2: AES-256-GCM tamper lab (ciphertext/tag/nonce/AAD bit flips, wrong key, replay) with sent-vs-delivered diff | `POST /qkd/key-exchange`, `POST /crypto/demo` |
| Transaction Transfer | Fictional transfer form + simulation conditions; full result: status, wire format, QKD session, event trail | `GET /banks`, `POST /transfers`, `GET /transfers` |
| Experimental Analysis | The four required graphs from **stored, re-runnable experiments**: Eve vs QBER, noise vs QBER (two models), qubits vs sifted length (log–log), acceptance rate vs Eve/noise | `POST /experiments`, `GET /experiments[/{id}]` |
| History & Security Logs | Paged, filterable transactions (with detail view), security events, QKD sessions (estimated vs true QBER) | `GET /transfers`, `/security-events`, `/qkd/sessions` |

## Honesty in the UI

- Every chart point is measured by the backend; the page states trials, qubit count, seed,
  and whether the run was mathematically modelled or circuit-simulated.
- Measured series are mean ± 1 sd (error bars); closed-form theory is dashed in the same hue.
- High QBER is described as disturbance "from Eve *or* noise"; the Security Simulator
  includes a noise-only scenario that crosses the threshold.
- The header states: educational simulation, fictional banks, no real transfers,
  not production security. Key bits are never displayed; only the public `key_id`.

## Visual design

- Color tokens in `src/index.css`, light and dark (follows the OS; `data-theme` overrides).
- Chart series use a validated categorical order (blue, orange, aqua) — checked with the
  palette validator in both modes (CVD ΔE ≥ 9.2, normal-vision ΔE ≥ 20.9). Aqua is below 3:1
  on the light surface, so every experiment chart offers a **data-table view**.
- Status colors (good / warning / critical) are reserved for state and always carry an icon
  and a text label. Hairline grids, ≤ 24 px bars with rounded data ends, 2 px lines, ≥ 8 px markers.
- Verified at 375 px width: no horizontal page scroll on any page.

## Tests

`npm test` (Vitest + Testing Library, jsdom) or `dev.py test-ui` (tests + production build):
formatting helpers, key-budget rows, experiment presets (within backend limits), chart data
transforms, API client (error flattening, URL encoding, unreachable backend), and components
(status badges carry icon + label, qubit trace wording, QBER meter accessible name,
chart ↔ table toggle, request payload building).
