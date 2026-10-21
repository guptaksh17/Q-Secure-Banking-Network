# Classical Cryptography Layer (Phase 5)

How the QKD final key protects a transaction. Code: `backend/app/crypto/`.

```
QKD final key (≥256 bits, Toeplitz-amplified, in memory only)
        │  HKDF-SHA256 (RFC 5869) — derivation + domain separation, NOT privacy amplification
        ├── key_id            8 bytes, public, storable
        ├── K(A→B)            32 bytes  → Bank A AEADSender  / Bank B AEADReceiver
        └── K(B→A)            32 bytes  → Bank B AEADSender  / Bank A AEADReceiver
                                   │
                         AES-256-GCM, 96-bit nonce, 128-bit tag
```

## Key derivation (`kdf.py`)

- IKM = QKD final key packed into whole bytes (big-endian bit order; < 8 trailing bits dropped).
- Salt = fixed public protocol constant (RFC 5869 permits a non-secret salt).
- `info` = `Q-Secure-Banking-Network/v1 | <purpose> | <session_id>`; `|` is forbidden in
  session ids so labels cannot be confused.
- Separate keys per direction ⇒ the two banks can never produce the same (key, nonce) pair.
- Verified against RFC 5869 test case 1.

## Encryption (`aead.py`)

| Property | Mechanism | Test |
|---|---|---|
| Confidentiality + integrity | AES-256-GCM via `cryptography` (OpenSSL) | McGrew–Viega vectors 13/14; round-trips |
| Nonce unique under its key | NIST SP 800-38D §8.2.1 deterministic nonce: 4-byte sender field ‖ 8-byte counter; counter only increments; encryption refused before wrap; callers cannot pass a nonce | 20,000 encryptions all distinct; exhaustion test |
| Tamper detection | Any change to ciphertext, tag, nonce or AAD ⇒ `AuthenticationError`; no plaintext on failure | every byte of each field flipped |
| Metadata binding | Transaction id/banks/session in AAD (authenticated, not encrypted) | AAD bit flips rejected |
| Replay protection | Receiver rejects nonces it already accepted; recorded only *after* authentication so forgeries cannot poison the cache | replay + poisoning tests |
| Wrong/cross-session keys | `key_id` check, then GCM tag check | 1-bit key disagreement ⇒ rejection, never wrong plaintext |
| Reflection | Direction-specific keys and sender field | bounce-back test |

## Lab endpoint

`POST /api/crypto/demo` runs a key exchange, encrypts a fictional message as Bank A,
optionally tampers (`ciphertext`, `tag`, `nonce`, `aad`, `wrong_key`, `replay`), and
reports Bank B's verification outcome. If the QKD session aborts the transaction is
`blocked` and nothing is encrypted. Responses include ciphertext, nonce, tag and `key_id`
— never key bytes.

## Limitations

- Python cannot reliably zeroise memory; keys may linger until garbage-collected.
- The replay cache and nonce counter live in process memory for the life of a session key.
  Keys are never persisted, so a restart loses the key along with its counter — a nonce
  can't be reused across restarts.
- The classical channel's authentication (assumed by BB84) is not implemented.
- AES-GCM's security bound limits one key to < 2³² messages for random nonces; with the
  deterministic counter the limit is 2⁶⁴ invocations, far beyond one banking session.
