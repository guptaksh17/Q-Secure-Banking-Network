"""End-to-end key exchange: BB84 -> parameter estimation -> abort decision ->
Cascade reconciliation -> verification -> Toeplitz privacy amplification.

Abort conditions, checked in order:
  SAMPLE_TOO_SMALL         test sample below ``min_sample_size`` (QBER not measurable)
  QBER_ABOVE_THRESHOLD     point-estimate QBER > illustrative threshold
  RECONCILIATION_FAILED    verification hashes differ after Cascade
  INSUFFICIENT_KEY         privacy-amplified length < ``min_final_key_bits``

On abort, no final key is produced. Final keys exist only in memory on the returned
object and are never included in ``metrics()``.

All public random choices (sample positions, Cascade permutations, hash seeds) are drawn
from the session generator and would be announced over the authenticated channel.
"""

from dataclasses import dataclass, replace
from enum import Enum

import numpy as np

from app.qkd.backends import QuantumBackend
from app.qkd.bb84 import BB84Run, make_rng, run_bb84
from app.qkd.channel import ChannelConfig
from app.qkd.estimation import ParameterEstimate, estimate_qber
from app.qkd.privacy_amplification import (
    KeyLengthBudget,
    random_seed,
    secure_key_length,
    toeplitz_hash,
)
from app.qkd.reconciliation import ReconciliationResult, cascade_reconcile


class AbortReason(str, Enum):
    SAMPLE_TOO_SMALL = "sample_too_small"
    QBER_ABOVE_THRESHOLD = "qber_above_threshold"
    RECONCILIATION_FAILED = "reconciliation_failed"
    INSUFFICIENT_KEY = "insufficient_key"


@dataclass(frozen=True)
class ProcessingConfig:
    qber_threshold: float = 0.11          # illustrative, not a universal bound
    sample_fraction: float = 0.25
    min_sample_size: int = 50
    estimation_epsilon: float = 1e-3      # Clopper-Pearson confidence = 1 - epsilon
    cascade_passes: int = 4
    verification_bits: int = 64
    pa_epsilon: float = 1e-10             # leftover-hash-lemma security parameter
    min_final_key_bits: int = 256         # enough to derive one AES-256 key

    def __post_init__(self):
        if not 0.0 < self.qber_threshold < 0.5:
            raise ValueError("qber_threshold must be in (0, 0.5)")
        if not 0.0 < self.sample_fraction < 1.0:
            raise ValueError("sample_fraction must be in (0, 1)")
        if not 0.0 < self.estimation_epsilon < 1.0 or not 0.0 < self.pa_epsilon < 1.0:
            raise ValueError("epsilons must be in (0, 1)")
        if self.min_sample_size < 1 or self.cascade_passes < 1 or self.verification_bits < 1:
            raise ValueError("sizes and pass counts must be positive")
        if self.min_final_key_bits < 1:
            raise ValueError("min_final_key_bits must be positive")


@dataclass(frozen=True)
class KeyExchangeResult:
    bb84: BB84Run
    processing: ProcessingConfig
    estimate: ParameterEstimate
    reconciliation: ReconciliationResult | None
    budget: KeyLengthBudget | None
    abort_reason: AbortReason | None
    alice_final_key: np.ndarray | None  # in memory only
    bob_final_key: np.ndarray | None    # in memory only

    @property
    def accepted(self) -> bool:
        return self.abort_reason is None

    def metrics(self) -> dict:
        """Everything the UI/database may store. Contains no key bits."""
        est, rec, bud = self.estimate, self.reconciliation, self.budget
        out = self.bb84.metrics()
        out.update({
            "accepted": self.accepted,
            "abort_reason": self.abort_reason.value if self.abort_reason else None,
            "qber_threshold": self.processing.qber_threshold,
            "sample_fraction": self.processing.sample_fraction,
            "test_sample_size": est.sample_size,
            "test_sample_errors": est.sample_errors,
            "estimated_qber": est.qber_estimate,
            "qber_upper_bound": est.qber_upper,
            "qber_confidence": est.confidence,
            "remaining_key_length": est.remaining_length,
            "errors_before_reconciliation": int(
                np.count_nonzero(est.alice_remaining != est.bob_remaining)
            ),
            "reconciliation": None if rec is None else {
                "errors_corrected": rec.errors_corrected,
                "parity_bits_leaked": rec.leaked_bits,
                "verification_bits_leaked": rec.verification_bits,
                "block_sizes": rec.block_sizes,
                "verified": rec.verified,
                "residual_errors": int(np.count_nonzero(est.alice_remaining != rec.bob_corrected)),
            },
            "privacy_amplification": None if bud is None else {
                "input_bits": bud.input_bits,
                "eve_information_bits": round(bud.eve_information_bits, 2),
                "reconciliation_leak_bits": bud.reconciliation_leak_bits,
                "verification_leak_bits": bud.verification_leak_bits,
                "security_margin_bits": round(bud.security_margin_bits, 2),
                "output_bits": bud.output_bits,
                "method": "Toeplitz universal hashing",
            },
            "final_key_length": 0 if self.alice_final_key is None else int(self.alice_final_key.size),
            "final_keys_match": None if self.alice_final_key is None
            else bool(np.array_equal(self.alice_final_key, self.bob_final_key)),
        })
        return out


def process_key(
    bb84: BB84Run, processing: ProcessingConfig, rng: np.random.Generator
) -> KeyExchangeResult:
    def finish(reason, estimate, rec=None, budget=None, keys=(None, None)):
        return KeyExchangeResult(bb84, processing, estimate, rec, budget, reason, *keys)

    est = estimate_qber(
        bb84.sift.alice_key, bb84.sift.bob_key,
        processing.sample_fraction, rng, processing.estimation_epsilon,
    )
    if est.sample_size < processing.min_sample_size or est.remaining_length == 0:
        return finish(AbortReason.SAMPLE_TOO_SMALL, est)
    if est.qber_estimate > processing.qber_threshold:
        return finish(AbortReason.QBER_ABOVE_THRESHOLD, est)

    rec = cascade_reconcile(
        est.alice_remaining, est.bob_remaining, est.qber_estimate, rng,
        passes=processing.cascade_passes, verification_bits=processing.verification_bits,
    )
    if not rec.verified:
        return finish(AbortReason.RECONCILIATION_FAILED, est, rec)

    budget = secure_key_length(
        est.remaining_length, est.qber_upper, rec.leaked_bits, rec.verification_bits,
        processing.pa_epsilon,
    )
    if budget.output_bits < processing.min_final_key_bits:
        return finish(AbortReason.INSUFFICIENT_KEY, est, rec, budget)

    seed = random_seed(est.remaining_length, budget.output_bits, rng)
    alice_final = toeplitz_hash(est.alice_remaining, seed, budget.output_bits)
    bob_final = toeplitz_hash(rec.bob_corrected, seed, budget.output_bits)
    return finish(None, est, rec, budget, (alice_final, bob_final))


def run_key_exchange(
    n_qubits: int,
    channel: ChannelConfig | None = None,
    processing: ProcessingConfig | None = None,
    rng: np.random.Generator | None = None,
    seed: int | None = None,
    backend: QuantumBackend | None = None,
) -> KeyExchangeResult:
    if rng is not None and seed is not None:
        raise ValueError("pass rng or seed, not both")
    rng = rng if rng is not None else make_rng(seed)
    bb84 = run_bb84(n_qubits, rng=rng, backend=backend, channel=channel)
    if seed is not None:  # record the seed on the BB84 run for reproducibility
        bb84 = replace(bb84, seed=seed)
    return process_key(bb84, processing or ProcessingConfig(), rng)
