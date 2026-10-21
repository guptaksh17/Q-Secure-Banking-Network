"""Interbank transfer workflow (fictional banks, fictional accounts, no real money).

    1. Bank A creates the transaction                      -> CREATED
    2. Fresh BB84 key exchange for this transfer           -> KEY_EXCHANGE
       aborted?  -> BLOCKED (nothing is encrypted or sent)
    3. HKDF session keys; AES-256-GCM seal of the payload,
       transaction metadata bound as associated data       -> ENCRYPTED
    4. Transit (optionally a simulated tampering attack)
    5. Bank B verifies the tag and decrypts                -> DELIVERED
       authentication fails?                               -> REJECTED

One QKD session per transfer: keys exist only inside ``submit_transfer`` and are
discarded on return. Each transfer therefore has its own key, so the stored
(key_id, nonce) pairs are unique even though every first message uses counter 0.
"""

import json
import re
import uuid
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

import numpy as np
from sqlalchemy.orm import Session

from app.crypto.aead import AEADError, AEADReceiver, EncryptedMessage, ReplayError
from app.crypto.secure_channel import establish_endpoints
from app.crypto.tamper import TAMPER_MODES, tamper_message
from app.db.models import EventType, Severity, Transaction, TransactionStatus, new_id, utcnow
from app.qkd.backends import QuantumBackend
from app.qkd.channel import ChannelConfig
from app.qkd.key_exchange import ProcessingConfig, run_key_exchange
from app.services.records import log_event, record_key_exchange

ACCOUNT_PATTERN = re.compile(r"^QSB-([AB])-(\d{4})$")
BANK_FOR_LETTER = {"A": "bank_a", "B": "bank_b"}
CURRENCIES = ("USD", "EUR", "GBP", "INR")
MAX_AMOUNT = Decimal("1000000.00")
MIN_AMOUNT = Decimal("0.01")


class TransferValidationError(ValueError):
    pass


@dataclass(frozen=True)
class TransferRequest:
    sender_account: str
    receiver_account: str
    amount: str               # decimal string, e.g. "1250.00"
    currency: str = "USD"
    memo: str = ""


@dataclass(frozen=True)
class SimulationOptions:
    n_qubits: int = 4096
    seed: int | None = None
    channel: ChannelConfig = field(default_factory=ChannelConfig)
    processing: ProcessingConfig = field(default_factory=ProcessingConfig)
    tamper: str = "none"
    backend: QuantumBackend | None = None


def parse_amount(amount: str) -> int:
    """Decimal string -> integer cents. Rejects floats-in-disguise like '1e3' or '0.001'."""
    if not isinstance(amount, str) or not re.fullmatch(r"\d{1,7}(\.\d{1,2})?", amount.strip()):
        raise TransferValidationError("amount must be a decimal string with at most 2 decimal places")
    try:
        value = Decimal(amount.strip()).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation as exc:  # pragma: no cover - regex already guards
        raise TransferValidationError("invalid amount") from exc
    if not MIN_AMOUNT <= value <= MAX_AMOUNT:
        raise TransferValidationError(f"amount must be between {MIN_AMOUNT} and {MAX_AMOUNT}")
    return int(value * 100)


def format_cents(cents: int) -> str:
    return f"{cents // 100}.{cents % 100:02d}"


def validate(request: TransferRequest) -> tuple[str, str, int]:
    """Returns (sender_bank, receiver_bank, amount_cents)."""
    sender = ACCOUNT_PATTERN.fullmatch(request.sender_account or "")
    receiver = ACCOUNT_PATTERN.fullmatch(request.receiver_account or "")
    if not sender or not receiver:
        raise TransferValidationError(
            "accounts must be fictional identifiers of the form QSB-A-1234 or QSB-B-1234"
        )
    sender_bank, receiver_bank = BANK_FOR_LETTER[sender[1]], BANK_FOR_LETTER[receiver[1]]
    if sender_bank == receiver_bank:
        raise TransferValidationError("this network models interbank transfers: banks must differ")
    if request.currency not in CURRENCIES:
        raise TransferValidationError(f"currency must be one of {CURRENCIES}")
    if len(request.memo) > 140:
        raise TransferValidationError("memo must be at most 140 characters")
    return sender_bank, receiver_bank, parse_amount(request.amount)


def _canonical(obj: dict) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def _payload(txn: Transaction) -> bytes:
    """The confidential part that travels encrypted."""
    return _canonical({
        "reference": txn.reference,
        "sender_account": txn.sender_account,
        "receiver_account": txn.receiver_account,
        "amount": format_cents(txn.amount_cents),
        "currency": txn.currency,
        "memo": txn.memo,
    })


def _associated_data(txn: Transaction, session_id: str, key_id: str) -> bytes:
    """Authenticated-but-public routing metadata."""
    return _canonical({
        "version": 1,
        "reference": txn.reference,
        "sender_bank": txn.sender_bank,
        "receiver_bank": txn.receiver_bank,
        "qkd_session_id": session_id,
        "key_id": key_id,
    })


