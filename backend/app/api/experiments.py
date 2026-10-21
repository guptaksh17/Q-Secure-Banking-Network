"""Run bounded experiments on demand and browse stored results.

Limits keep a single request to a few seconds; larger studies use the CLI scripts
(`dev.py experiment ...`).
"""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.serializers import experiment_out
from app.db.models import ExperimentResult
from app.qkd.channel import ChannelConfig
from app.services.experiment_store import run_and_store

router = APIRouter(prefix="/experiments", tags=["experiments"])


class ExperimentIn(BaseModel):
    name: str = Field(min_length=1, max_length=64)
    kind: Literal["channel_sweep", "key_exchange_sweep"]
    parameter: Literal["eve_probability", "noise", "n_qubits"]
    values: list[float] = Field(min_length=1, max_length=21)
    n_qubits: int = Field(default=4096, ge=256, le=32_768)
    trials: int = Field(default=10, ge=1, le=50)
    seed: int = Field(default=2024, ge=0)
    eve_probability: float = Field(default=0.0, ge=0.0, le=1.0)
    channel_noise: float = Field(default=0.0, ge=0.0, le=1.0)
    noise_model: Literal["depolarizing", "bit_phase_flip"] = "depolarizing"

    @model_validator(mode="after")
    def _check(self):
        if self.kind == "key_exchange_sweep" and self.parameter == "n_qubits":
            raise ValueError("key_exchange_sweep supports eve_probability or noise")
        if self.parameter in ("eve_probability", "noise") and not all(0 <= v <= 1 for v in self.values):
            raise ValueError("probability values must be in [0, 1]")
        if self.parameter == "n_qubits" and not all(256 <= v <= 32_768 and v == int(v) for v in self.values):
            raise ValueError("n_qubits values must be integers in [256, 32768]")
        work = len(self.values) * self.trials * (max(self.values) if self.parameter == "n_qubits" else self.n_qubits)
        if work > 20_000_000:
            raise ValueError("experiment too large for a single request; use the CLI scripts")
        return self


@router.post("", status_code=201)
def run_experiment(body: ExperimentIn, db: Session = Depends(get_db)) -> dict:
    record = run_and_store(
        db, name=body.name, kind=body.kind, parameter=body.parameter, values=body.values,
        n_qubits=body.n_qubits, trials=body.trials, seed=body.seed,
        base_channel=ChannelConfig(body.eve_probability, body.channel_noise, body.noise_model),
    )
    return experiment_out(record, full=True)


@router.get("")
def list_experiments(
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    total = db.scalar(select(func.count(ExperimentResult.id)))
    rows = db.scalars(select(ExperimentResult).order_by(ExperimentResult.created_at.desc()).limit(limit).offset(offset))
    return {"total": total, "items": [experiment_out(x) for x in rows]}


@router.get("/{experiment_id}")
def get_experiment(experiment_id: str, db: Session = Depends(get_db)) -> dict:
    x = db.get(ExperimentResult, experiment_id)
    if x is None:
        raise HTTPException(status_code=404, detail="experiment not found")
    return experiment_out(x, full=True)
