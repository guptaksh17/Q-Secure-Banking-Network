# Design and Simulation of a Quantum-Secure Banking Communication Network Using BB84 QKD and AES-256-GCM

**Application:** Q-Secure Banking Network  
**Course:** Quantum Communication & Cryptography — Capstone Project  
**Nature of the work:** educational software simulation (no quantum hardware, no real banking, not production security)

---

## Abstract

We present Q-Secure Banking Network, an interactive, experimentally evaluated simulation
of secure communication between two fictional banks. Each interbank transfer is protected by a key
established with the BB84 quantum key distribution (QKD) protocol over a simulated quantum channel
that can include an intercept-and-resend eavesdropper and configurable noise. The key passes through
the stages of a complete post-processing pipeline:
- basis sifting;
- QBER estimation from a randomly disclosed test sample, with an exact Clopper–Pearson upper bound;
- an accept/abort decision against an illustrative 11% threshold;
- Cascade-inspired error reconciliation with exact leakage accounting and hash verification;
- Toeplitz-hash privacy amplification.

The surviving key is expanded with HKDF-SHA256 into per-direction AES-256-GCM keys, which
encrypt and authenticate each transaction under deterministic, guaranteed-unique nonces, with the
transaction metadata bound as associated data and replays rejected. The system is built as a FastAPI/NumPy/Qiskit
backend with a React/Recharts frontend, stores only non-secret metadata, and is covered by 446
backend and 32 frontend tests.

A reproducible evaluation (root seed 2024; about 5,200 simulated BB84 sessions, including
1,980 complete key exchanges) confirms the expected physics:
- **Full intercept-and-resend:** measured QBER of 24.94% ± 0.73% against a theoretical 25%.
- **Noise:** QBER follows p/2 for the depolarizing channel and q for the bit-phase-flip channel.
- **Sifting:** about half the qubits survive, with a spread that falls as 1/√n.
- **Theory agreement:** all 50 measured points agree with closed-form theory (maximum |z| = 2.98; none above 3).
- **Backends:** a NumPy Born-rule model and Qiskit Aer circuits agree statistically.

The evaluation also shows that **privacy amplification, not the 11% threshold, is the binding
security constraint**:
- **Where keys stop surviving:** at about 6–7% QBER for 8,192 qubits and about 7.5–9% for 32,768 qubits.
- **Why:** Cascade leaks 1.13–1.22 × the Shannon minimum, and finite-sample confidence bounds cost more.

Every accepted session produced identical keys at both banks. In 1,980 sessions one Cascade run left
an undetectable-by-parity error pair; the hash verification caught it and the session aborted safely.

---

## 1. Introduction

### 1.1 Motivation

Interbank messaging today relies on public-key cryptography for key establishment. A large,
fault-tolerant quantum computer running Shor's algorithm [15] would break RSA and elliptic-curve
key exchange. Two responses exist:
- **Post-quantum cryptography:** classical algorithms believed to resist quantum attack, e.g. NIST FIPS 203, ML-KEM [19].
- **Quantum key distribution:** QKD derives key secrecy from physics — measuring an unknown quantum state disturbs it, so eavesdropping shows up as errors.

QKD is a strong teaching subject: the whole chain, from photon states to an authenticated bank
message, can be followed end to end. Real QKD hardware is inaccessible to most students, though,
so this project builds a **faithful, inspectable simulation** of that chain and measures its
behaviour.

### 1.2 Objectives

1. Simulate BB84 preparation, transmission, measurement and sifting, in both a mathematical
   model and gate-level circuits (Qiskit Aer), and be explicit about which is which.
2. Model an intercept-and-resend eavesdropper and physically meaningful channel noise.
3. Estimate QBER from a disclosed-and-discarded sample and abort when it is too high.
4. Reconcile residual errors and apply universal-hash privacy amplification with honest leakage accounting.
5. Protect transactions with AES-256-GCM using unique nonces, and verify authentication tags before delivery.
6. Provide an interactive banking workflow, persistent history and security logs — never persisting keys.
7. Generate every reported result from repeatable experiments.

### 1.3 Contribution and novelty statement

