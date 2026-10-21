"""Quantum channel between Alice and Bob: optional Eve, then optional noise.

Topology (documented modelling choice):

    Alice --> [Eve: intercept-and-resend] --> [noisy channel] --> Bob

Both stages map ``PreparedStates`` to ``PreparedStates``, i.e. every state on the
wire is always one of the four BB84 states (or a classical mixture of them).

Eve — intercept-and-resend
    Each qubit is intercepted independently with probability ``eve_probability``.
    Eve picks a uniform random basis, measures through the same ``QuantumBackend``
    as Bob (so with the Qiskit backend her measurement is circuit-simulated), and
    resends the BB84 state matching her outcome in her basis.

Noise — two standard single-qubit channels, applied independently per qubit:
    "depolarizing"    rho -> (1-p) rho + p I/2.  I/2 equals the uniform mixture of
                      the four BB84 states, so with probability p the state is
                      replaced by a random bit in a random basis. Exact, not an
                      approximation. Sifted-key error contribution: p/2.
    "bit_phase_flip"  rho -> (1-q) rho + q Y rho Y.  Y maps |0><->|1> and |+><->|->
                      (up to global phase), so the bit flips and the basis is kept.
                      Sifted-key error contribution: q (same in both bases).

Noise is applied at the state level for both backends; the Qiskit backend's
circuits cover preparation and measurement. Because the channels above act on
BB84 states exactly as described, circuit-level noise would give the same
outcome distribution.

Stages draw no random numbers when their parameter is 0, so an ideal channel
reproduces Phase 2 runs bit-for-bit for the same seed.
"""

from dataclasses import dataclass, field
from typing import Literal

import numpy as np

from app.qkd.backends import QuantumBackend
from app.qkd.bb84_types import PreparedStates

NoiseModel = Literal["depolarizing", "bit_phase_flip"]
NOISE_MODELS: tuple[NoiseModel, ...] = ("depolarizing", "bit_phase_flip")


@dataclass(frozen=True)
class ChannelConfig:
    eve_probability: float = 0.0
    noise: float = 0.0
    noise_model: NoiseModel = "depolarizing"

    def __post_init__(self):
        for name in ("eve_probability", "noise"):
            value = getattr(self, name)
            if not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be in [0, 1], got {value}")
        if self.noise_model not in NOISE_MODELS:
            raise ValueError(f"noise_model must be one of {NOISE_MODELS}")

    @property
    def is_ideal(self) -> bool:
        return self.eve_probability == 0.0 and self.noise == 0.0


@dataclass(frozen=True)
class EveRecord:
    """What Eve did. ``bases``/``results`` are meaningful only where ``intercepted``."""

    intercepted: np.ndarray  # bool
    bases: np.ndarray        # uint8
    results: np.ndarray      # uint8


@dataclass(frozen=True)
class ChannelOutcome:
    delivered: PreparedStates  # states that reach Bob
    eve: EveRecord
    noise_mask: np.ndarray     # bool: noise channel acted on this qubit
    config: ChannelConfig = field(default_factory=ChannelConfig)


def intercept_resend(
    states: PreparedStates,
    probability: float,
    rng: np.random.Generator,
    backend: QuantumBackend,
) -> tuple[PreparedStates, EveRecord]:
    n = len(states)
    intercepted = np.zeros(n, dtype=bool)
    eve_bases = np.zeros(n, dtype=np.uint8)
    eve_results = np.zeros(n, dtype=np.uint8)
    if probability == 0.0:
        return states, EveRecord(intercepted, eve_bases, eve_results)

    intercepted = rng.random(n) < probability
    idx = np.flatnonzero(intercepted)
    if idx.size:
        eve_bases[idx] = rng.integers(0, 2, size=idx.size, dtype=np.uint8)
        eve_results[idx] = backend.measure(states.bits[idx], states.bases[idx], eve_bases[idx], rng)

    bits, bases = states.bits.copy(), states.bases.copy()
    bits[idx], bases[idx] = eve_results[idx], eve_bases[idx]  # resend what she measured
    return PreparedStates(bits=bits, bases=bases), EveRecord(intercepted, eve_bases, eve_results)


def apply_noise(
    states: PreparedStates,
    noise: float,
    model: NoiseModel,
    rng: np.random.Generator,
) -> tuple[PreparedStates, np.ndarray]:
    n = len(states)
    if noise == 0.0:
        return states, np.zeros(n, dtype=bool)

    mask = rng.random(n) < noise
    idx = np.flatnonzero(mask)
    bits, bases = states.bits.copy(), states.bases.copy()
    if model == "depolarizing":
        bits[idx] = rng.integers(0, 2, size=idx.size, dtype=np.uint8)
        bases[idx] = rng.integers(0, 2, size=idx.size, dtype=np.uint8)
    elif model == "bit_phase_flip":
        bits[idx] ^= 1
    else:  # pragma: no cover - guarded by ChannelConfig
        raise ValueError(f"unknown noise model {model!r}")
    return PreparedStates(bits=bits, bases=bases), mask


def transmit(
    states: PreparedStates,
    config: ChannelConfig,
    rng: np.random.Generator,
    backend: QuantumBackend,
) -> ChannelOutcome:
    after_eve, eve = intercept_resend(states, config.eve_probability, rng, backend)
    delivered, noise_mask = apply_noise(after_eve, config.noise, config.noise_model, rng)
    return ChannelOutcome(delivered=delivered, eve=eve, noise_mask=noise_mask, config=config)


def expected_qber(config: ChannelConfig) -> float:
    """Theoretical sifted-key QBER for this channel (infinite-key limit).

    Eve: on a sifted position she guesses the wrong basis w.p. 1/2, after which Bob's
    result is random, so e_eve = p_eve / 4.
    Depolarizing p after Eve: QBER = (1 - p) e_eve + p / 2.
    Bit-phase flip q after Eve: an error survives iff exactly one of {Eve error, flip}
    happens: QBER = e_eve (1 - q) + (1 - e_eve) q.
    """
    e_eve = config.eve_probability / 4.0
    p = config.noise
    if config.noise_model == "depolarizing":
        return (1.0 - p) * e_eve + p / 2.0
    return e_eve * (1.0 - p) + (1.0 - e_eve) * p
