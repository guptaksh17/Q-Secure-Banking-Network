"""ORM models.

DATA POLICY: no column may hold raw, sifted, reconciled, final or derived key material.
Only the public ``key_id`` (an HKDF output under a separate label) is stored. A test
scans the SQLite file for every key the run derived to enforce this.
"""

import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import JSON, Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return uuid.uuid4().hex


class TransactionStatus(str, Enum):
    CREATED = "created"
    KEY_EXCHANGE = "key_exchange"
    BLOCKED = "blocked"          # QKD session aborted; nothing encrypted or sent
    ENCRYPTED = "encrypted"      # sealed with AES-256-GCM, in transit
    DELIVERED = "delivered"      # Bank B verified the tag and recorded the transfer
    REJECTED = "rejected"        # Bank B's authentication check failed


class Severity(str, Enum):
    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class EventType(str, Enum):
    TRANSACTION_CREATED = "transaction_created"
    QKD_SESSION_ACCEPTED = "qkd_session_accepted"
    QKD_SESSION_ABORTED = "qkd_session_aborted"
    HIGH_QBER_DETECTED = "high_qber_detected"
    TRANSACTION_BLOCKED = "transaction_blocked"
    TRANSACTION_ENCRYPTED = "transaction_encrypted"
    TAMPERING_SIMULATED = "tampering_simulated"
    AUTH_TAG_VERIFIED = "auth_tag_verified"
    AUTH_TAG_FAILED = "auth_tag_failed"
    REPLAY_REJECTED = "replay_rejected"
    TRANSACTION_DELIVERED = "transaction_delivered"
    TRANSACTION_REJECTED = "transaction_rejected"


class Bank(Base):
    __tablename__ = "banks"

    code: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    account_prefix: Mapped[str] = mapped_column(String(16))


class QKDSessionRecord(Base):
    __tablename__ = "qkd_sessions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    purpose: Mapped[str] = mapped_column(String(16))          # "transfer" | "lab"
    # parameters
    n_qubits: Mapped[int] = mapped_column(Integer)
    backend: Mapped[str] = mapped_column(String(16))
    simulation_kind: Mapped[str] = mapped_column(String(32))
    seed: Mapped[int | None] = mapped_column(Integer, nullable=True)
    eve_probability: Mapped[float] = mapped_column(Float)
    channel_noise: Mapped[float] = mapped_column(Float)
    noise_model: Mapped[str] = mapped_column(String(32))
    qber_threshold: Mapped[float] = mapped_column(Float)
    sample_fraction: Mapped[float] = mapped_column(Float)
    # headline metrics (queryable)
    sifted_key_length: Mapped[int] = mapped_column(Integer)
    test_sample_size: Mapped[int] = mapped_column(Integer)
    test_sample_errors: Mapped[int] = mapped_column(Integer)
    estimated_qber: Mapped[float] = mapped_column(Float)
    true_qber: Mapped[float] = mapped_column(Float)
    final_key_length: Mapped[int] = mapped_column(Integer)
    accepted: Mapped[bool] = mapped_column(Boolean)
    abort_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    key_id: Mapped[str | None] = mapped_column(String(16), nullable=True)  # public identifier
    # full metrics dict from KeyExchangeResult.metrics() (contains no key bits)
    metrics: Mapped[dict] = mapped_column(JSON)


class Transaction(Base):
    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    reference: Mapped[str] = mapped_column(String(32), unique=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    status: Mapped[str] = mapped_column(String(16), default=TransactionStatus.CREATED.value)
    failure_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)

    # Bank A's origination record (fictional data only)
    sender_bank: Mapped[str] = mapped_column(ForeignKey("banks.code"))
    receiver_bank: Mapped[str] = mapped_column(ForeignKey("banks.code"))
    sender_account: Mapped[str] = mapped_column(String(16))
    receiver_account: Mapped[str] = mapped_column(String(16))
    amount_cents: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(3))
    memo: Mapped[str] = mapped_column(String(140), default="")

    # what travelled over the classical channel
    qkd_session_id: Mapped[str | None] = mapped_column(ForeignKey("qkd_sessions.id"), nullable=True)
    key_id: Mapped[str | None] = mapped_column(String(16), nullable=True)
    nonce: Mapped[str | None] = mapped_column(String(24), nullable=True)        # hex
    ciphertext: Mapped[str | None] = mapped_column(Text, nullable=True)         # hex, tag excluded
    auth_tag: Mapped[str | None] = mapped_column(String(32), nullable=True)     # hex
    associated_data: Mapped[str | None] = mapped_column(Text, nullable=True)    # canonical JSON
    tamper_mode: Mapped[str] = mapped_column(String(16), default="none")

    # Bank B's outcome
    tag_verified: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    qkd_session: Mapped[QKDSessionRecord | None] = relationship()


class SecurityEvent(Base):
    __tablename__ = "security_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    event_type: Mapped[str] = mapped_column(String(32), index=True)
    severity: Mapped[str] = mapped_column(String(16), index=True)
    message: Mapped[str] = mapped_column(String(300))
    qkd_session_id: Mapped[str | None] = mapped_column(ForeignKey("qkd_sessions.id"), nullable=True, index=True)
    transaction_id: Mapped[str | None] = mapped_column(ForeignKey("transactions.id"), nullable=True, index=True)
    details: Mapped[dict] = mapped_column(JSON, default=dict)


class ExperimentResult(Base):
    __tablename__ = "experiment_results"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    name: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(32))        # "channel_sweep" | "key_exchange_sweep"
    parameter: Mapped[str] = mapped_column(String(32))
    config: Mapped[dict] = mapped_column(JSON)
    points: Mapped[list] = mapped_column(JSON)
