# Banking Workflow and Data Model (Phase 6)

Fictional banks, fictional accounts, no real money. Code: `backend/app/services/transfers.py`,
`backend/app/db/models.py`.

## Transfer lifecycle

```
CREATED ──► KEY_EXCHANGE ──► (QKD aborted) ──────────────────────► BLOCKED
                         └─► ENCRYPTED ──► Bank B verifies tag ──► DELIVERED
                                                    └─ fails ────► REJECTED
```

1. Bank A creates the transaction (validated: fictional `QSB-A-####` / `QSB-B-####`
   accounts, different banks, 0.01–1,000,000.00, USD/EUR/GBP/INR, memo ≤ 140 chars).
2. A **fresh BB84 key exchange runs for every transfer**. If it aborts, the transfer is
   `BLOCKED` and nothing is encrypted or sent.
3. HKDF derives per-direction keys; the confidential payload (accounts, amount, currency,
   memo, reference) is sealed with AES-256-GCM. Routing metadata (reference, banks,
   session id, key id) is bound as associated data.
4. Optional simulated attack in transit: `ciphertext`, `tag`, `nonce`, `aad`, `wrong_key`, `replay`.
5. Bank B verifies the tag and decrypts. Success ⇒ `DELIVERED`; any failure ⇒ `REJECTED`.
   A replayed copy is rejected and the transfer is recorded only once.

Keys exist only inside `submit_transfer` and are discarded when it returns. Because every
transfer has its own key, every stored (key_id, nonce) pair is unique even though each
transfer's single message uses counter 0.

## Tables

| Table | Holds | Never holds |
|---|---|---|
| `banks` | 2 fictional banks | — |
| `qkd_sessions` | parameters (qubits, backend, seed, Eve, noise, threshold, sample fraction), headline metrics (sifted length, sample size/errors, estimated & true QBER, final key length), accept/abort reason, public `key_id`, full metrics JSON | any key bits |
| `transactions` | Bank A's origination record, status, failure reason, nonce, ciphertext, tag, AAD, `key_id`, tag-verified flag, delivery time | keys |
| `security_events` | typed, severity-tagged audit log linked to session and transaction | keys |
| `experiment_results` | experiment config (incl. seed) and per-point statistics | — |

Data policy enforcement (`tests/test_data_policy.py`): every derived AES key and both final
QKD keys from a run are searched for in the raw SQLite file as bytes, lowercase hex,
uppercase hex and bit strings; the schema is checked so only `key_id` and integer
`*_length` counters mention "key".

## Security events

| Event | Severity |
|---|---|
| `transaction_created`, `qkd_session_accepted`, `transaction_encrypted`, `auth_tag_verified`, `transaction_delivered` | info |
| `qkd_session_aborted`, `transaction_blocked`, `tampering_simulated`, `transaction_rejected` | warning |
| `high_qber_detected`, `auth_tag_failed`, `replay_rejected` | critical |

`high_qber_detected` is worded as "disturbance consistent with eavesdropping **or excess
channel noise**" — high QBER is not proof of an eavesdropper.

## API

| Method & path | Purpose |
|---|---|
| `GET /api/banks` | fictional banks + example accounts |
| `POST /api/transfers` | run the full workflow (`simulation`: qubits, seed, Eve, noise, tamper) |
| `GET /api/transfers[?status=&limit=&offset=]`, `GET /api/transfers/{id}` | history, detail with encryption fields and event trail |
| `GET /api/qkd/sessions[?accepted=&purpose=]`, `GET /api/qkd/sessions/{id}` | QKD session history (transfer and lab runs) |
| `GET /api/security-events[?severity=&event_type=&transaction_id=]` | audit log |
| `GET /api/dashboard/summary` | counts by status, acceptance rate, mean QBER, recent events |
| `POST /api/experiments`, `GET /api/experiments[/{id}]` | run bounded sweeps and browse stored results |

## Database

SQLite (`backend/qsb.db`, git-ignored) by default; set `QSB_DATABASE_URL` for PostgreSQL
(add a driver such as `psycopg`). Tables are created at startup with `create_all`; a
long-lived deployment would add Alembic migrations. To reset, stop the server and delete
`backend/qsb.db`.
