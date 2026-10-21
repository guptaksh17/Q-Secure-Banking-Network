# Demonstration Guide (≈ 12 minutes)

A scripted walkthrough for a presentation or viva. Start from a clean database so the
dashboard tells the story as you go.

## 0. Before the demo

```
# from the repository root
python3.12 dev.py test        # Windows: py -3.12 dev.py test   (show it passes)
python3.12 dev.py run         # Windows: run.bat
```

Open http://localhost:5173. To reset the data, stop the server and delete `backend/qsb.db`.
On the **Experimental Analysis** page, press *Run all experiments* once beforehand (about 20 s)
so the graphs are ready.

## 1. Frame it (30 s): Dashboard

"Two fictional banks exchange transfers. Each transfer gets a fresh key from a simulated BB84
session; AES-256-GCM protects the message. This is an educational simulation — no quantum
hardware, no real money, not production security."

## 2. BB84 end to end (3 min): QKD Laboratory

1. Defaults (4,096 qubits, seed 1), **Run key exchange**. Walk through the six steps:
   about 50% kept at sifting → 25% of sifted bits disclosed to estimate QBER (0%) → accept →
   Cascade has nothing to fix → privacy amplification subtracts Eve's bound and the leakage →
   about 1,228-bit key, and Alice's and Bob's keys match.
2. Scroll to **First qubits, step by step**: discarded rows are where the bases differ.
3. Set **Eve = 100%**, run → about 25% QBER → **aborted: QBER above threshold**. Explain p/4:
   Eve picks the wrong basis half the time, and Bob then errs half the time.
4. Set Eve = 0, **noise = 10% depolarizing**, run → about 5% QBER → accepted; Cascade corrects
   the errors; the key is shorter. "Errors don't stop us — reconciliation fixes them, and
   privacy amplification removes what Eve could know."
5. Optional: switch the backend to **Qiskit Aer** to show the same protocol running as circuits.

## 3. Two layers of defence (3 min): Security Simulator

1. **Run scenarios.** Point at the last bar: *noise alone* crosses the threshold. "High QBER
   means disturbance — it does not prove Eve."
2. Tamper lab: **Flip a ciphertext bit** → rejected, the changed field highlighted. Repeat with
   *tag*, *associated metadata*, *replay* (the first delivery succeeds, the replay is refused).

## 4. A transfer (2 min): Transaction Transfer

1. Send the default transfer → **Delivered**; show the wire format (nonce, tag, ciphertext,
   AAD) and the event trail. "The key itself is never stored — only this public key id."
2. Set Eve = 100% → **Blocked**: nothing was encrypted.
3. Set the attack to *Flip an authentication-tag bit* → **Rejected** with a critical event.

## 5. Evidence (2 min): Experimental Analysis

Walk through the four graphs: measured points sit on the dashed theory lines; the acceptance
curves drop **before** 11% QBER — privacy amplification is the binding constraint. Mention
`docs/results/RESULTS.md`: every number regenerates from seed 2024.

## 6. Close (30 s): History & Security Logs

Filter events by *critical*: the high-QBER, auth-failure and replay events from the demo.

---

## Likely questions

**Why does full intercept-and-resend give 25%?** On a sifted position Eve chooses the wrong
basis with probability ½; her resent state is then unbiased in Alice's basis, so Bob's bit is
wrong with probability ½. ½ × ½ = ¼. E1 measures 25.0% ± sampling error.

**Is 11% a real security limit?** It's an illustrative threshold (about the Shor–Preskill
asymptotic limit with ideal error correction). Here the key-length budget aborts sooner, around
6–7% at 8,192 qubits, because Cascade leaks about 1.2× the Shannon minimum and finite samples
need a confidence bound.

**Can you tell Eve from noise?** No. Both raise QBER; the protocol only bounds what *any*
eavesdropper could know and removes it with privacy amplification.

**Why not SHA-256 for privacy amplification?** The leftover hash lemma needs a universal hash
family; Toeplitz matrices are 2-universal (tested: collision rate 2⁻ᵐ). HKDF-SHA256 is used
afterwards only to derive and separate AES keys.

**How do you guarantee nonce uniqueness?** NIST SP 800-38D deterministic construction:
4-byte sender field + 64-bit counter, separate keys per direction, a fresh key per transfer,
and the sender refuses to wrap. Tests: 20,000 unique nonces; (key_id, nonce) unique across all
stored transactions.

**What does Qiskit add if NumPy gives the same results?** It shows the gate-level procedure
(X/H preparation, H before measurement) running as actual circuits, and E7 shows both
backends agree statistically. NumPy is used for large experiments because it is much faster.

**Is anything secret stored?** No. A test captures every derived key and searches the raw
SQLite file for it in binary, hex and bit-string form.

**What would a real deployment need?** Physical QKD hardware, decoy states, an authenticated
classical channel, composable finite-key analysis, a QRNG, an HSM, and much more — see
`docs/limitations.md`.
