# Quantum Simulation Assumptions

Living document — every phase that adds a modelling choice records it here.

## Simulation modes

| Mode | Setting | What is actually simulated |
|------|---------|----------------------------|
| `numpy` | `QSB_QUANTUM_BACKEND=numpy` | Outcomes sampled from `PROB_ONE[prep_basis, bit, meas_basis]`, a table computed from the state vectors via the Born rule P(m) = \|⟨b_m\|ψ⟩\|² (`app/qkd/states.py`). Matching basis → deterministic; mismatching → 1/2. Mathematically modelled, not circuit-simulated. |
| `qiskit` | `QSB_QUANTUM_BACKEND=qiskit` | One circuit per chunk of ≤1000 qubits: `x` if bit = 1, `h` if prepared in X, `h` before measurement if measured in X, then `measure` (`app/qkd/backends.py`). Executed with Qiskit Aer's stabilizer method (exact for these Clifford-only, unentangled circuits), 1 shot. Circuit-simulated on a classical computer. |

Neither mode involves physical quantum hardware.

## Bases and states

- Z basis: |0⟩, |1⟩
- X basis: |+⟩ = (|0⟩ + |1⟩)/√2, |−⟩ = (|0⟩ − |1⟩)/√2

## Phase 2 protocol model

- Alice draws bits and bases independently and uniformly; Bob draws bases independently and uniformly.
- Sifting compares bases only, never bit values. Expected sifting ratio = 1/2;
  standard deviation over n qubits = sqrt(0.25 / n) (≈0.0035 at n = 20,000).
- `true_sifted_errors` compares full sifted keys — only possible inside a simulator.
  Real parties estimate QBER from a disclosed sample (Phase 4, below).

## Phase 3 channel model (`app/qkd/channel.py`)

Topology: **Alice → Eve (intercept-and-resend) → noisy channel → Bob.**
Every stage maps BB84 states to BB84 states (or exact classical mixtures of them).

| Stage | Parameter | Model | Sifted-QBER contribution |
|-------|-----------|-------|--------------------------|
| Eve | `eve_probability` p_E | Each qubit intercepted independently w.p. p_E; Eve measures in a uniform random basis (via the same backend as Bob, so circuit-simulated in Qiskit mode) and resends her outcome in her basis. | p_E / 4 |
| Depolarizing | `noise` p | ρ → (1−p)ρ + p·I/2. I/2 equals the uniform mixture of the four BB84 states, so w.p. p the state is replaced by a random bit in a random basis (exact). | p / 2 |
| Bit-phase flip | `noise` q | ρ → (1−q)ρ + q·YρY. Y swaps \|0⟩↔\|1⟩ and \|+⟩↔\|−⟩ up to global phase: bit flips, basis kept. | q |

Combined expected QBER (infinite-key limit), with e_E = p_E/4:

- depolarizing: QBER = (1 − p)·e_E + p/2
- bit-phase flip: QBER = e_E(1 − q) + (1 − e_E)q

Derivation of p_E/4: on a sifted position Eve picks the wrong basis w.p. 1/2; her
resent state is then unbiased in Alice's basis, so Bob errs w.p. 1/2.

Eve's information: on sifted positions she knows Alice's bit with certainty when she
intercepted in the correct basis — expected fraction p_E/2 (reported as
`eve_known_sifted_fraction`). Noise gives Eve no information.

Noise is applied at the state level in both modes; Qiskit circuits cover preparation and
measurement. Because the channels act on BB84 states exactly as tabulated, applying them
as circuit-level gates/noise would yield the same outcome distribution.

Not modelled: photon loss, detector efficiency/dark counts, multi-photon pulses and
photon-number-splitting, Eve strategies other than full-basis intercept-and-resend
(e.g. Breidbart-basis or collective attacks).

**Important:** QBER from noise is indistinguishable from QBER caused by Eve. Pure noise
can exceed the 11% illustrative threshold with no eavesdropper present (tested in
`tests/test_eve_noise.py`); high QBER signals disturbance, not proof of attack.

