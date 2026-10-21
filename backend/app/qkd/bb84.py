"""BB84 protocol engine.

Pipeline:
    alice_prepare -> bob chooses bases -> channel.transmit (Eve, noise) -> bob_measure -> sift

Bob's basis choices are independent of everything on the channel, so drawing them
before transmission is equivalent to drawing them on arrival, and keeps ideal-channel
runs identical to Phase 2 for the same seed.

Randomness: every random choice comes from one ``numpy.random.Generator``. A seed makes
runs reproducible for experiments. NumPy's PCG64 is NOT a cryptographic or quantum RNG;
that is acceptable for an educational simulation and is documented as a limitation.

Key material in a ``BB84Run`` lives only in memory. Nothing here persists it.
"""

from dataclasses import dataclass, field

import numpy as np

from app.qkd.backends import NumpyBackend, QuantumBackend
from app.qkd.bb84_types import PreparedStates
from app.qkd.channel import ChannelConfig, ChannelOutcome, expected_qber, transmit
from app.qkd.states import STATE_LABELS, Basis

__all__ = [
    "BB84Run", "PreparedStates", "SiftResult", "alice_prepare", "bob_measure",
    "choose_bases", "make_rng", "run_bb84", "sift",
]


def make_rng(seed: int | None = None) -> np.random.Generator:
    """Seeded generator for reproducible runs; ``None`` draws entropy from the OS."""
    return np.random.default_rng(seed)


@dataclass(frozen=True)
class SiftResult:
    mask: np.ndarray  # True where Alice's and Bob's bases matched
    alice_key: np.ndarray
    bob_key: np.ndarray

    @property
    def indices(self) -> np.ndarray:
        return np.flatnonzero(self.mask)

    def __len__(self) -> int:
        return int(self.alice_key.size)


@dataclass(frozen=True)
class BB84Run:
    alice_bits: np.ndarray
    alice_bases: np.ndarray
    bob_bases: np.ndarray
    bob_results: np.ndarray
    sift: SiftResult
    channel: ChannelOutcome
    backend_name: str
    simulation_kind: str
    seed: int | None = field(default=None)

    @property
    def n_qubits(self) -> int:
        return int(self.alice_bits.size)

    def metrics(self) -> dict:
        """Aggregate statistics. Safe to log/persist: contains no key bits.

        ``true_sifted_errors`` / ``true_sifted_error_rate`` compare the FULL sifted keys.
        Only a simulator can know these; real Alice and Bob must estimate QBER from a
        disclosed sample (Phase 4). They are reported for validating the simulation.

        ``eve_known_sifted_bits``: sifted positions where Eve intercepted in the
        correct basis, so her measured bit equals Alice's bit with certainty.
        """
        n = self.n_qubits
        sifted = len(self.sift)
        errors = int(np.count_nonzero(self.sift.alice_key != self.sift.bob_key))
        cfg = self.channel.config
        eve = self.channel.eve
        sift_mask = self.sift.mask
        eve_known = int(np.count_nonzero(
            sift_mask & eve.intercepted & (eve.bases == self.alice_bases)
        ))
        return {
            "n_qubits": n,
            "basis_matches": sifted,
            "sifting_ratio": sifted / n if n else 0.0,
            "sifted_key_length": sifted,
            "true_sifted_errors": errors,
            "true_sifted_error_rate": errors / sifted if sifted else 0.0,
            "expected_qber": expected_qber(cfg),
            "eve_probability": cfg.eve_probability,
            "channel_noise": cfg.noise,
            "noise_model": cfg.noise_model,
            "eve_intercepted": int(np.count_nonzero(eve.intercepted)),
            "eve_known_sifted_bits": eve_known,
            "eve_known_sifted_fraction": eve_known / sifted if sifted else 0.0,
            "noise_affected_qubits": int(np.count_nonzero(self.channel.noise_mask)),
            "backend": self.backend_name,
            "simulation_kind": self.simulation_kind,
            "seed": self.seed,
        }

    def trace(self, limit: int) -> list[dict]:
        """Per-qubit walkthrough of the first ``limit`` pulses for the QKD Laboratory UI."""
        eve = self.channel.eve
        rows = []
        for i in range(min(limit, self.n_qubits)):
            bit, a_basis = int(self.alice_bits[i]), Basis(int(self.alice_bases[i]))
            b_basis = Basis(int(self.bob_bases[i]))
            intercepted = bool(eve.intercepted[i])
            match = bool(self.sift.mask[i])
            rows.append({
                "index": i,
                "alice_bit": bit,
                "alice_basis": a_basis.name,
                "state": STATE_LABELS[(bit, a_basis)],
                "eve_intercepted": intercepted,
                "eve_basis": Basis(int(eve.bases[i])).name if intercepted else None,
                "eve_result": int(eve.results[i]) if intercepted else None,
                "noise_applied": bool(self.channel.noise_mask[i]),
                "bob_basis": b_basis.name,
                "bob_result": int(self.bob_results[i]),
                "bases_match": match,
                "error": match and int(self.bob_results[i]) != bit,
            })
        return rows