We did **not** invent BB84 (Bennett & Brassard, 1984 [1]). QKD for banking is not new either:
a QKD-secured bank transfer was demonstrated in Vienna in 2004 [20]. Our contribution is an
**integrated, interactive, educational prototype** that brings together, in one tested and
reproducible system:
- BB84;
- configurable attack and noise simulation;
- QBER-driven key acceptance and rejection;
- reconciliation and privacy amplification with exact leakage accounting;
- AES-GCM transaction protection;
- an evaluation that checks every measured quantity statistically against closed-form theory.

---

## 2. Background

### 2.1 BB84

Alice encodes each random bit in one of two conjugate bases:

| Basis | Bit 0 | Bit 1 |
|---|---|---|
| Z (rectilinear) | \|0⟩ | \|1⟩ |
| X (diagonal) | \|+⟩ = (\|0⟩ + \|1⟩)/√2 | \|−⟩ = (\|0⟩ − \|1⟩)/√2 |

The bases are *mutually unbiased*: |⟨z|x⟩|² = ½ for every Z state and X state. Bob measures in
a random basis. Measuring in the same basis gives Alice's bit with certainty; measuring in the
other basis gives a uniformly random outcome (Born rule). Over an authenticated classical
channel they compare **bases only** and keep matching positions (sifting). With independent,
uniform basis choices, about half the positions survive, with standard deviation √(0.25/n) in
the surviving fraction.

### 2.2 QBER and intercept-and-resend

QBER is the fraction of sifted positions where Alice's and Bob's bits differ.

An intercept-and-resend Eve measures each intercepted qubit in a random basis and resends the
state she observed. On a sifted position, she picks the wrong basis with probability ½. Her
resent state is then unbiased in Alice's basis, so Bob errs with probability ½. Intercepting a
fraction p of the qubits therefore gives:

  **QBER_Eve = p/4**, i.e. 25% for a full attack.

In exchange, Eve learns about p/2 of the sifted bits with certainty.

### 2.3 Channel noise

Two standard single-qubit channels are modelled exactly in the BB84 state representation:

- **Depolarizing:** ρ → (1 − p)ρ + p·I/2. Since I/2 equals the uniform mixture of the four BB84
  states, with probability p the state is replaced by a random bit in a random basis. QBER = p/2.
- **Bit-phase flip:** ρ → (1 − q)ρ + q·YρY. Y swaps |0⟩↔|1⟩ and |+⟩↔|−⟩ (up to global phase),
  so the bit flips and the basis is kept. QBER = q.

With Eve placed before the noise (e_E = p_E/4):
- **Depolarizing:** QBER = (1 − p)·e_E + p/2.
- **Bit-phase flip:** QBER = e_E(1 − q) + (1 − e_E)q.

**Noise and eavesdropping both raise QBER and cannot be told apart from QBER alone.**

### 2.4 Parameter estimation

Alice and Bob reveal a random subset of k sifted bits (here 25%) and discard it. The point
estimate ê = errors/k drives the abort rule. For sizing privacy amplification we use the
one-sided **Clopper–Pearson** bound [13]: the smallest e_U with P(X ≤ errors | k, e_U) ≤ ε
(ε = 10⁻³). It is exact for i.i.d. errors.

### 2.5 Error reconciliation: Cascade

Cascade [4] is an interactive binary-search protocol. Each pass permutes the key with a public
random permutation, splits it into blocks, and compares block parities. A BINARY search isolates
one error in each odd-parity block. Correcting a bit flips the parity of the blocks containing
it in earlier passes, which triggers further searches — the *cascade*. Every parity Alice
announces is information about the key and must be subtracted later. The Shannon limit for
reconciliation is n·h(e) bits, where h is the binary entropy.

### 2.6 Privacy amplification

Universal hash families [5] compress a partially secret string into a shorter, nearly uniform
key. The leftover hash lemma [7, 8] gives this guarantee, and it costs about 2·log₂(1/ε) bits of
margin. Binary Toeplitz matrices, fixed by n + m − 1 random bits, form a 2-universal family [6]
and can be applied in O(n log n) time with an FFT. Using the Shor–Preskill argument [2]
(phase-error rate ≈ bit-error rate), Eve's information about n reconciled bits is bounded by
n·h(e), giving the illustrative length:

  **m = ⌊ n(1 − h(e_U)) − leak_EC − leak_verify − 2·log₂(1/ε_PA) ⌋**

