# Q-Secure Banking Network

**Design and Simulation of a Quantum-Secure Banking Communication Network Using BB84 QKD and AES-256-GCM.**

An interactive educational prototype that models secure communication between two
*fictional* banks. BB84 establishes shared key material over a simulated quantum
channel (with optional noise and an intercept-and-resend eavesdropper), QBER drives
a key accept/reject decision, accepted keys are reconciled (Cascade) and
privacy-amplified (Toeplitz hashing), and AES-256-GCM protects each transaction.

> **Scope and honesty statement.** This is a software simulation. It is not a real
> banking network, does not run on quantum hardware, and does not provide
> production-grade QKD security. BB84 (Bennett & Brassard, 1984) and QKD for
> finance are established ideas; our contribution is the integrated, interactive,
> experimentally evaluated teaching prototype. See [docs/limitations.md](docs/limitations.md).

## Documentation

| Document | Contents |
|---|---|
| [docs/REPORT.md](docs/REPORT.md) | **Full project report** — background, design, implementation, evaluation, discussion |
| [docs/results/RESULTS.md](docs/results/RESULTS.md) | Generated experiment tables and figures (seed 2024) |
| [docs/quantum-assumptions.md](docs/quantum-assumptions.md) | Simulation modes, channel model, estimation, Cascade, privacy amplification |
| [docs/cryptography.md](docs/cryptography.md) | HKDF, AES-256-GCM, nonces, replay protection |
| [docs/banking-workflow.md](docs/banking-workflow.md) | Transfer lifecycle, data model, API |
| [docs/ui.md](docs/ui.md) | Pages and visual design |
| [docs/experiment-methodology.md](docs/experiment-methodology.md) | How experiments are seeded and reproduced |
| [docs/testing.md](docs/testing.md) | Test suites, statistical tests, mutation checks |
| [docs/limitations.md](docs/limitations.md) | What is simplified, assumed, or out of scope |
| [docs/demo-guide.md](docs/demo-guide.md) | 12-minute demo script and likely questions |
| [docs/architecture.md](docs/architecture.md) | Module layout |

## Repository layout

```
backend/
  app/qkd/        BB84 states, NumPy & Qiskit backends, channel (Eve, noise), estimation,
                  Cascade, Toeplitz privacy amplification, key-exchange pipeline, sweeps
  app/crypto/     HKDF-SHA256 key derivation, AES-256-GCM sender/receiver, tamper simulation
  app/services/   transfer workflow, event logging, experiment storage
  app/db/         SQLAlchemy models (SQLite; PostgreSQL optional)
  app/api/        FastAPI routes
  experiments/    reproducible experiment scripts + report generator
  tests/          pytest suite
frontend/         React + Vite + Tailwind CSS + Recharts (Vitest tests in src/test)
docs/             report, results, design notes
dev.py            cross-platform helper (setup / test / run / experiment / test-ui)
```

## Prerequisites

- Python **3.12** (required: the pinned dependencies resolve to binary wheels on Windows and macOS only for 3.12)
- Node.js **20 LTS or 22 LTS**
- Git, VS Code

## Quick start

| Step | macOS / Linux | Windows |
|------|---------------|---------|
| Create `backend/.venv`, install `requirements.txt`, copy `.env`, `npm install` | `./setup.sh` | `setup.bat` |
| Run backend tests (extra args pass through, e.g. `-k bb84`) | `./test.sh` | `test.bat` |
| Start FastAPI (:8000) and Vite (:5173); Ctrl+C stops both | `./run.sh` | `run.bat` |
| Frontend tests (Vitest) + production build | `python3.12 dev.py test-ui` | `py -3.12 dev.py test-ui` |
| Regenerate all results, figures and `docs/results/RESULTS.md` | `python3.12 dev.py experiment final_evaluation` | `py -3.12 dev.py experiment final_evaluation` |

Open http://localhost:5173. Interactive API docs: http://127.0.0.1:8000/docs.

All commands go through `dev.py`, which always uses `backend/.venv`'s own interpreter, so no
venv activation is needed.

**Moving between machines:** a venv is tied to the OS that created it. Never copy
`backend/.venv` or `frontend/node_modules` between macOS and Windows — delete them
(or exclude them when copying; `.gitignore` already does) and run setup on the new
machine. In VS Code, pick the interpreter once via *Python: Select Interpreter* →
`backend/.venv`.

### Manual setup (equivalent, Windows PowerShell)

```powershell
py -3.12 -m venv backend\.venv
backend\.venv\Scripts\python -m pip install --upgrade pip
backend\.venv\Scripts\python -m pip install -r requirements.txt   # root file includes backend/requirements.txt
Copy-Item backend\.env.example backend\.env
cd backend; .\.venv\Scripts\python -m pytest
.\.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000
# second terminal
cd frontend; npm install; npm run dev
```

## Configuration

`backend/.env` (copied from `.env.example`): `QSB_QBER_THRESHOLD` (0.11, illustrative),
`QSB_QBER_SAMPLE_FRACTION` (0.25), `QSB_DEFAULT_QUBITS` (4096), `QSB_QUANTUM_BACKEND`
(`numpy` or `qiskit`), `QSB_DATABASE_URL` (SQLite by default), `QSB_RANDOM_SEED`.

## Key results

See [docs/results/RESULTS.md](docs/results/RESULTS.md) for every table and figure.

From the seed-2024 evaluation (about 5,200 BB84 sessions, 1,980 complete key exchanges):

| Finding | Measured | Theory |
|---|---|---|
| Full intercept-and-resend QBER | 24.94% ± 0.73% | 25% |
| Depolarizing p = 0.5 / bit-phase flip q = 0.5 | 25.00% / 50.08% | 25% / 50% |
| Sifting ratio (all n) | 0.498–0.501 | 0.5 |
| Measured points consistent with theory | 50 / 50 (max \|z\| = 2.98) | \|z\| ≤ 3 |
| NumPy vs Qiskit Aer QBER difference | ≤ 0.15 pp (\|z\| ≤ 0.69) | 0 |
| Cascade leakage / Shannon limit | 1.13–1.22 | ≥ 1 |
| QBER where keys stop surviving (8,192 / 32,768 qubits) | ≈ 6–7% / ≈ 7.5–9% | 11% asymptotic, ideal EC |
| Accepted sessions with identical keys at both banks | 1,053 / 1,053 | all |
| End-to-end transfer latency | 3.1 ms median | — |

Main finding: **privacy amplification, not the 11% threshold, is the binding constraint**,
because Cascade's leakage and finite-sample bounds consume the key first.

## Data policy

Raw, sifted, reconciled and final keys are **never persisted** or returned by the
API. Only session parameters/metrics, fictional transaction metadata, ciphertext,
nonce, tag, the public key id, status and security events are stored. A test scans the raw
database file for every derived key.

## Roadmap

1. Repository and environment setup ✅
2. BB84 engine and tests ✅
3. Eve intercept-and-resend and channel noise ✅
4. QBER estimation, sample removal, reconciliation, Toeplitz privacy amplification ✅
5. AES-256-GCM ✅
6. Banking workflow and database ✅
7. React UI and charts ✅
8. Experiments, evaluation and documentation ✅
