"""Phase 8: complete, repeatable evaluation of the Q-Secure Banking Network simulation.

Run from the repository root:
    macOS:   python3.12 dev.py experiment final_evaluation
    Windows: py -3.12 dev.py experiment final_evaluation
    Quick smoke run (seconds):  ... final_evaluation --quick --out <dir>
    Re-render report only:      ... final_evaluation --from-json docs/results/results.json

Writes to docs/results/ by default:
    results.json       every number, with configuration, seeds and environment
    csv/*.csv          one table per experiment
    figures/*.png      report figures
    RESULTS.md         generated tables + figures (no hand-entered values)

Experiments
    E1  Eve intercept probability vs QBER            (theory p/4)
    E2  Channel noise vs QBER, two noise models       (theory p/2 and q)
    E3  Qubits sent vs sifted length; sifting-ratio spread vs sqrt(0.25/n)
    E4  Key acceptance + secret-key fraction vs Eve/noise at two key sizes
    E5  QBER estimation accuracy and Clopper-Pearson bound coverage
    E6  Cascade reconciliation efficiency and residual errors
    E7  NumPy (modelled) vs Qiskit Aer (circuit) agreement
Performance
    P1  BB84 throughput by backend and size
    P2  Key-exchange stage breakdown
    P3  HKDF + AES-256-GCM latency
    P4  End-to-end transfer latency incl. SQLite persistence

Statistical validation: for each measured point, z = (mean - theory) / (sd / sqrt(trials)).
Under correct modelling |z| > 3 should be rare (~0.3% of points).
"""

import argparse
import json
import math
import os
import platform
import statistics
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from app.crypto.aead import AEADReceiver, AEADSender
from app.crypto.kdf import derive_session_keys
from app.qkd.backends import NumpyBackend, QiskitBackend
from app.qkd.bb84 import run_bb84
from app.qkd.channel import ChannelConfig
from app.qkd.estimation import estimate_qber
from app.qkd.experiments import key_exchange_sweep, sweep
from app.qkd.key_exchange import ProcessingConfig
from app.qkd.privacy_amplification import binary_entropy, random_seed, secure_key_length, toeplitz_hash
from app.qkd.reconciliation import cascade_reconcile
from experiments import report

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = REPO_ROOT / "docs" / "results"


def grid(start, stop, step):
    n = int(round((stop - start) / step))
    return [round(start + i * step, 4) for i in range(n + 1)]


FULL = dict(
    seed=2024,
    e1=dict(values=grid(0, 1, 0.1), n_qubits=8192, trials=50),
    e2=dict(values=grid(0, 0.5, 0.05), n_qubits=8192, trials=50),
    e3=dict(values=[256, 512, 1024, 2048, 4096, 8192, 16384, 32768, 65536], trials=50),
    e4=dict(sizes=[8192, 32768], trials=30,
            eve=grid(0, 0.5, 0.05), depolarizing=grid(0, 0.3, 0.03), bit_phase_flip=grid(0, 0.15, 0.015)),
    e5=dict(runs=1000, n_qubits=4096, noise=0.1),
    e6=dict(rates=[0.01, 0.02, 0.03, 0.05, 0.07, 0.09, 0.11], n=10_000, trials=20),
    e7=dict(values=[0.0, 0.25, 0.5, 1.0], n_qubits=4096, trials=20),
    p1=dict(sizes=[1024, 4096, 16384, 32768], repeats=5),
    p2=dict(sizes=[8192, 32768], repeats=10),
    p3=dict(ops=5000, payload_bytes=256),
    p4=dict(transfers=30),
)

QUICK = dict(
    seed=7,
    e1=dict(values=[0, 0.5, 1.0], n_qubits=2048, trials=5),
    e2=dict(values=[0, 0.2], n_qubits=2048, trials=5),
    e3=dict(values=[256, 1024, 4096], trials=5),
    e4=dict(sizes=[4096], trials=3, eve=[0, 1.0], depolarizing=[0, 0.3], bit_phase_flip=[0, 0.15]),
    e5=dict(runs=40, n_qubits=4096, noise=0.1),
    e6=dict(rates=[0.03, 0.08], n=2000, trials=3),
    e7=dict(values=[0.0, 1.0], n_qubits=1024, trials=3),
    p1=dict(sizes=[1024], repeats=2),
    p2=dict(sizes=[4096], repeats=2),
    p3=dict(ops=200, payload_bytes=256),
    p4=dict(transfers=3),
)