With ideal error correction, the asymptotic rate 1 − 2h(e) reaches zero at e ≈ 11%. That is the
origin of the commonly quoted 11% threshold [2, 9].

### 2.7 Classical cryptography

- **HKDF** (RFC 5869 [17]) derives independent keys from input key material, using distinct
  `info` labels.
- **AES-GCM** (NIST SP 800-38D [16]) provides authenticated encryption with associated data.
  Its security collapses if a (key, nonce) pair repeats. The deterministic construction — a fixed
  field followed by an invocation counter — guarantees uniqueness.

---

## 3. System design

### 3.1 Architecture

```
React (Vite, :5173)  ──/api──►  FastAPI (:8000)
  Dashboard                       app/qkd      states · backends (NumPy | Qiskit Aer) · channel (Eve, noise)
  QKD Laboratory                               estimation · Cascade · Toeplitz PA · key-exchange pipeline · sweeps
  Security Simulator              app/crypto   HKDF-SHA256 · AES-256-GCM sender/receiver · tamper simulation
  Transaction Transfer            app/services transfer workflow · security events · experiment storage
  Experimental Analysis           app/db       SQLite (banks, qkd_sessions, transactions, security_events, experiment_results)
  History & Security Logs
```

The QKD engine is pure Python/NumPy with no web or database imports, so it can be unit-tested
and driven directly by experiment scripts. All randomness flows through one injectable
`numpy.random.Generator`.

### 3.2 End-to-end transfer workflow

1. Bank A creates a fictional transfer (validated: `QSB-A-####` / `QSB-B-####` accounts,
   different banks, amount as integer cents) → `CREATED`.
2. A **fresh BB84 session** runs for this transfer → `KEY_EXCHANGE`. If it aborts → `BLOCKED`,
   and nothing is encrypted or sent.
3. HKDF derives per-direction AES-256 keys and a public 8-byte `key_id`. The payload is sealed
   with AES-256-GCM; reference, banks, session and key id are bound as associated data → `ENCRYPTED`.
4. Optional simulated attack in transit: flip a bit of the ciphertext, tag, nonce or AAD; use a wrong key; or replay.
5. Bank B verifies the tag and decrypts → `DELIVERED`, or `REJECTED` on any authentication failure.
6. Every step writes a typed, severity-tagged security event.

### 3.3 Key design decisions

| Decision | Rationale |
|---|---|
| Two simulation modes, labelled in every result | NumPy samples Born-rule probabilities *computed from state vectors*; Qiskit runs X/H/measure circuits on Aer (stabilizer method). Neither is quantum hardware. |
| Channel maps BB84 states to BB84 states | Eve and noise compose without special cases; exact for the modelled channels. |
| Zero-parameter stages draw no randomness | Ideal runs are bit-for-bit identical across phases for the same seed. |
| Point estimate for abort, upper bound for key length | Matches the spec's threshold rule while keeping secrecy sizing conservative. |
| Leakage counted from the actual transcript | Privacy amplification subtracts what was really disclosed. |
| 64-bit Toeplitz hash verification after Cascade | Catches residual even-weight error patterns (observed once in evaluation, §6.4). |
| HKDF only after Toeplitz PA | HKDF performs derivation and domain separation; we do not claim SHA-256 is privacy amplification. |
| Per-direction keys + 4-byte sender field + 64-bit counter | (key, nonce) can never repeat; no caller-supplied nonces; refuses to wrap. |
| Fresh QKD session per transfer | Keys exist only for one request; (key_id, nonce) unique across the whole database. |
| Replay cache updated only after authentication | Forged messages cannot block the genuine one. |
| Never persist key material | Enforced by a test that scans the raw SQLite file for every derived key. |
| High QBER logged as "eavesdropping **or** excess noise" | Avoids claiming proof of an eavesdropper. |

---

## 4. Implementation

