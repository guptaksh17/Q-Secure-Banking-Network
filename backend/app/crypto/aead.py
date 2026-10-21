"""AES-256-GCM authenticated encryption with guaranteed-unique nonces and replay rejection.

Nonce construction — NIST SP 800-38D §8.2.1 (deterministic):
    nonce (96 bits) = fixed field (32 bits, identifies the sender)
                      || invocation counter (64 bits, big-endian, starts at 0)
Each ``AEADSender`` owns one key and one counter. The counter only increases and the
sender refuses to encrypt once it would wrap, so a (key, nonce) pair can never repeat.
Callers cannot supply a nonce. Because each direction also has its own key (see
``kdf.py``), uniqueness holds even if both banks used the same counter value.

Associated data (AAD) carries transaction metadata: authenticated, not encrypted.
Any change to ciphertext, tag, nonce, AAD or key makes decryption fail with
``AuthenticationError``; no plaintext is ever returned on failure.

``AEADReceiver`` rejects a nonce it has already accepted (``ReplayError``) so a
captured, valid transaction message cannot be delivered twice.
"""

from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

NONCE_BYTES = 12
TAG_BYTES = 16
FIXED_FIELD_BYTES = 4
MAX_COUNTER = 2**64 - 1
SENDER_FIELDS = {"bank_a": b"QSBA", "bank_b": b"QSBB"}
FORMAT_VERSION = 1


class AEADError(Exception):
    pass


class AuthenticationError(AEADError):
    """Tag verification failed: ciphertext, tag, nonce, AAD or key is wrong."""


class ReplayError(AEADError):
    """A message with this nonce was already accepted under this key."""


class KeyMismatchError(AEADError):
    """Message was produced under a different session key id."""


class NonceExhaustedError(AEADError):
    pass


@dataclass(frozen=True)
class EncryptedMessage:
    version: int
    key_id: str
    nonce: bytes
    ciphertext: bytes   # without tag
    tag: bytes          # 16-byte GCM authentication tag
    aad: bytes

    def to_dict(self) -> dict:
        """Hex-encoded form for storage/transport. Contains no key material."""
        return {
            "version": self.version,
            "key_id": self.key_id,
            "nonce": self.nonce.hex(),
            "ciphertext": self.ciphertext.hex(),
            "tag": self.tag.hex(),
            "aad": self.aad.hex(),
        }

    @classmethod
    def from_dict(cls, d: dict) -> "EncryptedMessage":
        return cls(
            version=int(d["version"]),
            key_id=d["key_id"],
            nonce=bytes.fromhex(d["nonce"]),
            ciphertext=bytes.fromhex(d["ciphertext"]),
            tag=bytes.fromhex(d["tag"]),
            aad=bytes.fromhex(d["aad"]),
        )


def _check_key(key: bytes) -> None:
    if not isinstance(key, (bytes, bytearray)) or len(key) != 32:
        raise ValueError("AES-256-GCM requires a 32-byte key")


class AEADSender:
    def __init__(self, key: bytes, key_id: str, sender: str, start_counter: int = 0):
        _check_key(key)
        if sender not in SENDER_FIELDS:
            raise ValueError(f"sender must be one of {sorted(SENDER_FIELDS)}")
        if not 0 <= start_counter <= MAX_COUNTER:
            raise ValueError("start_counter out of range")
        self._aead = AESGCM(bytes(key))
        self.key_id = key_id
        self.sender = sender
        self._fixed = SENDER_FIELDS[sender]
        self._next = start_counter

    def __repr__(self) -> str:
        return f"AEADSender(sender={self.sender!r}, key_id={self.key_id!r}, next_counter={self._next})"

    @property
    def messages_sent(self) -> int:
        return self._next

    def _next_nonce(self) -> bytes:
        if self._next > MAX_COUNTER:
            raise NonceExhaustedError("nonce counter exhausted; establish a new QKD session key")
        nonce = self._fixed + self._next.to_bytes(8, "big")
        self._next += 1
        return nonce

    def encrypt(self, plaintext: bytes, aad: bytes = b"") -> EncryptedMessage:
        nonce = self._next_nonce()
        sealed = self._aead.encrypt(nonce, plaintext, aad)
        return EncryptedMessage(
            version=FORMAT_VERSION,
            key_id=self.key_id,
            nonce=nonce,
            ciphertext=sealed[:-TAG_BYTES],
            tag=sealed[-TAG_BYTES:],
            aad=aad,
        )


class AEADReceiver:
    def __init__(self, key: bytes, key_id: str, expected_sender: str):
        _check_key(key)
        if expected_sender not in SENDER_FIELDS:
            raise ValueError(f"expected_sender must be one of {sorted(SENDER_FIELDS)}")
        self._aead = AESGCM(bytes(key))
        self.key_id = key_id
        self._fixed = SENDER_FIELDS[expected_sender]
        self._accepted_nonces: set[bytes] = set()

    def __repr__(self) -> str:
        return f"AEADReceiver(key_id={self.key_id!r}, accepted={len(self._accepted_nonces)})"

    def decrypt(self, message: EncryptedMessage) -> bytes:
        if message.version != FORMAT_VERSION:
            raise AuthenticationError(f"unsupported message version {message.version}")
        if message.key_id != self.key_id:
            raise KeyMismatchError("message key_id does not match this session")
        if len(message.nonce) != NONCE_BYTES or len(message.tag) != TAG_BYTES:
            raise AuthenticationError("malformed nonce or tag")
        if message.nonce[:FIXED_FIELD_BYTES] != self._fixed:
            raise AuthenticationError("nonce sender field does not match expected sender")
        if message.nonce in self._accepted_nonces:
            raise ReplayError("nonce already accepted under this key")
        try:
            plaintext = self._aead.decrypt(message.nonce, message.ciphertext + message.tag, message.aad)
        except InvalidTag as exc:
            raise AuthenticationError("authentication tag verification failed") from exc
        # Record only after successful authentication, so forged messages cannot
        # poison the replay cache.
        self._accepted_nonces.add(message.nonce)
        return plaintext