# --- helpers -------------------------------------------------------------------------

def z_score(mean, std, trials, expected):
    se = std / math.sqrt(trials) if trials > 1 else 0.0
    if se == 0.0:
        return 0.0 if abs(mean - expected) < 1e-12 else math.inf
    return (mean - expected) / se


def timed(fn, repeats):
    samples = []
    for _ in range(repeats):
        t = time.perf_counter()
        fn()
        samples.append(time.perf_counter() - t)
    return {
        "median_ms": statistics.median(samples) * 1e3,
        "p95_ms": float(np.percentile(samples, 95)) * 1e3,
        "min_ms": min(samples) * 1e3,
        "repeats": repeats,
    }


def environment():
    from importlib.metadata import version
    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "platform": platform.platform(),
        "machine": platform.machine(),
        "processor": platform.processor() or "unknown",
        "cpu_count": os.cpu_count(),
        "python": sys.version.split()[0],
        "packages": {p: version(p) for p in ("numpy", "qiskit", "qiskit-aer", "cryptography", "fastapi", "SQLAlchemy")},
    }


def log(msg):
    print(msg, flush=True)


# --- experiments -----------------------------------------------------------------------

def e1_eve(cfg, seed):
    r = sweep("eve_probability", cfg["values"], n_qubits=cfg["n_qubits"], trials=cfg["trials"], seed=seed)
    rows = [{
        "eve_probability": p["value"], "qber_mean": p["qber"]["mean"], "qber_sd": p["qber"]["std"],
        "theory": p["expected_qber"], "eve_known_fraction": p["eve_known_sifted_fraction"]["mean"],
        "z": z_score(p["qber"]["mean"], p["qber"]["std"], cfg["trials"], p["expected_qber"]),
    } for p in r["points"]]
    return {"config": r["config"], "rows": rows}


def e2_noise(cfg, seed):
    out = {}
    for model in ("depolarizing", "bit_phase_flip"):
        r = sweep("noise", cfg["values"], n_qubits=cfg["n_qubits"], trials=cfg["trials"], seed=seed,
                  base_channel=ChannelConfig(noise_model=model))
        out[model] = {"config": r["config"], "rows": [{
            "noise": p["value"], "qber_mean": p["qber"]["mean"], "qber_sd": p["qber"]["std"],
            "theory": p["expected_qber"],
            "z": z_score(p["qber"]["mean"], p["qber"]["std"], cfg["trials"], p["expected_qber"]),
        } for p in r["points"]]}
    return out


def e3_sifting(cfg, seed):
    r = sweep("n_qubits", cfg["values"], trials=cfg["trials"], seed=seed)
    rows = []
    for p in r["points"]:
        n = p["n_qubits"]
        rows.append({
            "n_qubits": n,
            "sifted_mean": p["sifted_key_length"]["mean"],
            "sifted_sd": p["sifted_key_length"]["std"],
            "ratio_mean": p["sifting_ratio"]["mean"],
            "ratio_sd": p["sifting_ratio"]["std"],
            "ratio_sd_theory": math.sqrt(0.25 / n),
            "z": z_score(p["sifted_key_length"]["mean"], p["sifted_key_length"]["std"], cfg["trials"], n / 2),
        })
    return {"config": r["config"], "rows": rows}


