# Testing Strategy

| Suite | Command (from repo root) | Tests |
|---|---|---|
| Backend (pytest) | `python3.12 dev.py test` · Windows `py -3.12 dev.py test` | ~450 |
| Frontend (Vitest) + production build | `python3.12 dev.py test-ui` | 32 |
| Evaluation smoke run | included in the backend suite (`tests/test_final_evaluation.py`) | 3 |

Useful variants: `dev.py test -k bb84`, `dev.py test -m "not slow"`, `dev.py test -m "not qiskit"`.

## What is tested

| Area | Key properties | Files |
|---|---|---|
| Quantum states | |+⟩, |−⟩ definitions; normalisation; orthonormal bases; mutually unbiased bases (\|⟨z\|x⟩\|² = ½); Born probabilities sum to 1; probability table derived, not hard-coded | `test_qkd_states.py` |
| Backends | Matching basis is deterministic; mismatching is unbiased; NumPy and Qiskit share one contract; circuits contain the right gates | `test_qkd_backends.py` |
| BB84 | Ideal-channel sifted keys agree exactly; sifting keeps about ½; ratio concentrates as 1/√n; reproducibility | `test_bb84.py` |
| Channel | Eve resends in her own basis; Eve is exact when her basis matches; zero parameters draw no randomness; depolarizing output is the uniform mixture; closed-form QBER | `test_channel.py`, `test_eve_noise.py` |
| Spec requirements | Full intercept-and-resend → about 25% QBER (both backends); more noise → higher QBER; noise alone can exceed 11% | `test_eve_noise.py` |
| Estimation | Sample removed from the key; unbiased; Clopper–Pearson exact form and coverage | `test_estimation.py` |
| Reconciliation | All errors removed (1–11%); leakage ≥ Shannon limit and < 1.35×; **Cascade invariant** (no odd-parity block in any pass); verification catches residual errors | `test_reconciliation.py` |
| Privacy amplification | FFT Toeplitz equals the explicit matrix (up to 60k×20k); GF(2) linearity; 2⁻ᵐ collision rate; key-length formula | `test_privacy_amplification.py` |
| Key exchange | High-QBER sessions abort; accepted sessions give identical keys; permissive threshold still yields 0 bits under full attack | `test_key_exchange.py` |
| Crypto | RFC 5869 and McGrew–Viega vectors; every single-bit flip of ciphertext, tag, nonce and AAD rejected; 20,000 unique nonces; counter exhaustion; replay and cache poisoning; reflection | `test_kdf.py`, `test_aead.py`, `test_secure_channel.py` |
| Banking & data | Lifecycle (delivered / blocked / rejected); validation; (key_id, nonce) unique across transactions; **raw SQLite file scanned for every derived key** | `test_transfers.py`, `test_data_policy.py`, `test_db.py` |
| API | Every endpoint, filters, pagination, 404/422, no key fields in any response | `test_api_*.py` |
| Frontend | Formatting, chart transforms, presets within API limits, API client errors, status badges carry icon + label, chart ↔ table toggle | `frontend/src/test/*` |

## Statistical tests

Randomised properties are checked with **fixed seeds** (so tests are deterministic) and
**5σ binomial tolerances**, e.g. |QBER − p/4| < 5·√(p/4·(1 − p/4)/m) for m sifted bits.
Tolerances follow from the sampling distribution, not from observed results.

## Mutation checks (do the tests catch real bugs?)

During development each critical component was deliberately broken, the suite was run, and
the code was restored. Every mutation below made at least one test fail:

| Phase | Deliberate bug | Caught by |
|---|---|---|
| 3 | Eve resends Alice's original state (no disturbance) | channel tests |
| 3 | Depolarizing keeps the basis | depolarizing-mixture test |
| 3 | Eve always measures in Z | basis-uniformity test |
| 4 | Cascade back-tracking disabled | **initially missed** → added the Cascade-invariant test, which now catches it (12 failures) |
| 4 | Sample bits not removed from key | estimation test |
| 4 | PA ignores reconciliation leakage | key-length test |
| 4 | Abort rule ignored | key-exchange tests |
| 4 | Toeplitz off-by-one window | matrix-equivalence test |
| 5 | Nonce counter never advances | nonce-uniqueness tests |
| 5 | Replay cache disabled / poisoned | replay tests |
| 5 | Same key both directions | domain-separation test |
| 5 | AAD not authenticated | AAD tamper tests |
| 5 | Session id ignored in HKDF | cross-session tests |
| 6 | Derived key written into an event / final key in metrics JSON | raw-database scan |
| 6 | Same-bank transfers allowed; wrong-key attack uses the right key; replay not attempted | workflow tests |

## Reproducibility of results

`dev.py experiment final_evaluation` regenerates `docs/results/` from root seed 2024. Same
seed + same package versions ⇒ identical experiment tables. Timings vary by machine.