| Phase | Deliverable | Main modules |
|---|---|---|
| 1 | Monorepo, pinned dependencies, cross-platform `dev.py` (Windows `.bat` / macOS `.sh`) | `dev.py`, `backend/requirements.txt` |
| 2 | BB84 engine, Born-rule table, NumPy & Qiskit backends | `app/qkd/states.py`, `backends.py`, `bb84.py` |
| 3 | Intercept-and-resend, depolarizing & bit-phase-flip noise, seeded sweeps | `app/qkd/channel.py`, `experiments.py` |
| 4 | Sampling + Clopper–Pearson, abort rule, Cascade, verification, Toeplitz PA | `estimation.py`, `reconciliation.py`, `privacy_amplification.py`, `key_exchange.py` |
| 5 | HKDF, AES-256-GCM with deterministic nonces, replay rejection | `app/crypto/kdf.py`, `aead.py`, `secure_channel.py` |
| 6 | Transfer workflow, SQLite models, security events, REST API | `app/services/transfers.py`, `app/db/models.py`, `app/api/*` |
| 7 | Six-page React UI with Recharts | `frontend/src/pages/*` |
| 8 | Final evaluation, figures, report | `backend/experiments/final_evaluation.py`, `report.py` |

**What is simulated, and how.**

| Behaviour | How it is produced |
|---|---|
| Qubit preparation/measurement (NumPy mode) | Mathematically modelled: outcomes sampled from P(1) = \|⟨b₁\|ψ⟩\|² computed from the state vectors |
| Qubit preparation/measurement (Qiskit mode) | Circuit-simulated on Qiskit Aer: `x` for bit 1, `h` for X preparation, `h` before measurement for X basis |
| Eve's measurement | Same backend as Bob (so circuit-simulated in Qiskit mode) |
| Noise | Applied at the state level in both modes (exact for these channels) |
| Classical messages (sifting, parities, hashes) | Simulated in-process; disclosed bits are counted |
| AES-GCM, HKDF | Real implementations from the `cryptography` library (OpenSSL) |

---

## 5. Experimental methodology

- **One command regenerates everything:** `dev.py experiment final_evaluation` (about 90 s on the
  test machine) writes `docs/results/results.json`, CSV tables, eight figures and
  `docs/results/RESULTS.md`. No value is hand-entered.
- **Reproducibility:** a single root seed (2024). `numpy.random.SeedSequence.spawn` gives every
  (setting, trial) an independent stream. The same seed and package versions reproduce every
  experiment table exactly.
- **Statistics:** each point reports the mean and sample standard deviation over trials.
  Agreement with theory is checked by z = (mean − theory)/(sd/√trials); under correct modelling,
  |z| > 3 should occur in about 0.3% of points.
- **Two notions of QBER:**
  - **E1–E3, E7:** the *true* sifted-key error rate, which only a simulator can know. Used to validate the physics.
  - **E4–E5:** the *sample estimate*, as real parties would use.
- **Environment:** macOS 15.3.1 on Apple silicon (arm64, 8 cores), Python 3.12.13, NumPy 2.5.4,
  Qiskit 2.6.0, Qiskit Aer 0.18.0, cryptography 50.0.2. Timings are specific to this machine;
  experiment tables are not.

| ID | Experiment | Configuration |
|---|---|---|
| E1 | Eve probability vs QBER | p ∈ {0, 0.1, …, 1}; 8,192 qubits; 50 trials |
| E2 | Noise vs QBER (two models) | p ∈ {0, 0.05, …, 0.5}; 8,192 qubits; 50 trials |
| E3 | Qubits vs sifted length | n = 256 … 65,536 (×2); 50 trials |
| E4 | Acceptance & key yield, full pipeline | Eve 0–0.5, depolarizing 0–0.3, bit-phase flip 0–0.15; n ∈ {8,192, 32,768}; 30 trials (1,980 sessions) |
| E5 | Estimation accuracy & bound coverage | 1,000 sessions; depolarizing 0.1 (e = 5%) |
| E6 | Cascade efficiency | e = 1–11%; 10,000-bit keys; 20 trials |
| E7 | NumPy vs Qiskit Aer | Eve ∈ {0, 0.25, 0.5, 1}; 4,096 qubits; 20 trials each |
| P1–P4 | Performance | BB84 throughput; stage timings; HKDF/AES-GCM; end-to-end transfer |