def e4_acceptance(cfg, seed):
    out = {}
    sweeps = [("eve", "eve_probability", ChannelConfig(), cfg["eve"]),
              ("depolarizing", "noise", ChannelConfig(noise_model="depolarizing"), cfg["depolarizing"]),
              ("bit_phase_flip", "noise", ChannelConfig(noise_model="bit_phase_flip"), cfg["bit_phase_flip"])]
    for n in cfg["sizes"]:
        for name, param, base, values in sweeps:
            log(f"    E4 {name} n={n}")
            r = key_exchange_sweep(param, values, n_qubits=n, trials=cfg["trials"], seed=seed, base_channel=base)
            out[f"{name}_{n}"] = {"config": r["config"], "rows": [{
                "value": p["value"], "n_qubits": n, "acceptance_rate": p["acceptance_rate"],
                "expected_qber": p["expected_qber"],
                "estimated_qber_mean": p["estimated_qber"]["mean"], "true_qber_mean": p["true_qber"]["mean"],
                "secret_fraction_mean": p["secret_fraction"]["mean"],
                "final_bits_accepted_mean": p["final_key_length_accepted"]["mean"] if p["final_key_length_accepted"] else 0,
                "abort_reasons": p["abort_reasons"],
                "all_accepted_keys_match": p["all_accepted_keys_match"],
                "upper_bound_coverage": p["upper_bound_coverage"],
            } for p in r["points"]]}
    return out


def e5_estimation(cfg, seed):
    """Sample-based QBER vs the true sifted QBER, and coverage of the 99.9% upper bound."""
    channel = ChannelConfig(noise=cfg["noise"])
    p_true = channel.noise / 2
    children = np.random.SeedSequence(seed).spawn(cfg["runs"])
    errors, covered, ks = [], 0, []
    for ss in children:
        rng = np.random.default_rng(ss)
        run = run_bb84(cfg["n_qubits"], rng=rng, channel=channel)
        est = estimate_qber(run.sift.alice_key, run.sift.bob_key, 0.25, rng, epsilon=1e-3)
        true = run.metrics()["true_sifted_error_rate"]
        errors.append(est.qber_estimate - true)
        covered += est.qber_upper >= p_true
        ks.append(est.sample_size)
    k = statistics.mean(ks)
    return {
        "config": {**cfg, "seed": seed, "error_probability": p_true, "confidence": 0.999},
        "estimation_error_mean": float(np.mean(errors)),
        "estimation_error_sd": float(np.std(errors, ddof=1)),
        # sampling without replacement from ~sifted bits: sd ~ sqrt(p(1-p)/k * (1 - f))
        "estimation_error_sd_theory": math.sqrt(p_true * (1 - p_true) / k * (1 - 0.25)),
        "mean_sample_size": k,
        "upper_bound_coverage": covered / cfg["runs"],
        "errors": [float(e) for e in errors],
    }


def e6_cascade(cfg, seed):
    rows = []
    root = np.random.SeedSequence(seed)
    for rate, ss in zip(cfg["rates"], root.spawn(len(cfg["rates"]))):
        effs, residual, verified, leaks = [], 0, 0, []
        for child in ss.spawn(cfg["trials"]):
            rng = np.random.default_rng(child)
            a = rng.integers(0, 2, cfg["n"], dtype=np.uint8)
            b = a ^ (rng.random(cfg["n"]) < rate).astype(np.uint8)
            actual = np.count_nonzero(a != b) / cfg["n"]
            r = cascade_reconcile(a, b, rate, rng)
            effs.append(r.leaked_bits / (cfg["n"] * binary_entropy(actual)))
            leaks.append(r.leaked_bits)
            residual += int(np.count_nonzero(r.bob_corrected != a))
            verified += r.verified
        rows.append({
            "error_rate": rate, "efficiency_mean": float(np.mean(effs)), "efficiency_sd": float(np.std(effs, ddof=1)),
            "leaked_bits_mean": float(np.mean(leaks)), "shannon_limit_bits": cfg["n"] * binary_entropy(rate),
            "residual_error_bits_total": residual, "verified_fraction": verified / cfg["trials"],
        })
    return {"config": {**cfg, "seed": seed, "passes": 4}, "rows": rows}


def e7_backends(cfg, seed):
    out = {}
    for name, backend in (("numpy", NumpyBackend()), ("qiskit", QiskitBackend())):
        out[name] = sweep("eve_probability", cfg["values"], n_qubits=cfg["n_qubits"], trials=cfg["trials"],
                          seed=seed, backend=backend)
    rows = []
    for a, b in zip(out["numpy"]["points"], out["qiskit"]["points"]):
        se = math.sqrt(a["qber"]["std"] ** 2 / cfg["trials"] + b["qber"]["std"] ** 2 / cfg["trials"])
        diff = b["qber"]["mean"] - a["qber"]["mean"]
        rows.append({
            "eve_probability": a["value"], "numpy_qber": a["qber"]["mean"], "qiskit_qber": b["qber"]["mean"],
            "theory": a["expected_qber"], "difference": diff,
            "z_two_sample": diff / se if se else 0.0,
            "qiskit_z_vs_theory": z_score(b["qber"]["mean"], b["qber"]["std"], cfg["trials"], b["expected_qber"]),
        })
    return {"config": {**cfg, "seed": seed}, "rows": rows}