def alice_prepare(n_qubits: int, rng: np.random.Generator) -> PreparedStates:
    """Alice draws uniform random bits and independent uniform random Z/X bases."""
    if n_qubits < 1:
        raise ValueError("n_qubits must be at least 1")
    bits = rng.integers(0, 2, size=n_qubits, dtype=np.uint8)
    bases = rng.integers(0, 2, size=n_qubits, dtype=np.uint8)
    return PreparedStates(bits=bits, bases=bases)


def choose_bases(n_qubits: int, rng: np.random.Generator) -> np.ndarray:
    """Independent uniform Z/X basis choices (used by Bob)."""
    return rng.integers(0, 2, size=n_qubits, dtype=np.uint8)


def bob_measure(
    states: PreparedStates,
    bob_bases: np.ndarray,
    rng: np.random.Generator,
    backend: QuantumBackend,
) -> np.ndarray:
    return backend.measure(states.bits, states.bases, bob_bases, rng)


def sift(
    alice_bits: np.ndarray,
    alice_bases: np.ndarray,
    bob_bases: np.ndarray,
    bob_results: np.ndarray,
) -> SiftResult:
    """Public basis comparison over the (assumed authenticated) classical channel.

    Only bases are compared — never bit values. Positions with mismatched bases are
    discarded by both parties.
    """
    mask = alice_bases == bob_bases
    return SiftResult(mask=mask, alice_key=alice_bits[mask], bob_key=bob_results[mask])


def run_bb84(
    n_qubits: int,
    rng: np.random.Generator | None = None,
    backend: QuantumBackend | None = None,
    seed: int | None = None,
    channel: ChannelConfig | None = None,
) -> BB84Run:
    """One BB84 session: prepare, transmit (optionally through Eve and noise), measure, sift.

    Pass either ``rng`` (caller-managed generator) or ``seed`` (convenience).
    """
    if rng is not None and seed is not None:
        raise ValueError("pass rng or seed, not both")
    rng = rng if rng is not None else make_rng(seed)
    backend = backend if backend is not None else NumpyBackend()
    channel = channel if channel is not None else ChannelConfig()

    sent = alice_prepare(n_qubits, rng)
    bob_bases = choose_bases(n_qubits, rng)
    outcome = transmit(sent, channel, rng, backend)
    bob_results = bob_measure(outcome.delivered, bob_bases, rng, backend)
    sifted = sift(sent.bits, sent.bases, bob_bases, bob_results)

    return BB84Run(
        alice_bits=sent.bits,
        alice_bases=sent.bases,
        bob_bases=bob_bases,
        bob_results=bob_results,
        sift=sifted,
        channel=outcome,
        backend_name=backend.name,
        simulation_kind=backend.simulation_kind,
        seed=seed,
    )
