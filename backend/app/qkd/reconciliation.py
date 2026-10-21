"""Cascade-inspired error reconciliation (Brassard & Salvail, 1993) with leakage accounting.

Alice's key is the reference; Bob corrects his copy. Per pass i:

1. Both apply a public permutation (identity on pass 0, random afterwards) and split
   the key into blocks of size k_i = k_1 * 2^i, with k_1 ~ 0.73 / QBER.
2. Alice announces every block parity (1 leaked bit per block).
3. For each block whose parity differs, BINARY search: Alice announces the parity of
   the first half (1 leaked bit per step) until a single erroneous bit is isolated;
   Bob flips it.
4. Cascade step: that flip changes the parity of the block containing the bit in every
   earlier pass. Any such block now has odd disagreement and is binary-searched too
   (its parity was already announced, so only the search steps leak).

After all passes, Alice and Bob compare a fresh 64-bit Toeplitz hash of their keys
(collision probability 2^-64 for differing keys). A mismatch aborts the session.

Every announced bit is counted in ``leaked_bits`` and later subtracted during privacy
amplification. Simplifications vs. production Cascade: fixed doubling block sizes,
no adaptive pass count, and no interactive optimisation (e.g. BICONF, Yanetani's
improvements). The *protocol messages* are simulated in-process: parities are computed
from both keys directly, but only Alice's announced parities are counted as leakage.
"""

import math
from dataclasses import dataclass, field

import numpy as np

from app.qkd.privacy_amplification import random_seed, toeplitz_hash

MIN_QBER_FOR_BLOCK_SIZE = 0.01  # avoids enormous first blocks when the estimate is 0


@dataclass(frozen=True)
class ReconciliationResult:
    bob_corrected: np.ndarray
    leaked_bits: int            # parity bits disclosed during Cascade
    verification_bits: int      # hash bits disclosed during verification
    errors_corrected: int
    block_sizes: list[int] = field(default_factory=list)
    verified: bool = False

    @property
    def total_leaked_bits(self) -> int:
        return self.leaked_bits + self.verification_bits


def initial_block_size(qber: float, n: int) -> int:
    q = max(qber, MIN_QBER_FOR_BLOCK_SIZE)
    return int(min(n, max(4, math.ceil(0.73 / q))))


def _parity(key: np.ndarray, idx: np.ndarray) -> int:
    return int(key[idx].sum() & 1)


class _Cascade:
    def __init__(self, alice: np.ndarray, bob: np.ndarray, rng: np.random.Generator, k1: int):
        self.alice = alice
        self.bob = bob.copy()
        self.n = int(alice.size)
        self.rng = rng
        self.k1 = k1
        self.perms: list[np.ndarray] = []
        self.inverse: list[np.ndarray] = []
        self.sizes: list[int] = []
        self.leaked = 0
        self.corrected = 0

    def _block(self, p: int, b: int) -> np.ndarray:
        s = self.sizes[p]
        return self.perms[p][b * s:(b + 1) * s]

    def _block_of(self, p: int, pos: int) -> int:
        return int(self.inverse[p][pos]) // self.sizes[p]

    def _binary_search(self, idx: np.ndarray) -> int:
        """Precondition: idx has odd disagreement. Returns one erroneous position."""
        while idx.size > 1:
            half = idx[: idx.size // 2]
            self.leaked += 1  # Alice announces parity of the first half
            if _parity(self.alice, half) != _parity(self.bob, half):
                idx = half
            else:
                idx = idx[idx.size // 2:]
        return int(idx[0])

    def _correct(self, pos: int, upto_pass: int) -> None:
        self.bob[pos] ^= 1
        self.corrected += 1
        queue = [(p, self._block_of(p, pos)) for p in range(upto_pass + 1)]
        while queue:
            p, b = queue.pop()
            idx = self._block(p, b)
            # Alice's parity for this block was announced when pass p began.
            if _parity(self.alice, idx) != _parity(self.bob, idx):
                new = self._binary_search(idx)
                self.bob[new] ^= 1
                self.corrected += 1
                queue.extend((q, self._block_of(q, new)) for q in range(upto_pass + 1) if q != p)

    def run(self, passes: int) -> None:
        for p in range(passes):
            perm = np.arange(self.n) if p == 0 else self.rng.permutation(self.n)
            inverse = np.empty_like(perm)
            inverse[perm] = np.arange(self.n)
            self.perms.append(perm)
            self.inverse.append(inverse)
            self.sizes.append(min(self.n, self.k1 * 2**p))

            n_blocks = math.ceil(self.n / self.sizes[p])
            self.leaked += n_blocks  # Alice announces all block parities for this pass
            for b in range(n_blocks):
                idx = self._block(p, b)
                if _parity(self.alice, idx) != _parity(self.bob, idx):
                    self._correct(self._binary_search(idx), p)


def keys_match_by_hash(
    alice: np.ndarray, bob: np.ndarray, bits: int, rng: np.random.Generator
) -> bool:
    """Compare ``bits``-bit Toeplitz hashes under a fresh public seed."""
    seed = random_seed(int(alice.size), bits, rng)
    return bool(np.array_equal(toeplitz_hash(alice, seed, bits), toeplitz_hash(bob, seed, bits)))


def cascade_reconcile(
    alice_key: np.ndarray,
    bob_key: np.ndarray,
    qber_estimate: float,
    rng: np.random.Generator,
    passes: int = 4,
    verification_bits: int = 64,
) -> ReconciliationResult:
    if alice_key.shape != bob_key.shape or alice_key.ndim != 1:
        raise ValueError("keys must be 1-D arrays of equal length")
    if alice_key.size == 0:
        raise ValueError("cannot reconcile an empty key")
    if passes < 1:
        raise ValueError("passes must be at least 1")

    cascade = _Cascade(alice_key, bob_key, rng, initial_block_size(qber_estimate, alice_key.size))
    cascade.run(passes)
    verified = keys_match_by_hash(alice_key, cascade.bob, verification_bits, rng)
    return ReconciliationResult(
        bob_corrected=cascade.bob,
        leaked_bits=cascade.leaked,
        verification_bits=verification_bits,
        errors_corrected=cascade.corrected,
        block_sizes=list(cascade.sizes),
        verified=verified,
    )