# --- performance --------------------------------------------------------------------------

def p1_bb84(cfg):
    rows = []
    for n in cfg["sizes"]:
        for name, backend in (("numpy", NumpyBackend()), ("qiskit", QiskitBackend())):
            t = timed(lambda: run_bb84(n, seed=1, backend=backend,
                                       channel=ChannelConfig(eve_probability=0.5, noise=0.05)), cfg["repeats"])
            rows.append({"backend": name, "n_qubits": n, **t,
                         "qubits_per_second": n / (t["median_ms"] / 1e3)})
    return {"config": cfg, "rows": rows}


def p2_stages(cfg):
    rows = []
    for n in cfg["sizes"]:
        stages = {"bb84": [], "estimation": [], "cascade": [], "privacy_amplification": []}
        for rep in range(cfg["repeats"]):
            rng = np.random.default_rng(rep)
            t0 = time.perf_counter()
            run = run_bb84(n, rng=rng, channel=ChannelConfig(noise=0.06))
            t1 = time.perf_counter()
            est = estimate_qber(run.sift.alice_key, run.sift.bob_key, 0.25, rng)
            t2 = time.perf_counter()
            rec = cascade_reconcile(est.alice_remaining, est.bob_remaining, est.qber_estimate, rng)
            t3 = time.perf_counter()
            budget = secure_key_length(est.remaining_length, est.qber_upper, rec.leaked_bits,
                                       rec.verification_bits, ProcessingConfig().pa_epsilon)
            if budget.output_bits:
                s = random_seed(est.remaining_length, budget.output_bits, rng)
                toeplitz_hash(est.alice_remaining, s, budget.output_bits)
                toeplitz_hash(rec.bob_corrected, s, budget.output_bits)
            t4 = time.perf_counter()
            for k, v in zip(stages, (t1 - t0, t2 - t1, t3 - t2, t4 - t3)):
                stages[k].append(v * 1e3)
        row = {"n_qubits": n, "channel": "depolarizing 0.06 (QBER ~3%)"}
        row.update({f"{k}_median_ms": statistics.median(v) for k, v in stages.items()})
        row["total_median_ms"] = sum(row[f"{k}_median_ms"] for k in stages)
        rows.append(row)
    return {"config": cfg, "rows": rows}


def p3_crypto(cfg):
    key_bits = np.random.default_rng(0).integers(0, 2, 1024, dtype=np.uint8)
    hkdf = timed(lambda: derive_session_keys(key_bits, "bench"), 200)
    keys = derive_session_keys(key_bits, "bench")
    payload = os.urandom(cfg["payload_bytes"])
    aad = b"txn=BENCH|from=bank_a|to=bank_b"
    sender = AEADSender(keys.bank_a_to_bank_b, keys.key_id, "bank_a")
    msgs = []
    enc = timed(lambda: msgs.append(sender.encrypt(payload, aad)), cfg["ops"])
    receiver = AEADReceiver(keys.bank_a_to_bank_b, keys.key_id, "bank_a")
    it = iter(msgs)
    dec = timed(lambda: receiver.decrypt(next(it)), cfg["ops"])
    return {"config": cfg, "hkdf_session_keys": hkdf, "aes_gcm_encrypt": enc, "aes_gcm_decrypt_verify": dec}


def p4_transfers(cfg):
    from app.db.database import Database
    from app.services.transfers import SimulationOptions, TransferRequest, submit_transfer

    with tempfile.TemporaryDirectory() as tmp:
        db = Database(f"sqlite:///{Path(tmp) / 'bench.db'}")
        db.create_all()
        req = TransferRequest("QSB-A-1001", "QSB-B-2001", "100.00")
        counter = iter(range(10_000))

        def one():
            with db.session() as s:
                submit_transfer(s, req, SimulationOptions(seed=next(counter)))

        result = timed(one, cfg["transfers"])
        db.dispose()
    return {"config": {**cfg, "n_qubits": 4096, "storage": "SQLite file"}, **result}


