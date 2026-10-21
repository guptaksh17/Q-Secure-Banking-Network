# Experiment Methodology

Every number in a chart or report table is produced by a script in
`backend/experiments/`, run against the simulator. Nothing is hand-entered,
interpolated or smoothed.

## Final evaluation (Phase 8)

`python3.12 dev.py experiment final_evaluation` (Windows: `py -3.12 ...`) runs experiments
E1–E7 and benchmarks P1–P4 and writes `docs/results/` (results.json, csv/, figures/,
RESULTS.md) in about 90 s. Options: `--seed N`, `--quick --out DIR` (smoke run),
`--from-json docs/results/results.json` (re-render figures and tables without re-running).
Each measured point is validated with z = (mean − theory)/(sd/√trials).

## Running individual sweeps

```
python3.12 dev.py experiment channel_sweeps            # macOS
py -3.12 dev.py experiment channel_sweeps              # Windows
python3.12 dev.py experiment channel_sweeps --seed 7 --trials 50 --n-qubits 8192 --backend qiskit
```

Output: `backend/experiments/output/<name>.json` (git-ignored; regenerate anytime).
Each file embeds its full configuration: root seed, trials, qubit count, channel
parameters, backend and whether it was mathematically modelled or circuit-simulated.

## Reproducibility

- One root seed per sweep. `numpy.random.SeedSequence(seed).spawn(values × trials)`
  gives each (value, trial) an independent child stream.
- Same seed + same configuration ⇒ identical output on any machine.
- **Common random numbers:** sweeps sharing a root seed reuse the same child streams at the
  same row index. Alice's/Bob's random choices therefore coincide across sweeps (visible
  as identical sifted-key lengths per row), so cross-sweep differences reflect the swept
  parameter rather than sampling luck. This is a variance-reduction design, not a bug.

## Statistics reported per point

mean, sample standard deviation (ddof = 1), min and max over trials, for QBER, sifted-key
length, sifting ratio and Eve's known-bit fraction, alongside the closed-form expected QBER
from `docs/quantum-assumptions.md`.

## QBER definition by phase

- Phase 3: *true* sifted-key error rate — full comparison of Alice's and Bob's sifted keys,
  only possible inside a simulator. Used to validate the channel model.
- Phase 4 onward: *estimated* QBER from a randomly disclosed and discarded test sample, as
  real parties would do. `key_acceptance` reports both, plus their difference
  (`estimation_error`), so estimation accuracy can be studied.

## Experiments

| Script | Sweeps | Purpose |
|--------|--------|---------|
| `channel_sweeps` | Eve probability 0–1; depolarizing noise 0–0.5; bit-phase-flip noise 0–0.5; qubit count 256–16,384 | Eve vs QBER, noise vs QBER, qubits vs sifted length |
| `key_acceptance` | Full pipeline vs Eve probability 0–1, depolarizing 0–0.3, bit-phase flip 0–0.15 (8,192 qubits, 30 trials) | Acceptance rate, abort reasons, estimated vs true QBER, final key length, key agreement |
