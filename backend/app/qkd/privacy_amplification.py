"""Toeplitz hashing for privacy amplification (and key verification).

A binary Toeplitz matrix T (m x n) is constant along diagonals, so it is fixed by
n + m - 1 random seed bits: T[i, j] = seed[i - j + n - 1]. The family
{x -> T x mod 2} is 2-universal (Carter-Wegman; Krawczyk 1994): for x != y,
Pr_seed[T x = T y] = 2^-m. The leftover hash lemma then lets Alice and Bob
compress a partially-secret string into a shorter, nearly uniform key.

The seed is chosen by Alice and announced publicly — Eve may know it.

T x equals a slice of the linear convolution seed * x, computed here with an FFT.
Integer sums are at most n, far below float64's exact-integer range, so rounding
recovers them exactly.
"""

import math
from dataclasses import dataclass

import numpy as np


def toeplitz_matrix(seed: np.ndarray, n: int, m: int) -> np.ndarray:
    """Explicit m x n matrix — for teaching and tests; use ``toeplitz_hash`` for real sizes."""
    _check_seed(seed, n, m)
    i = np.arange(m)[:, None]
    j = np.arange(n)[None, :]
    return seed[i - j + n - 1].astype(np.uint8)


def toeplitz_hash(key: np.ndarray, seed: np.ndarray, m: int) -> np.ndarray:
    """Return T(seed) @ key mod 2 as m uint8 bits."""
    n = int(key.size)
    _check_seed(seed, n, m)
    if m == 0:
        return np.zeros(0, dtype=np.uint8)
    full_len = seed.size + n - 1
    size = 1 << (full_len - 1).bit_length()
    conv = np.fft.irfft(
        np.fft.rfft(seed.astype(np.float64), size) * np.fft.rfft(key.astype(np.float64), size),
        size,
    )
    window = np.rint(conv[n - 1:n - 1 + m]).astype(np.int64)
    return (window & 1).astype(np.uint8)


def random_seed(n: int, m: int, rng: np.random.Generator) -> np.ndarray:
    return rng.integers(0, 2, size=n + m - 1, dtype=np.uint8)


def _check_seed(seed: np.ndarray, n: int, m: int) -> None:
    if n < 1 or m < 0:
        raise ValueError("need n >= 1 and m >= 0")
    if seed.size != n + m - 1:
        raise ValueError(f"Toeplitz seed must have n + m - 1 = {n + m - 1} bits, got {seed.size}")


def binary_entropy(p: float) -> float:
    if p <= 0.0 or p >= 1.0:
        return 0.0
    return -p * math.log2(p) - (1 - p) * math.log2(1 - p)


@dataclass(frozen=True)
class KeyLengthBudget:
    input_bits: int
    eve_information_bits: float   # n * h(qber_upper): bound on Eve's info from the quantum phase
    reconciliation_leak_bits: int
    verification_leak_bits: int
    security_margin_bits: float   # 2 log2(1/epsilon_pa) from the leftover hash lemma
    output_bits: int


def secure_key_length(
    n: int,
    qber_upper: float,
    reconciliation_leak: int,
    verification_leak: int,
    epsilon_pa: float,
) -> KeyLengthBudget:
    """Illustrative final-key length (Shor-Preskill-style, asymptotic-inspired).

    m = floor( n (1 - h(e_U)) - leak_EC - leak_verify - 2 log2(1/eps_PA) ), floored at 0.

    Assumes the phase-error rate equals the bit-error rate (symmetric BB84 channel)
    and uses the upper confidence bound e_U from parameter estimation. Leakage terms
    are counted from the actual reconciliation transcript, not estimated.
    """
    eve = n * binary_entropy(min(qber_upper, 0.5)) if qber_upper < 0.5 else float(n)
    margin = 2 * math.log2(1 / epsilon_pa)
    raw = n - eve - reconciliation_leak - verification_leak - margin
    return KeyLengthBudget(
        input_bits=n,
        eve_information_bits=eve,
        reconciliation_leak_bits=reconciliation_leak,
        verification_leak_bits=verification_leak,
        security_margin_bits=margin,
        output_bits=max(0, math.floor(raw)),
    )
