"""Turn an accepted QKD key exchange into AES-256-GCM endpoints for both banks.

Alice (Bank A) derives keys from *her* final key and Bob (Bank B) from *his*. They
only interoperate if reconciliation and privacy amplification really produced equal
keys — so a key disagreement surfaces as an authentication failure, never as silently
wrong plaintext.
"""

from dataclasses import dataclass

from app.crypto.aead import AEADReceiver, AEADSender
from app.crypto.kdf import SessionKeys, derive_session_keys
from app.qkd.key_exchange import KeyExchangeResult


class KeyNotEstablishedError(RuntimeError):
    pass


@dataclass(frozen=True)
class BankEndpoint:
    bank: str          # "bank_a" or "bank_b"
    keys: SessionKeys
    sender: AEADSender
    receiver: AEADReceiver


def endpoint(bank: str, keys: SessionKeys) -> BankEndpoint:
    peer = "bank_b" if bank == "bank_a" else "bank_a"
    return BankEndpoint(
        bank=bank,
        keys=keys,
        sender=AEADSender(keys.sending_key(bank), keys.key_id, sender=bank),
        receiver=AEADReceiver(keys.receiving_key(bank), keys.key_id, expected_sender=peer),
    )


def establish_endpoints(
    result: KeyExchangeResult, session_id: str
) -> tuple[BankEndpoint, BankEndpoint]:
    """Returns (bank_a, bank_b). Raises if the key exchange was aborted."""
    if not result.accepted:
        reason = result.abort_reason.value if result.abort_reason else "unknown"
        raise KeyNotEstablishedError(f"QKD session aborted ({reason}); no key available")
    alice_keys = derive_session_keys(result.alice_final_key, session_id)
    bob_keys = derive_session_keys(result.bob_final_key, session_id)
    return endpoint("bank_a", alice_keys), endpoint("bank_b", bob_keys)