# --- validation summary -----------------------------------------------------------------

def validation_summary(results):
    groups = {
        "E1 Eve vs QBER": [r["z"] for r in results["e1"]["rows"]],
        "E2 depolarizing vs QBER": [r["z"] for r in results["e2"]["depolarizing"]["rows"]],
        "E2 bit-phase flip vs QBER": [r["z"] for r in results["e2"]["bit_phase_flip"]["rows"]],
        "E3 sifted length vs n/2": [r["z"] for r in results["e3"]["rows"]],
        "E7 Qiskit vs theory": [r["qiskit_z_vs_theory"] for r in results["e7"]["rows"]],
        "E7 Qiskit vs NumPy (two-sample)": [r["z_two_sample"] for r in results["e7"]["rows"]],
    }
    out = []
    for name, zs in groups.items():
        finite = [abs(z) for z in zs if math.isfinite(z)]
        out.append({
            "check": name, "points": len(zs),
            "max_abs_z": max(finite) if finite else 0.0,
            "points_abs_z_gt_3": sum(1 for z in zs if not math.isfinite(z) or abs(z) > 3),
        })
    return out


# --- main -----------------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--quick", action="store_true", help="tiny configuration for a smoke test")
    parser.add_argument("--seed", type=int, default=None, help="override the root seed")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--from-json", type=Path, default=None,
                        help="re-render CSV/figures/RESULTS.md from an existing results.json without re-running")
    args = parser.parse_args()
    # dev.py runs experiments from backend/; resolve relative paths from the repo root.
    args.out = args.out if args.out.is_absolute() else REPO_ROOT / args.out
    if args.from_json and not args.from_json.is_absolute():
        args.from_json = REPO_ROOT / args.from_json

    if args.from_json:
        results = json.loads(args.from_json.read_text(encoding="utf-8"))
        report.write_all(results, args.out)
        log(f"Re-rendered {args.out} from {args.from_json}")
        return

    cfg = QUICK if args.quick else FULL
    seed = args.seed if args.seed is not None else cfg["seed"]
    start = time.perf_counter()
    results = {"mode": "quick" if args.quick else "full", "root_seed": seed, "environment": environment()}

    steps = [
        ("e1", "E1 Eve vs QBER", lambda: e1_eve(cfg["e1"], seed)),
        ("e2", "E2 noise vs QBER", lambda: e2_noise(cfg["e2"], seed)),
        ("e3", "E3 sifting", lambda: e3_sifting(cfg["e3"], seed)),
        ("e4", "E4 acceptance & key rate", lambda: e4_acceptance(cfg["e4"], seed)),
        ("e5", "E5 estimation accuracy", lambda: e5_estimation(cfg["e5"], seed)),
        ("e6", "E6 Cascade efficiency", lambda: e6_cascade(cfg["e6"], seed)),
        ("e7", "E7 NumPy vs Qiskit", lambda: e7_backends(cfg["e7"], seed)),
        ("p1", "P1 BB84 throughput", lambda: p1_bb84(cfg["p1"])),
        ("p2", "P2 stage timings", lambda: p2_stages(cfg["p2"])),
        ("p3", "P3 HKDF + AES-GCM", lambda: p3_crypto(cfg["p3"])),
        ("p4", "P4 end-to-end transfers", lambda: p4_transfers(cfg["p4"])),
    ]
    for key, label, fn in steps:
        t = time.perf_counter()
        log(f"[{key}] {label} ...")
        results[key] = fn()
        log(f"[{key}] done in {time.perf_counter() - t:.1f}s")

    results["validation"] = validation_summary(results)
    results["runtime_seconds"] = round(time.perf_counter() - start, 1)
    report.write_all(results, args.out)
    log(f"\nWrote {args.out} in {results['runtime_seconds']}s")
    for v in results["validation"]:
        log(f"  {v['check']:<34} points={v['points']:>3}  max|z|={v['max_abs_z']:.2f}  |z|>3: {v['points_abs_z_gt_3']}")


if __name__ == "__main__":
    main()