---

## 6. Results

Full tables are in [results/RESULTS.md](results/RESULTS.md); CSVs are in `docs/results/csv/`.

### 6.1 Validation summary

| Check | Points | max \|z\| | \|z\| > 3 |
|---|---|---|---|
| E1 Eve vs QBER | 11 | 2.98 | 0 |
| E2 depolarizing vs QBER | 11 | 1.35 | 0 |
| E2 bit-phase flip vs QBER | 11 | 1.43 | 0 |
| E3 sifted length vs n/2 | 9 | 1.12 | 0 |
| E7 Qiskit vs theory | 4 | 1.01 | 0 |
| E7 Qiskit vs NumPy (two-sample) | 4 | 0.69 | 0 |

All 50 points are consistent with theory.

### 6.2 Eavesdropping and noise (E1, E2)

![E1](results/figures/fig1_eve_vs_qber.png)

- **Linear in Eve's intercept probability:** QBER tracks p/4 closely, from 2.53% at p = 0.1 to
  **24.94% ± 0.73% at p = 1** (theory 25%).
- **What Eve learns:** 50.1% of sifted bits with certainty under full attack (theory 50%).
- **Where the threshold is crossed:** the 11% threshold is first exceeded between p = 0.4
  (9.91%) and p = 0.5 (12.60%).

![E2](results/figures/fig2_noise_vs_qber.png)

- **Noise alone matches theory:** depolarizing noise gives p/2 (25.00% at p = 0.5) and
  bit-phase-flip gives q (50.08% at q = 0.5).
- **Noise alone crosses the threshold:** at 25% depolarizing noise (QBER 12.55%) or 15%
  bit-phase flip (QBER 15.00%), with **no eavesdropper**. This confirms that high QBER signals
  disturbance, not proof of attack.

### 6.3 Sifting (E3)

![E3](results/figures/fig3_sifting.png)

- **Half the qubits survive:** the mean sifting ratio stays within 0.4979–0.5012 for all sizes.
- **The spread matches √(0.25/n):** for example, 0.0050 vs 0.0055 at n = 8,192, and 0.0021 vs
  0.0020 at n = 65,536.

### 6.4 Key acceptance and secret-key yield (E4)

![E4 acceptance](results/figures/fig4_acceptance.png)

| Channel (sessions accepted) | 8,192 qubits | 32,768 qubits |
|---|---|---|
| Eve 25% (QBER ≈ 6.3%) | 87% | 100% |
| Eve 30% (QBER ≈ 7.4–7.5%) | 13% | 100% |
| Eve 35% (QBER ≈ 8.8%) | 0% | 7% |
| Depolarizing 15% (QBER ≈ 7.5%) | 13% | 100% |
| Bit-phase flip 7.5% (QBER ≈ 7.5%) | 13% | 100% |
| Any channel with QBER ≳ 10.5% | 0% | 0% |

![E4 key rate](results/figures/fig5_key_rate.png)

Findings:

1. **Privacy amplification is the binding constraint.** Sessions between about 7% and 11%
   estimated QBER pass the threshold but abort as `insufficient_key`. With Cascade's measured
   efficiency (f ≈ 1.17), the asymptotic key rate already reaches zero at about 9.8% QBER (dashed
   curve), and finite-sample terms move the cut-off lower still.
2. **Finite-size effects shrink with block length.** On a clean channel the yield is 0.328 bits
   per qubit sent at 8,192 qubits and 0.354 at 32,768, against an asymptotic maximum of 0.375
   (½ sifting × ¾ after sampling). The cut-off moves from about 6–7% to about 7.5–9% QBER.
3. **Correctness:** 1,053 of 1,980 sessions were accepted, and **every accepted session produced
   identical final keys** at both banks.
