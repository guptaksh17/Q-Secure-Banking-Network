# Architecture

```
React (Vite, :5173) ──/api proxy──▶ FastAPI (:8000)
                                     ├─ app/qkd       BB84, Eve, noise, QBER, reconciliation, privacy amplification
                                     ├─ app/crypto    HKDF-SHA256 key derivation, AES-256-GCM (counter nonces, replay rejection)
                                     ├─ app/services  transfer workflow (fresh QKD session per transfer), event log, experiment storage
                                     ├─ app/db        SQLAlchemy models: banks, qkd_sessions, transactions, security_events, experiment_results
                                     └─ app/api       HTTP routes
```

Design rules:

- The QKD engine (`app/qkd`) is pure Python/NumPy with no web or DB imports, so it
  can be unit-tested and used by experiment scripts directly.
- Key material lives only in memory for the duration of a request.
- All randomness flows through an injectable `numpy.random.Generator` so experiments
  are reproducible with a seed; production-style runs use OS entropy.
