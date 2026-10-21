"""Derive AES-256 keys from the QKD final key with HKDF-SHA256 (RFC 5869).

Role of HKDF here: key *derivation and domain separation* only. The QKD final key is
already privacy-amplified (Toeplitz hashing, Phase 4); HKDF does NOT perform privacy
amplification and is not claimed to.

From one QKD key we derive, with distinct ``info`` labels:
  - ``bank_a_to_bank_b``  32-byte AES-256 key for messages Bank A -> Bank B
  - ``bank_b_to_bank_a``  32-byte AES-256 key for messages Bank B -> Bank A
  - ``key_id``            8-byte public identifier (safe to store/log; reveals nothing
                          useful about the keys because HKDF outputs under different
                          info labels are independent pseudorandom values)

Separate per-direction keys mean the two banks can never collide on (key, nonce) pairs.
The session id is bound into every label so keys from different sessions differ even
in the (negligible-probability) event that two QKD keys coincided.

Key bytes live only in memory. Python cannot reliably zeroise memory; this is a
documented limitation of the prototype.
"""

from dataclasses import dataclass, field

import numpy as np
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

PROTOCOL_LABEL = b"Q-Secure-Banking-Network/v1"
HKDF_SALT = PROTOCOL_LABEL + b"/hkdf-salt"   # fixed, public; RFC 5869 allows a non-secret salt
AES_KEY_BYTES = 32
KEY_ID_BYTES = 8
MIN_QKD_KEY_BITS = 256


class KeyDerivationError(ValueError):
    pass


def bits_to_bytes(bits: np.ndarray) -> bytes:
    """Pack whole bytes only (big-endian bit order); trailing bits (< 8) are dropped."""
    if bits.ndim != 1 or (bits.size and not np.isin(bits, (0, 1)).all()):
        raise KeyDerivationError("key must be a 1-D array of 0/1 bits")
    usable = bits[: (bits.size // 8) * 8].astype(np.uint8)
    return np.packbits(usable).tobytes()


def hkdf_sha256(ikm: bytes, info: bytes, length: int, salt: bytes = HKDF_SALT) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=length, salt=salt, info=info).derive(ikm)


@dataclass(frozen=True)
class SessionKeys:
    session_id: str
    key_id: str                                   # hex, public
    bank_a_to_bank_b: bytes = field(repr=False)   # secret
    bank_b_to_bank_a: bytes = field(repr=False)   # secret

    def sending_key(self, sender: str) -> bytes:
        return {"bank_a": self.bank_a_to_bank_b, "bank_b": self.bank_b_to_bank_a}[sender]

    def receiving_key(self, receiver: str) -> bytes:
        return {"bank_b": self.bank_a_to_bank_b, "bank_a": self.bank_b_to_bank_a}[receiver]


def derive_session_keys(qkd_key_bits: np.ndarray, session_id: str) -> SessionKeys:
    if qkd_key_bits is None or qkd_key_bits.size < MIN_QKD_KEY_BITS:
        raise KeyDerivationError(f"QKD key must have at least {MIN_QKD_KEY_BITS} bits")
    if not session_id or "|" in session_id:
        raise KeyDerivationError("session_id must be non-empty and must not contain '|'")
    ikm = bits_to_bytes(qkd_key_bits)
    sid = session_id.encode()

    def label(purpose: bytes) -> bytes:
        return PROTOCOL_LABEL + b"|" + purpose + b"|" + sid

    return SessionKeys(
        session_id=session_id,
        key_id=hkdf_sha256(ikm, label(b"key-id"), KEY_ID_BYTES).hex(),
        bank_a_to_bank_b=hkdf_sha256(ikm, label(b"aes-256-gcm|bank_a->bank_b"), AES_KEY_BYTES),
        bank_b_to_bank_a=hkdf_sha256(ikm, label(b"aes-256-gcm|bank_b->bank_a"), AES_KEY_BYTES),
    )
