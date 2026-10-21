"""Reproducible parameter sweeps over the BB84 simulation.

Every data point comes from actually running the simulator — nothing is
interpolated or hand-entered. One root seed fixes the whole sweep: a
``numpy.random.SeedSequence`` spawns an independent child stream per
(value, trial), so results are identical on every machine and changing the
number of trials at one point does not alter any other point's streams.

``sweep`` reports the *true* sifted-key error rate (full-key comparison, available
only in simulation). ``key_exchange_sweep`` runs the full Phase 4 pipeline and reports
the sample-based estimate alongside the true value, plus acceptance and key length.
"""

from dataclasses import asdict, replace
from typing import Literal

import numpy as np

from app.qkd.backends import NumpyBackend, QuantumBackend
from app.qkd.bb84 import run_bb84
from app.qkd.channel import ChannelConfig, expected_qber
from app.qkd.key_exchange import ProcessingConfig, run_key_exchange

SweepParameter = Literal["eve_probability", "noise", "n_qubits"]


def run_trials(
    n_qubits: int,
    channel: ChannelConfig,
    seeds: list[np.random.SeedSequence],
    backend: QuantumBackend,
) -> list[dict]:
    return [
        run_bb84(n_qubits, rng=np.random.default_rng(ss), backend=backend, channel=channel).metrics()
        for ss in seeds
    ]


def _summarise(values: np.ndarray) -> dict:
    return {
        "mean": float(values.mean()),
        "std": float(values.std(ddof=1)) if values.size > 1 else 0.0,
        "min": float(values.min()),
        "max": float(values.max()),
    }


def sweep(
    parameter: SweepParameter,
    values: list[float],
    *,
    n_qubits: int = 2048,
    trials: int = 20,
    seed: int = 2024,
    base_channel: ChannelConfig | None = None,
    backend: QuantumBackend | None = None,
) -> dict:
    """Run ``trials`` independent sessions at each value of ``parameter``.

    Returns a JSON-serialisable dict with the full configuration (for
    reproducibility) and one summary row per value.
    """
    if trials < 1:
        raise ValueError("trials must be at least 1")
    if not values:
        raise ValueError("values must not be empty")
    base_channel = base_channel or ChannelConfig()
    backend = backend or NumpyBackend()
    children = np.random.SeedSequence(seed).spawn(len(values) * trials)

    points = []
    for i, value in enumerate(values):
        if parameter == "n_qubits":
            n, channel = int(value), base_channel
        elif parameter in ("eve_probability", "noise"):
            n, channel = n_qubits, replace(base_channel, **{parameter: float(value)})
        else:
            raise ValueError(f"unknown sweep parameter {parameter!r}")

        runs = run_trials(n, channel, children[i * trials:(i + 1) * trials], backend)
        qber = np.array([r["true_sifted_error_rate"] for r in runs])
        sifted = np.array([r["sifted_key_length"] for r in runs], dtype=float)
        ratio = np.array([r["sifting_ratio"] for r in runs])
        eve_known = np.array([r["eve_known_sifted_fraction"] for r in runs])
        points.append({
            "value": value,
            "n_qubits": n,
            "qber": _summarise(qber),
            "expected_qber": expected_qber(channel),
            "sifted_key_length": _summarise(sifted),
            "sifting_ratio": _summarise(ratio),
            "eve_known_sifted_fraction": _summarise(eve_known),
        })

    return {
        "parameter": parameter,
        "config": {
            "values": list(values),
            "n_qubits": n_qubits,
            "trials": trials,
            "seed": seed,
            "eve_probability": base_channel.eve_probability,
            "noise": base_channel.noise,
            "noise_model": base_channel.noise_model,
            "backend": backend.name,
            "simulation_kind": backend.simulation_kind,
            "qber_definition": "true sifted-key error rate (simulation-only full comparison)",
        },
        "points": points,
    }


def key_exchange_sweep(
    parameter: Literal["eve_probability", "noise"],
    values: list[float],
    *,
    n_qubits: int = 4096,
    trials: int = 20,
    seed: int = 2024,
    base_channel: ChannelConfig | None = None,
    processing: ProcessingConfig | None = None,
    backend: QuantumBackend | None = None,
) -> dict:
    """Full key-exchange runs per value: acceptance rate, estimated vs true QBER, key length."""
    if trials < 1:
        raise ValueError("trials must be at least 1")
    if not values:
        raise ValueError("values must not be empty")
    if parameter not in ("eve_probability", "noise"):
        raise ValueError(f"unknown sweep parameter {parameter!r}")
    base_channel = base_channel or ChannelConfig()
    processing = processing or ProcessingConfig()
    backend = backend or NumpyBackend()
    children = np.random.SeedSequence(seed).spawn(len(values) * trials)

    points = []
    for i, value in enumerate(values):
        channel = replace(base_channel, **{parameter: float(value)})
        runs = [
            run_key_exchange(n_qubits, channel=channel, processing=processing,
                             rng=np.random.default_rng(ss), backend=backend).metrics()
            for ss in children[i * trials:(i + 1) * trials]
        ]
        accepted = [r for r in runs if r["accepted"]]
        reasons: dict[str, int] = {}
        for r in runs:
            if r["abort_reason"]:
                reasons[r["abort_reason"]] = reasons.get(r["abort_reason"], 0) + 1
        estimated = np.array([r["estimated_qber"] for r in runs])
        true = np.array([r["true_sifted_error_rate"] for r in runs])
        points.append({
            "value": value,
            "acceptance_rate": len(accepted) / trials,
            "abort_reasons": reasons,
            "estimated_qber": _summarise(estimated),
            "true_qber": _summarise(true),
            "estimation_error": _summarise(estimated - true),
            "expected_qber": expected_qber(channel),
            "final_key_length_accepted": _summarise(
                np.array([r["final_key_length"] for r in accepted], dtype=float)
            ) if accepted else None,
            "all_accepted_keys_match": all(r["final_keys_match"] for r in accepted),
            # aborted runs count as 0 bits: the operational key yield per qubit sent
            "secret_fraction": _summarise(
                np.array([r["final_key_length"] / r["n_qubits"] for r in runs])
            ),
            "upper_bound_coverage": float(np.mean(
                [r["qber_upper_bound"] >= expected_qber(channel) for r in runs]
            )),
        })

    return {
        "parameter": parameter,
        "config": {
            "values": list(values), "n_qubits": n_qubits, "trials": trials, "seed": seed,
            "eve_probability": base_channel.eve_probability, "noise": base_channel.noise,
            "noise_model": base_channel.noise_model, "backend": backend.name,
            "simulation_kind": backend.simulation_kind,
            "processing": asdict(processing),
        },
        "points": points,
    }
