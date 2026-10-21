"""Banks, transfers, QKD session history, security events, dashboard summary."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.serializers import event_out, session_out, transaction_out
from app.config import Settings, get_settings
from app.crypto.tamper import TamperMode
from app.db.models import (
    Bank,
    QKDSessionRecord,
    SecurityEvent,
    Severity,
    Transaction,
    TransactionStatus,
)
from app.qkd.channel import ChannelConfig
from app.qkd.key_exchange import ProcessingConfig
from app.services.transfers import (
    CURRENCIES,
    SimulationOptions,
    TransferRequest,
    TransferValidationError,
    submit_transfer,
)

router = APIRouter(tags=["banking"])


# --- banks ---------------------------------------------------------------------

@router.get("/banks")
def list_banks(db: Session = Depends(get_db)) -> list[dict]:
    return [
        {
            "code": b.code,
            "name": b.name,
            "account_prefix": b.account_prefix,
            "example_accounts": [f"{b.account_prefix}{n:04d}" for n in (1001, 1002, 2001)],
        }
        for b in db.scalars(select(Bank).order_by(Bank.code))
    ]


# --- transfers -----------------------------------------------------------------

class SimulationIn(BaseModel):
    n_qubits: int = Field(default=4096, ge=1024, le=65_536)
    seed: int | None = Field(default=None, ge=0)
    eve_probability: float = Field(default=0.0, ge=0.0, le=1.0)
    channel_noise: float = Field(default=0.0, ge=0.0, le=1.0)
    noise_model: Literal["depolarizing", "bit_phase_flip"] = "depolarizing"
    tamper: TamperMode = "none"


class TransferIn(BaseModel):
    sender_account: str = Field(examples=["QSB-A-1001"])
    receiver_account: str = Field(examples=["QSB-B-2001"])
    amount: str = Field(examples=["1250.00"], description="Decimal string, max 2 dp")
    currency: Literal[CURRENCIES] = "USD"  # type: ignore[valid-type]
    memo: str = Field(default="", max_length=140)
    simulation: SimulationIn = Field(default_factory=SimulationIn)


@router.post("/transfers", status_code=201)
def create_transfer(
    body: TransferIn, db: Session = Depends(get_db), settings: Settings = Depends(get_settings)
) -> dict:
    sim = body.simulation
    options = SimulationOptions(
        n_qubits=sim.n_qubits,
        seed=sim.seed,
        channel=ChannelConfig(sim.eve_probability, sim.channel_noise, sim.noise_model),
        processing=ProcessingConfig(
            qber_threshold=settings.qber_threshold, sample_fraction=settings.qber_sample_fraction
        ),
        tamper=sim.tamper,
    )
    request = TransferRequest(body.sender_account, body.receiver_account, body.amount,
                              body.currency, body.memo)
    try:
        txn = submit_transfer(db, request, options)
    except TransferValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return _transaction_detail(db, txn)


@router.get("/transfers")
def list_transfers(
    status: TransactionStatus | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    q = select(Transaction)
    if status:
        q = q.where(Transaction.status == status.value)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.scalars(q.order_by(Transaction.created_at.desc(), Transaction.id).limit(limit).offset(offset))
    return {"total": total, "items": [transaction_out(t) for t in rows]}


@router.get("/transfers/{transaction_id}")
def get_transfer(transaction_id: str, db: Session = Depends(get_db)) -> dict:
    txn = db.get(Transaction, transaction_id)
    if txn is None:
        raise HTTPException(status_code=404, detail="transaction not found")
    return _transaction_detail(db, txn)


def _transaction_detail(db: Session, txn: Transaction) -> dict:
    events = db.scalars(
        select(SecurityEvent).where(SecurityEvent.transaction_id == txn.id).order_by(SecurityEvent.id)
    )
    return {
        "transaction": transaction_out(txn, full=True),
        "qkd_session": session_out(txn.qkd_session) if txn.qkd_session else None,
        "events": [event_out(e) for e in events],
    }


# --- QKD sessions & security events ---------------------------------------------

@router.get("/qkd/sessions")
def list_sessions(
    accepted: bool | None = None,
    purpose: Literal["transfer", "lab"] | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    q = select(QKDSessionRecord)
    if accepted is not None:
        q = q.where(QKDSessionRecord.accepted == accepted)
    if purpose:
        q = q.where(QKDSessionRecord.purpose == purpose)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.scalars(q.order_by(QKDSessionRecord.created_at.desc()).limit(limit).offset(offset))
    return {"total": total, "items": [session_out(s) for s in rows]}


@router.get("/qkd/sessions/{session_id}")
def get_session(session_id: str, db: Session = Depends(get_db)) -> dict:
    s = db.get(QKDSessionRecord, session_id)
    if s is None:
        raise HTTPException(status_code=404, detail="QKD session not found")
    return session_out(s, full=True)


@router.get("/security-events")
def list_events(
    severity: Severity | None = None,
    event_type: str | None = Query(default=None, max_length=32),
    transaction_id: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> dict:
    q = select(SecurityEvent)
    if severity:
        q = q.where(SecurityEvent.severity == severity.value)
    if event_type:
        q = q.where(SecurityEvent.event_type == event_type)
    if transaction_id:
        q = q.where(SecurityEvent.transaction_id == transaction_id)
    total = db.scalar(select(func.count()).select_from(q.subquery()))
    rows = db.scalars(q.order_by(SecurityEvent.id.desc()).limit(limit).offset(offset))
    return {"total": total, "items": [event_out(e) for e in rows]}


# --- dashboard -----------------------------------------------------------------

@router.get("/dashboard/summary")
def dashboard_summary(db: Session = Depends(get_db)) -> dict:
    by_status = dict(db.execute(select(Transaction.status, func.count()).group_by(Transaction.status)).all())
    sessions_total = db.scalar(select(func.count(QKDSessionRecord.id))) or 0
    sessions_accepted = db.scalar(
        select(func.count(QKDSessionRecord.id)).where(QKDSessionRecord.accepted.is_(True))
    ) or 0
    avg_qber = db.scalar(select(func.avg(QKDSessionRecord.estimated_qber)))
    by_severity = dict(db.execute(select(SecurityEvent.severity, func.count()).group_by(SecurityEvent.severity)).all())
    recent = db.scalars(select(SecurityEvent).order_by(SecurityEvent.id.desc()).limit(10))
    return {
        "transactions": {
            "total": sum(by_status.values()),
            "by_status": {s.value: by_status.get(s.value, 0) for s in TransactionStatus},
        },
        "qkd_sessions": {
            "total": sessions_total,
            "accepted": sessions_accepted,
            "acceptance_rate": sessions_accepted / sessions_total if sessions_total else None,
            "mean_estimated_qber": avg_qber,
        },
        "security_events": {s.value: by_severity.get(s.value, 0) for s in Severity},
        "recent_events": [event_out(e) for e in recent],
    }
