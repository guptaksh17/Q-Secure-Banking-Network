# Limitations and Threats to Validity

This project is an **educational software simulation**. It is not a banking system, it does
not run on quantum hardware, and it does not provide production-grade QKD security. This
document lists what is simplified, what is assumed, and what is out of scope, so the results
can be read for what they are.

## 1. Physical model

| Simplification | Consequence | What a real system needs |
|---|---|---|
| Ideal single-photon source | No multi-photon pulses, so the photon-number-splitting attack is impossible here | Weak coherent pulses with decoy states (Hwang 2003; Lo, Ma & Chen 2005) |
| Lossless channel, perfect detectors | Every qubit arrives and is detected; no dark counts, afterpulsing or efficiency mismatch | Loss and detector models; key rate falls exponentially with fibre length |
| Noise is independent per qubit (depolarizing or bit-phase flip) | Errors are i.i.d., which the estimation bound relies on | Correlated, drifting and basis-dependent errors |
| Fixed topology: Eve then noise | Eve's resent states are also degraded by noise | Arbitrary placement; Eve may hide inside the noise budget |
| Simulated on a classical computer | NumPy mode samples Born-rule probabilities; Qiskit mode runs Clifford circuits on Aer — both are classical simulations | Physical photonic hardware |
| Pseudo-random numbers (NumPy PCG64) for bits, bases and public choices | Reproducible, but not a quantum or cryptographic RNG | A quantum RNG for bases/bits, a CSPRNG for public randomness |

## 2. Adversary model

- **Only intercept-and-resend in a uniformly random Z/X basis** is implemented. Not modelled:
  intermediate (Breidbart) basis attacks, optimal cloning, collective and coherent attacks,
  photon-number splitting, Trojan-horse and detector-blinding side channels, and attacks on
  the classical channel.
- **The classical channel is assumed authenticated** but authentication is not implemented.
  Real BB84 needs a pre-shared key and information-theoretic MACs (e.g. Wegman–Carter);
  without them a man-in-the-middle defeats the protocol.
- **High QBER is not proof of an eavesdropper.** Noise alone exceeds the 11% threshold
  (demonstrated in experiment E2 and in the Security Simulator); the system can only say the
  channel was disturbed.

## 3. Security analysis

- **Key-length formula is illustrative.** m = n(1 − h(e_U)) − leak_EC − leak_verify − 2·log₂(1/ε)
  combines a Shor–Preskill-style bound (phase-error rate assumed equal to bit-error rate) with
  the leftover-hash-lemma margin. It is **not a composable finite-key proof** (cf. Tomamichel
  et al. 2012); it has no smooth min-entropy analysis and no separate parameter-estimation
  failure probability in the final security statement.
- **The Clopper–Pearson bound assumes i.i.d. errors.** That is true for this simulator, and
  it corresponds to collective-attack-style analyses. It does not hold against a general adversary.
- **The 11% abort threshold is illustrative**, not a universal security limit. In practice
  privacy amplification is the binding constraint (experiment E4: keys stop surviving at
  roughly 6–7% QBER for 8,192 qubits).
- **Public randomness** (sample positions, Cascade permutations, Toeplitz seeds) comes from
  the session's PRNG; a real system would use fresh, independent randomness.

## 4. Reconciliation and privacy amplification

- Cascade is simplified: fixed 4 passes, block sizes doubling from k₁ = ⌈0.73/QBER⌉, no BICONF
  or later optimisations. The protocol messages are simulated in-process; the leakage *count*
  matches what Alice announces, but there is no network latency. Real Cascade is highly
  interactive, and its round trips dominate latency over long links.
- Measured leakage is about 1.1–1.25 × the Shannon limit (E6). Modern LDPC or polar codes
  achieve lower leakage with one-way communication.
- Toeplitz hashing is computed with an exact FFT convolution. The seed is public, as the
  protocol allows.

## 5. Classical cryptography and engineering

- Keys live in Python process memory. Python cannot reliably zeroise memory, and there is no
  HSM or secure enclave.
- The nonce counter and replay cache are in memory for the lifetime of one session key. Keys
  are never persisted, so a restart loses both together and a nonce cannot be reused — but a
  long-lived key would need a persistent, atomic counter.
- The API has no user authentication, TLS, rate limiting or audit signing. CORS is set up for
  local development only.
- SQLite with `create_all` and no migrations; single process; not built for concurrency or
  high availability.
- AES-256-GCM and HKDF come from the `cryptography` library (OpenSSL). Nothing here
  implements primitives from scratch, and that's deliberate.

## 6. Banking domain

- Two fictional banks and fictional account identifiers; no balances, double-entry ledger,
  settlement, reversal or idempotency keys.
- No regulatory scope (e.g. PCI DSS, ISO 20022 messaging, KYC/AML). Do not use real account
  data; the input validation rejects anything that does not look like `QSB-A-####` / `QSB-B-####`.

## 7. Deployment reality of QKD

Real QKD links are distance-limited (typically tens to about a hundred kilometres of fibre
without trusted nodes), need dedicated optical hardware, and deliver modest key rates. Wide-area
networks rely on trusted relay nodes, which reintroduce trust assumptions. This prototype
abstracts all of that away.

## 8. Threats to validity of the experiments

- **Internal:** statistical tests use fixed seeds, so they are deterministic. Tolerances (about 5σ)
  were chosen before the results were seen. Mutation checks confirmed the tests fail when the
  physics or cryptography is broken (see `docs/testing.md`).
- **Construct:** "QBER" in E1–E3 is the true sifted-key error rate, which only a simulator can
  know. E4–E5 use the sample estimate, as a real system would.
- **External:** performance figures come from one machine (recorded in
  `docs/results/RESULTS.md`) and will differ elsewhere. The experiment tables themselves are
  reproducible bit for bit from the recorded seed and package versions.