## Phase 4 key processing (`app/qkd/key_exchange.py`)

Pipeline: sifted key → **test-sample disclosure** → **abort rule** → **Cascade** →
**hash verification** → **Toeplitz privacy amplification** → final key (in memory only).

### Parameter estimation (`estimation.py`)

- Alice picks `round(f · n_sifted)` positions uniformly without replacement (f = 0.25
  by default) and both reveal those bits. Revealed bits are **removed** from the key.
- Point estimate ê = errors / k drives the abort rule: abort if ê > threshold (0.11,
  illustrative).
- One-sided **Clopper–Pearson** upper bound e_U at confidence 1 − 10⁻³ is used for
  key-length sizing. Assumes i.i.d. errors (true for this simulator; corresponds to
  collective-attack analyses), not a general finite-key proof.
- Abort if the sample has fewer than 50 bits (`sample_too_small`).

### Reconciliation (`reconciliation.py`) — Cascade-inspired

- Brassard–Salvail Cascade: 4 passes, k₁ = ⌈0.73 / max(ê, 0.01)⌉, k_{i+1} = 2k_i,
  identity permutation on pass 1 and public random permutations afterwards, BINARY
  search on odd-parity blocks, and the cascade step (re-search earlier-pass blocks
  whose parity a correction changed).
- **Every announced parity is counted** as leaked (block parities + binary-search steps).
  Measured efficiency: leaked ≈ 1.10–1.22 × n·h(e), consistent with published Cascade
  figures; tests assert ≥ the Shannon limit n·h(e).
- Verification: 64-bit Toeplitz hash under a fresh public seed (collision 2⁻⁶⁴);
  mismatch → abort (`reconciliation_failed`). The 64 bits are counted as leaked.
- Simplifications: fixed doubling block sizes, no BICONF or later Cascade optimisations.
  Messages are simulated in-process; only Alice's announcements are counted.

### Privacy amplification (`privacy_amplification.py`)

- Toeplitz matrix T (m × n) from n + m − 1 public random bits; output T·x mod 2.
  2-universal family ⇒ leftover hash lemma applies. Computed via exact FFT convolution;
  tests check equality with the explicit matrix product, GF(2) linearity, and the 2⁻ᵐ
  collision rate.
- Illustrative final length (Shor–Preskill-style, asymptotic-inspired):

  m = ⌊ n(1 − h(e_U)) − leak_EC − leak_verify − 2·log₂(1/ε_PA) ⌋, with ε_PA = 10⁻¹⁰.

  n·h(e_U) bounds Eve's information assuming phase-error rate = bit-error rate
  (symmetric channel). Abort if m < 256 (`insufficient_key`) — one AES-256 key.
- This is **not** a composable finite-key security proof and we do not claim
  production-grade security. SHA-256 is not used for privacy amplification.

### Observed consequence (from `key_acceptance` experiment)

With 8,192 qubits, keys stop surviving at QBER ≈ 6–7%, *below* the 11% threshold:
Cascade's ~1.2× leakage moves the asymptotic break-even to ≈ 9.8%, and finite-sample
terms cost the rest. Between ≈ 7% and 11% sessions pass the threshold but abort as
`insufficient_key`. Privacy amplification, not the threshold, is the binding gate; even
with a misconfigured permissive threshold, full intercept-and-resend yields 0 key bits
(tested).

## Randomness

All protocol randomness comes from one `numpy.random.Generator` (PCG64), seeded for
reproducible experiments or seeded from OS entropy otherwise. PCG64 is **not** a
cryptographic or quantum random-number generator; a real QKD system needs a QRNG or
at least a CSPRNG. AES-GCM keys/nonces (Phase 5) will use OS cryptographic randomness.

## Known idealisations (to be extended)

- Single-photon source; no multi-photon pulses (so no photon-number-splitting attack).
- Lossless channel unless loss is explicitly modelled.
- Classical channel assumed authenticated (authentication itself is not implemented).
- QBER threshold of 11% is illustrative, not a universal security bound.
- High QBER indicates disturbance; it does not by itself prove an eavesdropper.