4. **Verification matters.** One session (Eve 5%, 8,192 qubits) aborted as
   `reconciliation_failed`. Reproducing it showed that Cascade corrected 45 of 47 errors, but two
   errors shared a block in all four passes. Even-weight errors are invisible to parity checks.
   The 64-bit hash verification detected the mismatch and the session aborted. Observed rate:
   1 in 1,980 (0.05%). Without verification, the banks would have derived different AES keys —
   which GCM would still have rejected, failing safe.

### 6.5 Estimation accuracy (E5)

![E5](results/figures/fig6_estimation_error.png)

Across 1,000 sessions at e = 5% with a mean test sample of 512 bits:
- **Unbiased:** the estimate minus the true sifted QBER averages **+0.031 percentage points**.
- **Spread as predicted:** standard deviation 0.862 pp, against 0.834 pp predicted for sampling
  without replacement.
- **Bound coverage:** the 99.9% Clopper–Pearson upper bound covered the true error probability
  in 1,000/1,000 runs here, and in 1,979/1,980 E4 runs. Overall 2,979/2,980 (99.97%), consistent
  with the nominal 99.9%.

### 6.6 Reconciliation efficiency (E6)

![E6](results/figures/fig7_cascade_efficiency.png)

| Error rate | 1% | 2% | 3% | 5% | 7% | 9% | 11% |
|---|---|---|---|---|---|---|---|
| Leakage / n·h(e) | 1.129 | 1.140 | 1.153 | 1.166 | 1.190 | 1.192 | 1.217 |

- **Efficiency:** in line with published efficiencies for Cascade.
- **Reliability:** 140 synthetic runs left zero residual errors, and all were verified.
- **Cost:** efficiency worsens as e grows, which, together with h(e), drives the early cut-off in §6.4.

### 6.7 Modelled vs circuit-simulated backends (E7)

| Eve p | NumPy QBER | Qiskit QBER | Theory | Two-sample z |
|---|---|---|---|---|
| 0 | 0.00% | 0.00% | 0.00% | 0.00 |
| 0.25 | 6.30% | 6.19% | 6.25% | −0.69 |
| 0.5 | 12.68% | 12.64% | 12.50% | −0.16 |
| 1 | 24.97% | 24.82% | 25.00% | −0.56 |

The gate-level circuits and the Born-rule model are statistically indistinguishable, which
validates using the much faster NumPy model for large experiments.

### 6.8 Performance (P1–P4)

![Performance](results/figures/fig8_performance.png)

| Measurement | Result |
|---|---|
| BB84 + Eve + noise, NumPy | 6.3 M qubits/s at 1,024 qubits → 19 M qubits/s at 32,768 qubits |
| BB84 + Eve + noise, Qiskit Aer | ~9.4–11 K qubits/s (≈ 2,000× slower: 3.48 s vs 1.72 ms at 32,768 qubits) |
| Full key exchange, 8,192 qubits (QBER ≈ 3%) | 4.2 ms median (Cascade 2.3 ms) |
| Full key exchange, 32,768 qubits | 14.6 ms median (Cascade 8.8 ms ≈ 60%) |
| HKDF-SHA256 session-key derivation | 24.6 µs |
| AES-256-GCM, 256-byte payload | 1.6 µs encrypt, 0.9 µs decrypt + verify |
| End-to-end transfer (QKD + HKDF + AES-GCM + SQLite) | 3.1 ms median, 3.7 ms p95 |

- **Where the time goes:** classical cryptography is negligible next to key establishment, and
  within key establishment Cascade dominates.
- **Missing cost:** in a real deployment, Cascade's many interactive round trips over a network
  — absent here — would dominate latency even more.

---

## 7. Discussion

1. **The physics is reproduced quantitatively, not only qualitatively.** Every QBER and sifting
   point lies within 3 standard errors of closed-form theory, on both backends.
2. **The threshold is a policy; privacy amplification is the security mechanism.** A
   misconfigured 45% threshold still yields zero key bits under full attack (tested), because
   the key-length budget subtracts Eve's bounded information. Conversely, sessions well below
   11% QBER are rejected when the budget cannot pay for leakage and finite-size margins.
3. **Eve and noise cannot be told apart from QBER.** The system therefore logs
   "disturbance consistent with eavesdropping or excess channel noise" and removes the bounded
   information either way.
