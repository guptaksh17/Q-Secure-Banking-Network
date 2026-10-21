"""Simulated in-transit tampering, used by the Security Simulator and transfer workflow."""

from dataclasses import replace
from typing import Literal

from app.crypto.aead import EncryptedMessage

TamperMode = Literal["none", "ciphertext", "tag", "nonce", "aad", "wrong_key", "replay"]
TAMPER_MODES: tuple[str, ...] = ("none", "ciphertext", "tag", "nonce", "aad", "wrong_key", "replay")


def _flip_first_bit(data: bytes) -> bytes:
    return bytes([data[0] ^ 0x01]) + data[1:] if data else b"\x01"


def tamper_message(message: EncryptedMessage, mode: str) -> EncryptedMessage:
    """Flip one bit in the chosen field. ``wrong_key``/``replay``/``none`` leave it intact
    (those attacks act on the receiver side or on delivery count, not on the bytes)."""
    if mode == "ciphertext":
        return replace(message, ciphertext=_flip_first_bit(message.ciphertext))
    if mode == "tag":
        return replace(message, tag=_flip_first_bit(message.tag))
    if mode == "nonce":
        # flip a counter bit (last byte) so the sender field stays valid and GCM is what rejects it
        return replace(message, nonce=message.nonce[:-1] + bytes([message.nonce[-1] ^ 0x01]))
    if mode == "aad":
        return replace(message, aad=_flip_first_bit(message.aad))
    return message
