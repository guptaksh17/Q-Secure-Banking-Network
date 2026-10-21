"""Run experiments and store their results (config + per-point statistics) in the database."""

from sqlalchemy.orm import Session

from app.db.models import ExperimentResult
from app.qkd.channel import ChannelConfig
from app.qkd.experiments import key_exchange_sweep, sweep


def run_and_store(
    db: Session,
    *,
    name: str,
    kind: str,
    parameter: str,
    values: list[float],
    n_qubits: int,
    trials: int,
    seed: int,
    base_channel: ChannelConfig,
) -> ExperimentResult:
    if kind == "channel_sweep":
        result = sweep(parameter, values, n_qubits=n_qubits, trials=trials, seed=seed,
                       base_channel=base_channel)
    elif kind == "key_exchange_sweep":
        result = key_exchange_sweep(parameter, values, n_qubits=n_qubits, trials=trials, seed=seed,
                                    base_channel=base_channel)
    else:
        raise ValueError(f"unknown experiment kind {kind!r}")
    record = ExperimentResult(
        name=name, kind=kind, parameter=parameter, config=result["config"], points=result["points"],
    )
    db.add(record)
    db.flush()
    return record