4. **Defence in depth works.**
   - A QBER abort blocks the transfer before encryption.
   - Cascade's rare residual errors are caught by verification.
   - Any tampering with the ciphertext, tag, nonce or AAD — or a wrong key, or a replay — is
     rejected by AES-GCM authentication and the replay cache.
5. **Finite-size effects are large at teaching-scale block lengths.** Moving from 8,192 to
   32,768 qubits raised the clean-channel yield by 8% and the tolerable QBER by about 1.5
   percentage points. Real systems use far larger blocks.

---

## 8. Security claims and non-claims

**We claim (as properties of this simulation):**
- the modelled channels and attack behave as theory predicts;
- accepted keys are identical at both banks;
- leaked information is accounted for exactly;
- every AES-GCM encryption uses a nonce unique under its key;
- tampering and replays are rejected;
- no key material is persisted or returned by the API.

**We do not claim:**
- production-grade or composable security;
- security against attacks beyond intercept-and-resend;
- that SHA-256 or HKDF performs privacy amplification;
- that 11% is a universal threshold;
- any implementation of authentication on the classical channel.

The key-length formula is Shor–Preskill-style and asymptotic-inspired, with an i.i.d. confidence
bound. It is not a finite-key proof [10]. See [limitations.md](limitations.md).

---

## 9. Testing

| Suite | Count |
|---|---|
| Backend (pytest) | 446 |
| Frontend (Vitest) | 32 |

Highlights:
- **Spec requirements:** the tests listed in the specification are all present.
- **Statistical tests:** 5σ binomial tolerances with fixed seeds.
- **Published vectors:** RFC 5869 (HKDF) and McGrew–Viega (AES-256-GCM) test vectors.
- **Tampering:** every single-bit flip of each AES-GCM field is rejected.
- **Data policy:** the raw-database scan for key material.
- **Mutation testing:** the code was deliberately broken in 20 ways and each break made a test
  fail. One break — Cascade without back-tracking — initially went unnoticed, which led to a new
  test of the Cascade invariant.

See [testing.md](testing.md).

---

## 10. Limitations and future work

**Limitations** (detailed in [limitations.md](limitations.md)):
- idealised single-photon, lossless, noiseless-detector physics;
- a single attack strategy;
- i.i.d. noise;
- PRNG instead of a QRNG;
- unauthenticated classical channel;
- asymptotic-inspired key length;
- simplified Cascade;
- keys in Python memory;
- no API authentication;
- SQLite without migrations;
- a fictional banking domain with no balances or ledger.

**Future work:**
- decoy-state BB84 with loss and detector models;
- collective-attack and Breidbart-basis Eves;
- composable finite-key analysis (smooth min-entropy, separate ε terms);
- LDPC or polar-code reconciliation, to cut leakage and round trips;
- Wegman–Carter authentication of the classical channel;
- a trusted-node multi-bank network topology;
- a hybrid mode combining QKD with ML-KEM (FIPS 203) key encapsulation;
- persistent atomic nonce counters for long-lived keys.

---

## 11. Conclusion

Q-Secure Banking Network demonstrates, end to end and reproducibly, how a BB84-derived key can
protect interbank messages. The simulation:
- reproduces BB84's defining quantitative behaviour — the 25% intercept-and-resend signature,
  50% sifting, and noise-induced QBER — with every measured point consistent with theory;
- shows why privacy amplification, not a QBER threshold, determines whether a usable key exists;
- turns that key into authenticated, replay-protected transactions while never storing a secret.

As an educational prototype, it makes each step of the QKD chain visible, testable and measurable.

---

## References

