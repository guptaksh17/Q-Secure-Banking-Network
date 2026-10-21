"""Parameter estimation: disclose a random test sample, estimate QBER, discard the sample.

Alice picks sample positions uniformly at random (without replacement) from the sifted
key and announces them; both parties reveal their bits there over the authenticated
classical channel. Revealed bits are known to Eve, so they are removed from the key.

Two numbers come out:
- ``qber_estimate``  — errors / sample_size (point estimate, used for the abort rule).
- ``qber_upper``     — one-sided Clopper–Pearson upper bound at confidence 1 - epsilon,
                       used when sizing privacy amplification so a lucky small sample
                       cannot overstate secrecy.

The binomial bound assumes errors are i.i.d. across positions. That holds for this
simulator's channel (Eve and noise act independently per qubit) and corresponds to
collective-attack-style analyses; it is not a general finite-key proof.
"""

import math
from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class ParameterEstimate:
    sifted_length: int
    sample_size: int
    sample_errors: int
    qber_estimate: float
    qber_upper: float
    confidence: float
    sample_mask: np.ndarray  # over sifted positions; True = disclosed and discarded
    alice_remaining: np.ndarray
    bob_remaining: np.ndarray

    @property
    def remaining_length(self) -> int:
        return int(self.alice_remaining.size)


def _binomial_cdf(k: int, n: int, p: float) -> float:
    """P(X <= k) for X ~ Binomial(n, p), via log-space terms (stable for large n)."""
    if p <= 0.0:
        return 1.0
    if p >= 1.0:
        return 1.0 if k >= n else 0.0
    i = np.arange(k + 1)
    log_terms = (
        math.lgamma(n + 1)
        - np.array([math.lgamma(x + 1) + math.lgamma(n - x + 1) for x in i])
        + i * math.log(p)
        + (n - i) * math.log1p(-p)
    )
    peak = log_terms.max()
    return float(min(1.0, math.exp(peak) * np.exp(log_terms - peak).sum()))


def clopper_pearson_upper(errors: int, n: int, epsilon: float) -> float:
    """Smallest p with P(X <= errors | n, p) <= epsilon (one-sided exact binomial bound)."""
    if n <= 0:
        return 1.0
    if not 0 <= errors <= n:
        raise ValueError("errors must be in [0, n]")
    if errors == n:
        return 1.0
    lo, hi = errors / n, 1.0
    for _ in range(80):  # bisection to ~1e-24 width
        mid = (lo + hi) / 2
        if _binomial_cdf(errors, n, mid) > epsilon:
            lo = mid
        else:
            hi = mid
    return hi


def estimate_qber(
    alice_key: np.ndarray,
    bob_key: np.ndarray,
    sample_fraction: float,
    rng: np.random.Generator,
    epsilon: float = 1e-3,
) -> ParameterEstimate:
    if alice_key.shape != bob_key.shape:
        raise ValueError("sifted keys must have equal length")
    if not 0.0 < sample_fraction < 1.0:
        raise ValueError("sample_fraction must be in (0, 1)")
    n = int(alice_key.size)
    k = int(round(sample_fraction * n))

    mask = np.zeros(n, dtype=bool)
    if k:
        mask[rng.choice(n, size=k, replace=False)] = True
    errors = int(np.count_nonzero(alice_key[mask] != bob_key[mask]))

    return ParameterEstimate(
        sifted_length=n,
        sample_size=k,
        sample_errors=errors,
        qber_estimate=errors / k if k else 0.0,
        qber_upper=clopper_pearson_upper(errors, k, epsilon),
        confidence=1.0 - epsilon,
        sample_mask=mask,
        alice_remaining=alice_key[~mask],
        bob_remaining=bob_key[~mask],
    )
