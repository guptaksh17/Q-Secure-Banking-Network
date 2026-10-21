"""Quantum measurement backends.

Both backends answer the same question: given BB84 states (bit, basis) arriving at a
receiver who measures each in a chosen basis, what outcomes are observed?

- ``NumpyBackend``  — *mathematically modelled*: samples each outcome from the Born-rule
  probability table in ``states.PROB_ONE``. Fast; suitable for large experiments.
- ``QiskitBackend`` — *circuit-simulated*: builds circuits (X for bit 1, H for X-basis
  preparation, H before a Z measurement for X-basis measurement) and executes them on
  Qiskit Aer. Slower; demonstrates the gate-level procedure.

Neither runs on quantum hardware. Every receiver in the protocol (Bob, and Eve in
Phase 3) measures through one of these backends.
"""

from typing import Literal, Protocol

import numpy as np

from app.qkd.states import PROB_ONE, Basis

SimulationKind = Literal["mathematical_model", "circuit_simulation"]


class QuantumBackend(Protocol):
    name: str
    simulation_kind: SimulationKind

    def measure(
        self,
        bits: np.ndarray,
        prep_bases: np.ndarray,
        meas_bases: np.ndarray,
        rng: np.random.Generator,
    ) -> np.ndarray:
        """Measure states |bits, prep_bases> in ``meas_bases``; returns uint8 outcomes."""
        ...


def _validate(bits: np.ndarray, prep_bases: np.ndarray, meas_bases: np.ndarray) -> None:
    if not (bits.shape == prep_bases.shape == meas_bases.shape) or bits.ndim != 1:
        raise ValueError("bits, prep_bases and meas_bases must be 1-D arrays of equal length")
    for name, arr in (("bits", bits), ("prep_bases", prep_bases), ("meas_bases", meas_bases)):
        if arr.size and not np.isin(arr, (0, 1)).all():
            raise ValueError(f"{name} must contain only 0/1")


class NumpyBackend:
    name = "numpy"
    simulation_kind: SimulationKind = "mathematical_model"

    def measure(self, bits, prep_bases, meas_bases, rng):
        _validate(bits, prep_bases, meas_bases)
        p_one = PROB_ONE[prep_bases, bits, meas_bases]
        # rng.random() is in [0, 1): p=0 never yields 1, p=1 always does.
        return (rng.random(bits.size) < p_one).astype(np.uint8)


class QiskitBackend:
    """Executes one Aer job per chunk of qubits.

    All gates are Clifford (X, H, measure) and qubits are never entangled, so Aer's
    stabilizer method simulates thousands of qubits per circuit exactly and cheaply.
    """

    name = "qiskit"
    simulation_kind: SimulationKind = "circuit_simulation"

    def __init__(self, chunk_size: int = 1000):
        try:
            from qiskit import QuantumCircuit
            from qiskit_aer import AerSimulator
        except ImportError as exc:  # pragma: no cover - depends on environment
            raise RuntimeError(
                "Qiskit backend requested but qiskit/qiskit-aer are not installed"
            ) from exc
        self._circuit_cls = QuantumCircuit
        self._simulator = AerSimulator(method="stabilizer")
        self.chunk_size = chunk_size

    def build_circuit(self, bits, prep_bases, meas_bases):
        """One circuit, one qubit per BB84 pulse. Exposed for inspection/teaching."""
        n = bits.size
        qc = self._circuit_cls(n, n)
        for i in range(n):
            if bits[i] == 1:
                qc.x(i)  # |0> -> |1>
            if prep_bases[i] == Basis.X:
                qc.h(i)  # |0>/|1> -> |+>/|->
            if meas_bases[i] == Basis.X:
                qc.h(i)  # rotate X basis onto Z for a computational-basis measurement
            qc.measure(i, i)
        return qc

    def measure(self, bits, prep_bases, meas_bases, rng):
        _validate(bits, prep_bases, meas_bases)
        out = np.empty(bits.size, dtype=np.uint8)
        for start in range(0, bits.size, self.chunk_size):
            stop = min(start + self.chunk_size, bits.size)
            qc = self.build_circuit(bits[start:stop], prep_bases[start:stop], meas_bases[start:stop])
            # Aer's seed is drawn from our generator so whole runs stay reproducible.
            seed = int(rng.integers(0, 2**31 - 1))
            result = self._simulator.run(qc, shots=1, memory=True, seed_simulator=seed).result()
            bitstring = result.get_memory()[0]
            # Qiskit prints classical bit 0 as the rightmost character.
            out[start:stop] = np.frombuffer(bitstring[::-1].encode("ascii"), dtype=np.uint8) - ord("0")
        return out


def get_backend(name: str) -> QuantumBackend:
    if name == "numpy":
        return NumpyBackend()
    if name == "qiskit":
        return QiskitBackend()
    raise ValueError(f"unknown quantum backend {name!r}; expected 'numpy' or 'qiskit'")