1. C. H. Bennett and G. Brassard, "Quantum cryptography: Public key distribution and coin tossing," *Proc. IEEE Int. Conf. on Computers, Systems and Signal Processing*, Bangalore, 1984, pp. 175–179.
2. P. W. Shor and J. Preskill, "Simple proof of security of the BB84 quantum key distribution protocol," *Phys. Rev. Lett.* 85, 441 (2000).
3. C. H. Bennett, G. Brassard, C. Crépeau and U. M. Maurer, "Generalized privacy amplification," *IEEE Trans. Inf. Theory* 41(6), 1915–1923 (1995).
4. G. Brassard and L. Salvail, "Secret-key reconciliation by public discussion," *EUROCRYPT '93*, LNCS 765, pp. 410–423 (1994).
5. J. L. Carter and M. N. Wegman, "Universal classes of hash functions," *J. Comput. Syst. Sci.* 18(2), 143–154 (1979).
6. H. Krawczyk, "LFSR-based hashing and authentication," *CRYPTO '94*, LNCS 839, pp. 129–139 (1994).
7. R. Impagliazzo, L. A. Levin and M. Luby, "Pseudo-random generation from one-way functions," *Proc. 21st ACM STOC*, 1989, pp. 12–24.
8. M. N. Wegman and J. L. Carter, "New hash functions and their use in authentication and set equality," *J. Comput. Syst. Sci.* 22(3), 265–279 (1981).
9. V. Scarani, H. Bechmann-Pasquinucci, N. J. Cerf, M. Dušek, N. Lütkenhaus and M. Peev, "The security of practical quantum key distribution," *Rev. Mod. Phys.* 81, 1301 (2009).
10. M. Tomamichel, C. C. W. Lim, N. Gisin and R. Renner, "Tight finite-key analysis for quantum cryptography," *Nature Communications* 3, 634 (2012).
11. W.-Y. Hwang, "Quantum key distribution with high loss: Toward global secure communication," *Phys. Rev. Lett.* 91, 057901 (2003).
12. H.-K. Lo, X. Ma and K. Chen, "Decoy state quantum key distribution," *Phys. Rev. Lett.* 94, 230504 (2005).
13. C. J. Clopper and E. S. Pearson, "The use of confidence or fiducial limits illustrated in the case of the binomial," *Biometrika* 26(4), 404–413 (1934).
14. A. Javadi-Abhari et al., "Quantum computing with Qiskit," arXiv:2405.08810 (2024).
15. P. W. Shor, "Algorithms for quantum computation: discrete logarithms and factoring," *Proc. 35th IEEE FOCS*, 1994, pp. 124–134.
16. M. Dworkin, *Recommendation for Block Cipher Modes of Operation: Galois/Counter Mode (GCM) and GMAC*, NIST SP 800-38D (2007).
17. H. Krawczyk and P. Eronen, *HMAC-based Extract-and-Expand Key Derivation Function (HKDF)*, RFC 5869 (2010).
18. D. A. McGrew and J. Viega, "The Galois/Counter Mode of Operation (GCM)," submission to NIST Modes of Operation process (2004).
19. NIST, *Module-Lattice-Based Key-Encapsulation Mechanism Standard*, FIPS 203 (2024).
20. A. Poppe et al., "Practical quantum key distribution with polarization entangled photons," *Optics Express* 12(16), 3865–3871 (2004).

---

## Appendix A — Reproducing this report

```
python3.12 dev.py setup                          # Windows: py -3.12 dev.py setup
python3.12 dev.py test                           # backend tests
python3.12 dev.py test-ui                        # frontend tests + build
python3.12 dev.py experiment final_evaluation    # regenerates docs/results/ (seed 2024, ~90 s)
python3.12 dev.py run                            # http://localhost:5173
```

## Appendix B — API overview

| Endpoint | Purpose |
|---|---|
| `GET /api/health` | Status, defaults, which simulators are available |
| `POST /api/qkd/bb84` | Raw BB84 run (metrics + qubit trace) |
| `POST /api/qkd/key-exchange` | Full pipeline; stored as a lab session |
| `POST /api/crypto/demo` | Key exchange + AES-GCM with optional tampering |
| `GET /api/banks` | Fictional banks |
| `POST/GET /api/transfers`, `GET /api/transfers/{id}` | Transfer workflow and history |
| `GET /api/qkd/sessions[/{id}]` | QKD session history |
| `GET /api/security-events` | Audit log |
| `GET /api/dashboard/summary` | Aggregates |
| `POST/GET /api/experiments[/{id}]` | Bounded on-demand experiments |

Interactive documentation: http://127.0.0.1:8000/docs.