def submit_transfer(
    db: Session, request: TransferRequest, options: SimulationOptions | None = None
) -> Transaction:
    options = options or SimulationOptions()
    if options.tamper not in TAMPER_MODES:
        raise TransferValidationError(f"tamper must be one of {TAMPER_MODES}")
    sender_bank, receiver_bank, cents = validate(request)

    # 1. Bank A creates the transaction
    txn = Transaction(
        id=new_id(),
        reference=f"TXN-{uuid.uuid4().hex[:10].upper()}",
        sender_bank=sender_bank,
        receiver_bank=receiver_bank,
        sender_account=request.sender_account,
        receiver_account=request.receiver_account,
        amount_cents=cents,
        currency=request.currency,
        memo=request.memo,
        tamper_mode=options.tamper,
        status=TransactionStatus.CREATED.value,
    )
    db.add(txn)
    db.flush()
    log_event(db, EventType.TRANSACTION_CREATED, Severity.INFO,
              f"{txn.reference}: {format_cents(cents)} {txn.currency} "
              f"{sender_bank} -> {receiver_bank} created", transaction_id=txn.id)

    # 2. fresh QKD key exchange
    txn.status = TransactionStatus.KEY_EXCHANGE.value
    rng = np.random.default_rng(options.seed)
    result = run_key_exchange(
        options.n_qubits, channel=options.channel, processing=options.processing,
        rng=rng, backend=options.backend,
    )
    session_id = new_id()
    endpoints = None
    key_id = None
    if result.accepted:
        endpoints = establish_endpoints(result, session_id)
        key_id = endpoints[0].keys.key_id
    session = record_key_exchange(
        db, result, purpose="transfer", key_id=key_id,
        session_id=session_id, transaction_id=txn.id,
    )
    txn.qkd_session_id = session.id

    if endpoints is None:
        txn.status = TransactionStatus.BLOCKED.value
        txn.failure_reason = result.abort_reason.value
        log_event(db, EventType.TRANSACTION_BLOCKED, Severity.WARNING,
                  f"{txn.reference} blocked: no secure key ({result.abort_reason.value}); "
                  "nothing was encrypted or transmitted",
                  qkd_session_id=session.id, transaction_id=txn.id)
        db.flush()
        return txn

    # Orient endpoints: the sending bank encrypts, the receiving bank decrypts.
    bank_a, bank_b = endpoints
    sender_ep, receiver_ep = (bank_a, bank_b) if sender_bank == "bank_a" else (bank_b, bank_a)

    # 3. seal
    aad = _associated_data(txn, session.id, key_id)
    sent = sender_ep.sender.encrypt(_payload(txn), aad)
    txn.key_id, txn.nonce = sent.key_id, sent.nonce.hex()
    txn.ciphertext, txn.auth_tag = sent.ciphertext.hex(), sent.tag.hex()
    txn.associated_data = aad.decode()
    txn.status = TransactionStatus.ENCRYPTED.value
    log_event(db, EventType.TRANSACTION_ENCRYPTED, Severity.INFO,
              f"{txn.reference} sealed with AES-256-GCM (key_id {key_id}, nonce {sent.nonce.hex()})",
              qkd_session_id=session.id, transaction_id=txn.id)

    # 4. transit
    delivered: EncryptedMessage = tamper_message(sent, options.tamper)
    receiver: AEADReceiver = receiver_ep.receiver
    if options.tamper == "wrong_key":
        receiver = AEADReceiver(bytes(32), key_id, expected_sender=sender_bank)
    if options.tamper != "none":
        log_event(db, EventType.TAMPERING_SIMULATED, Severity.WARNING,
                  f"{txn.reference}: simulated attack '{options.tamper}' applied in transit",
                  qkd_session_id=session.id, transaction_id=txn.id,
                  details={"mode": options.tamper})

    # 5. Bank B verifies and records
    try:
        plaintext = receiver.decrypt(delivered)
        if plaintext != _payload(txn):  # defence in depth: GCM already guarantees this
            raise AEADError("decrypted payload does not match origination record")
    except AEADError as exc:
        txn.status = TransactionStatus.REJECTED.value
        txn.tag_verified = False
        txn.failure_reason = type(exc).__name__
        log_event(db, EventType.AUTH_TAG_FAILED, Severity.CRITICAL,
                  f"{txn.reference}: authentication failed at {receiver_bank} ({type(exc).__name__}); "
                  "message discarded", qkd_session_id=session.id, transaction_id=txn.id,
                  details={"error": str(exc)})
        log_event(db, EventType.TRANSACTION_REJECTED, Severity.WARNING,
                  f"{txn.reference} rejected; no funds recorded",
                  qkd_session_id=session.id, transaction_id=txn.id)
        db.flush()
        return txn

    txn.status = TransactionStatus.DELIVERED.value
    txn.tag_verified = True
    txn.delivered_at = utcnow()
    log_event(db, EventType.AUTH_TAG_VERIFIED, Severity.INFO,
              f"{txn.reference}: authentication tag verified by {receiver_bank}",
              qkd_session_id=session.id, transaction_id=txn.id)
    log_event(db, EventType.TRANSACTION_DELIVERED, Severity.INFO,
              f"{txn.reference} delivered: {format_cents(cents)} {txn.currency} recorded by {receiver_bank}",
              qkd_session_id=session.id, transaction_id=txn.id)

    if options.tamper == "replay":
        try:
            receiver.decrypt(delivered)
        except ReplayError:
            log_event(db, EventType.REPLAY_REJECTED, Severity.CRITICAL,
                      f"{txn.reference}: replayed copy rejected; transfer recorded only once",
                      qkd_session_id=session.id, transaction_id=txn.id)
    db.flush()
    return txn
