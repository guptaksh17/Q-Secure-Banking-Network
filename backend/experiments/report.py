"""Render evaluation results to CSV tables, PNG figures and a generated RESULTS.md.

Everything here is derived mechanically from the results dict produced by
final_evaluation.py — no value is typed in by hand.
"""

import csv
import json
import math
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from app.qkd.privacy_amplification import binary_entropy  # noqa: E402

# Validated categorical order (blue, orange, aqua) + reserved threshold red, neutral ink.
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
CRITICAL, INK, INK2, GRID = "#d03b3b", "#0b0b0b", "#52514e", "#e1e0d9"

plt.rcParams.update({
    "figure.dpi": 150, "savefig.dpi": 150, "savefig.bbox": "tight",
    "font.size": 9, "axes.titlesize": 10, "axes.labelsize": 9,
    "axes.edgecolor": "#c3c2b7", "axes.labelcolor": INK2, "axes.titlecolor": INK,
    "xtick.color": INK2, "ytick.color": INK2,
    "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.8,
    "axes.spines.top": False, "axes.spines.right": False,
    "legend.frameon": False, "lines.linewidth": 2, "lines.markersize": 5,
})


def pct(v, d=1):
    return f"{v * 100:.{d}f}%"


# --- CSV ---------------------------------------------------------------------------------------

def write_csv(path, rows):
    if not rows:
        return
    keys = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys, lineterminator="\n")
        w.writeheader()
        for r in rows:
            w.writerow({k: (json.dumps(v) if isinstance(v, (dict, list)) else v) for k, v in r.items()})


def tables(results):
    t = {
        "e1_eve_vs_qber": results["e1"]["rows"],
        "e2_depolarizing_vs_qber": results["e2"]["depolarizing"]["rows"],
        "e2_bit_phase_flip_vs_qber": results["e2"]["bit_phase_flip"]["rows"],
        "e3_sifting": results["e3"]["rows"],
        "e6_cascade_efficiency": results["e6"]["rows"],
        "e7_numpy_vs_qiskit": results["e7"]["rows"],
        "p1_bb84_throughput": results["p1"]["rows"],
        "p2_stage_timings": results["p2"]["rows"],
        "validation_summary": results["validation"],
    }
    for name, block in results["e4"].items():
        t[f"e4_acceptance_{name}"] = block["rows"]
    return t


# --- figures ---------------------------------------------------------------------------------------

def _theory_line(ax, x, y, color, label):
    ax.plot(x, y, linestyle="--", color=color, linewidth=1.5, label=label)


def fig_eve(results, path):
    rows = results["e1"]["rows"]
    x = [r["eve_probability"] for r in rows]
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    _theory_line(ax, x, [r["theory"] for r in rows], BLUE, "Theory p/4")
    ax.errorbar(x, [r["qber_mean"] for r in rows], yerr=[r["qber_sd"] for r in rows], fmt="o", color=BLUE,
                capsize=3, label=f"Measured mean ± 1 sd ({results['e1']['config']['trials']} trials)")
    ax.axhline(0.11, color=CRITICAL, linewidth=1.2, label="Illustrative 11% threshold")
    ax.set(xlabel="Eve intercept-and-resend probability", ylabel="Sifted-key QBER",
           title="E1 · Eavesdropping raises QBER linearly (p/4)")
    ax.yaxis.set_major_formatter(lambda v, _: pct(v, 0))
    ax.xaxis.set_major_formatter(lambda v, _: pct(v, 0))
    ax.legend(loc="upper left")
    fig.savefig(path)
    plt.close(fig)


def fig_noise(results, path):
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    for model, color, theory in (("depolarizing", BLUE, "p/2"), ("bit_phase_flip", ORANGE, "q")):
        rows = results["e2"][model]["rows"]
        x = [r["noise"] for r in rows]
        name = model.replace("_", "-")
        _theory_line(ax, x, [r["theory"] for r in rows], color, f"{name} theory ({theory})")
        ax.errorbar(x, [r["qber_mean"] for r in rows], yerr=[r["qber_sd"] for r in rows], fmt="o",
                    color=color, capsize=3, label=f"{name} measured")
    ax.axhline(0.11, color=CRITICAL, linewidth=1.2, label="Illustrative 11% threshold")
    ax.set(xlabel="Noise probability per qubit", ylabel="Sifted-key QBER",
           title="E2 · Channel noise raises QBER (no eavesdropper present)")
    ax.yaxis.set_major_formatter(lambda v, _: pct(v, 0))
    ax.xaxis.set_major_formatter(lambda v, _: pct(v, 0))
    ax.legend(loc="upper left")
    fig.savefig(path)
    plt.close(fig)


def fig_sifting(results, path):
    rows = results["e3"]["rows"]
    n = [r["n_qubits"] for r in rows]
    fig, (a, b) = plt.subplots(1, 2, figsize=(9, 3.6))
    _theory_line(a, n, [x / 2 for x in n], BLUE, "Theory n/2")
    a.errorbar(n, [r["sifted_mean"] for r in rows], yerr=[r["sifted_sd"] for r in rows], fmt="o", color=BLUE,
               capsize=3, label="Measured mean ± 1 sd")
    a.set(xscale="log", yscale="log", xlabel="Qubits sent", ylabel="Sifted-key length (bits)",
          title="E3a · Sifting keeps half the qubits")
    a.legend()
    _theory_line(b, n, [r["ratio_sd_theory"] for r in rows], BLUE, "Theory √(0.25/n)")
    b.plot(n, [r["ratio_sd"] for r in rows], "o", color=BLUE, label="Measured sd across trials")
    b.set(xscale="log", yscale="log", xlabel="Qubits sent", ylabel="Std. dev. of sifting ratio",
          title="E3b · Sifting ratio concentrates as 1/√n")
    b.legend()
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def fig_acceptance(results, path):
    e4 = results["e4"]
    sizes = sorted({int(k.rsplit("_", 1)[1]) for k in e4})
    colors = [BLUE, ORANGE, AQUA]
    panels = [("eve", "Eve intercept probability"), ("depolarizing", "Depolarizing noise p"),
              ("bit_phase_flip", "Bit-phase-flip noise q")]
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.4), sharey=True)
    for ax, (name, xlabel) in zip(axes, panels):
        for n, c in zip(sizes, colors):
            rows = e4[f"{name}_{n}"]["rows"]
            ax.plot([r["value"] for r in rows], [r["acceptance_rate"] for r in rows], "o-", color=c,
                    label=f"{n:,} qubits")
        ax.set(xlabel=xlabel, title=f"E4 · {name.replace('_', '-')}")
        ax.xaxis.set_major_formatter(lambda v, _: pct(v, 0 if abs(v * 100 - round(v * 100)) < 1e-6 else 1))
    axes[0].set_ylabel("Sessions accepted")
    axes[0].yaxis.set_major_formatter(lambda v, _: pct(v, 0))
    axes[0].legend(loc="lower left")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


def fig_key_rate(results, path):
    e4 = results["e4"]
    sizes = sorted({int(k.rsplit("_", 1)[1]) for k in e4})
    f_ec = sum(r["efficiency_mean"] for r in results["e6"]["rows"]) / len(results["e6"]["rows"])
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    es = [i / 1000 for i in range(0, 131)]

    def asym(e, f):
        return max(0.0, 0.5 * 0.75 * (1 - binary_entropy(e) - f * binary_entropy(e)))

    ax.plot(es, [asym(e, 1.0) for e in es], linestyle=":", color=INK2, linewidth=1.5,
            label="Asymptotic, ideal EC (f = 1)")
    ax.plot(es, [asym(e, f_ec) for e in es], linestyle="--", color=INK2, linewidth=1.5,
            label=f"Asymptotic, measured Cascade (f = {f_ec:.2f})")
    for n, c in zip(sizes, [BLUE, ORANGE]):
        pts = [r for name in ("eve", "depolarizing", "bit_phase_flip") for r in e4[f"{name}_{n}"]["rows"]]
        ax.plot([r["true_qber_mean"] for r in pts], [r["secret_fraction_mean"] for r in pts], "o", color=c,
                label=f"Measured, {n:,} qubits (all channels)")
    ax.axvline(0.11, color=CRITICAL, linewidth=1.2, label="Illustrative 11% threshold")
    ax.set(xlabel="True QBER", ylabel="Final key bits per qubit sent", xlim=(-0.005, 0.13),
           title="E4 · Secret-key yield vs QBER (finite-size gap shrinks with n)")
    ax.xaxis.set_major_formatter(lambda v, _: pct(v, 0))
    ax.legend(loc="upper right", fontsize=8)
    fig.savefig(path)
    plt.close(fig)


def fig_estimation(results, path):
    e5 = results["e5"]
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    ax.hist(e5["errors"], bins=30, color=BLUE, edgecolor="white", linewidth=0.8)
    for s in (-1, 1):
        ax.axvline(s * e5["estimation_error_sd_theory"], color=INK2, linestyle="--", linewidth=1.2)
    ax.set(xlabel="Estimated QBER − true sifted QBER", ylabel="Runs",
           title=f"E5 · Sample estimate is unbiased (dashed: ±1 sd theory; {e5['config']['runs']} runs)")
    ax.xaxis.set_major_formatter(lambda v, _: pct(v, 1))
    fig.savefig(path)
    plt.close(fig)


def fig_cascade(results, path):
    rows = results["e6"]["rows"]
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    ax.axhline(1.0, color=INK2, linestyle="--", linewidth=1.5, label="Shannon limit (f = 1)")
    ax.errorbar([r["error_rate"] for r in rows], [r["efficiency_mean"] for r in rows],
                yerr=[r["efficiency_sd"] for r in rows], fmt="o-", color=BLUE, capsize=3,
                label="Cascade (4 passes) mean ± 1 sd")
    ax.set(xlabel="Bit error rate", ylabel="Leaked bits / n·h(e)", ylim=(0.9, 1.4),
           title="E6 · Reconciliation leakage relative to the Shannon limit")
    ax.xaxis.set_major_formatter(lambda v, _: pct(v, 0))
    ax.legend()
    fig.savefig(path)
    plt.close(fig)


def fig_performance(results, path):
    p1, p2 = results["p1"]["rows"], results["p2"]["rows"]
    fig, (a, b) = plt.subplots(1, 2, figsize=(10, 3.6))
    for name, c in (("numpy", BLUE), ("qiskit", ORANGE)):
        rows = [r for r in p1 if r["backend"] == name]
        label = "NumPy (mathematical model)" if name == "numpy" else "Qiskit Aer (circuit simulation)"
        a.plot([r["n_qubits"] for r in rows], [r["median_ms"] for r in rows], "o-", color=c, label=label)
    a.set(xscale="log", yscale="log", xlabel="Qubits sent", ylabel="Median time (ms)",
          title="P1 · BB84 transmission + sifting")
    a.legend()
    last = p2[-1]
    stages = ["bb84", "estimation", "cascade", "privacy_amplification"]
    vals = [last[f"{s}_median_ms"] for s in stages]
    b.barh([s.replace("_", " ") for s in stages][::-1], vals[::-1], color=BLUE, height=0.5)
    for i, v in enumerate(vals[::-1]):
        b.text(v, i, f"  {v:.1f} ms", va="center", color=INK, fontsize=8)
    b.set(xlabel="Median time (ms)", title=f"P2 · Key-exchange stages at {last['n_qubits']:,} qubits")
    b.grid(axis="y", visible=False)
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)


FIGURES = [
    ("fig1_eve_vs_qber.png", fig_eve, "Eve intercept probability vs QBER"),
    ("fig2_noise_vs_qber.png", fig_noise, "Channel noise vs QBER"),
    ("fig3_sifting.png", fig_sifting, "Qubits sent vs sifted-key length"),
    ("fig4_acceptance.png", fig_acceptance, "Key acceptance rate under attack and noise"),
    ("fig5_key_rate.png", fig_key_rate, "Secret-key yield vs QBER"),
    ("fig6_estimation_error.png", fig_estimation, "QBER estimation error"),
    ("fig7_cascade_efficiency.png", fig_cascade, "Cascade efficiency"),
    ("fig8_performance.png", fig_performance, "Performance"),
]


# --- markdown -------------------------------------------------------------------------------------

def md_table(headers, rows):
    out = ["| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"]
    out += ["| " + " | ".join(str(c) for c in r) + " |" for r in rows]
    return "\n".join(out)


def z_fmt(z):
    return "∞" if not math.isfinite(z) else f"{z:+.2f}"


def results_markdown(r):
    env = r["environment"]
    L = []
    L.append("# Generated Results\n")
    L.append(f"> Generated by `dev.py experiment final_evaluation` ({r['mode']} mode, root seed **{r['root_seed']}**) "
             f"on {env['timestamp_utc']} in {r['runtime_seconds']} s. Every value below is computed from "
             "simulator runs recorded in `results.json`; nothing is entered by hand. Re-running with the same "
             "seed and package versions reproduces the experiment tables exactly (timings vary by machine).\n")
    L.append("## Environment\n")
    L.append(md_table(["Item", "Value"], [
        ["Platform", env["platform"]], ["Processor", env["processor"]], ["CPU cores", env["cpu_count"]],
        ["Python", env["python"]], *[[k, v] for k, v in env["packages"].items()],
    ]))

    L.append("\n## Statistical validation against theory\n")
    L.append("z = (measured mean − theory) / (sd/√trials). Under correct modelling |z| > 3 should occur in "
             "roughly 0.3% of points.\n")
    L.append(md_table(["Check", "Points", "max |z|", "Points with |z| > 3"],
                      [[v["check"], v["points"], f"{v['max_abs_z']:.2f}", v["points_abs_z_gt_3"]]
                       for v in r["validation"]]))

    e1 = r["e1"]
    L.append(f"\n## E1 · Eve intercept probability vs QBER\n\n{e1['config']['n_qubits']:,} qubits, "
             f"{e1['config']['trials']} trials per point.\n")
    L.append(md_table(["Eve p", "QBER mean", "± sd", "Theory p/4", "z", "Eve knows (sifted)"],
                      [[pct(x["eve_probability"], 0), pct(x["qber_mean"], 2), pct(x["qber_sd"], 2),
                        pct(x["theory"], 2), z_fmt(x["z"]), pct(x["eve_known_fraction"], 1)] for x in e1["rows"]]))
    L.append("\n![E1](figures/fig1_eve_vs_qber.png)\n")

    L.append("\n## E2 · Channel noise vs QBER\n")
    for model, th in (("depolarizing", "p/2"), ("bit_phase_flip", "q")):
        L.append(f"\n**{model.replace('_', '-')}** (theory {th})\n")
        L.append(md_table(["Noise", "QBER mean", "± sd", "Theory", "z"],
                          [[pct(x["noise"], 0), pct(x["qber_mean"], 2), pct(x["qber_sd"], 2), pct(x["theory"], 2),
                            z_fmt(x["z"])] for x in r["e2"][model]["rows"]]))
    L.append("\n![E2](figures/fig2_noise_vs_qber.png)\n")

    L.append("\n## E3 · Qubits sent vs sifted-key length\n")
    L.append(md_table(["Qubits", "Sifted mean", "Ratio mean", "Ratio sd", "Theory sd √(0.25/n)", "z (vs n/2)"],
                      [[f"{x['n_qubits']:,}", f"{x['sifted_mean']:.1f}", f"{x['ratio_mean']:.4f}",
                        f"{x['ratio_sd']:.4f}", f"{x['ratio_sd_theory']:.4f}", z_fmt(x["z"])] for x in r["e3"]["rows"]]))
    L.append("\n![E3](figures/fig3_sifting.png)\n")

    L.append("\n## E4 · Key acceptance and secret-key yield\n")
    L.append("Full pipeline per run: sampling (25%), abort rule (11%), Cascade, Toeplitz privacy amplification, "
             "≥ 256-bit minimum. *Secret fraction* counts aborted runs as 0.\n")
    for name, block in r["e4"].items():
        cfg = block["config"]
        L.append(f"\n**{name.rsplit('_', 1)[0].replace('_', '-')}**, {cfg['n_qubits']:,} qubits, {cfg['trials']} trials\n")
        L.append(md_table(["Value", "Accepted", "Est. QBER", "True QBER", "Final bits (accepted)",
                           "Bits / qubit", "Keys match", "Abort reasons"],
                          [[pct(x["value"], 1), pct(x["acceptance_rate"], 0), pct(x["estimated_qber_mean"], 2),
                            pct(x["true_qber_mean"], 2), f"{x['final_bits_accepted_mean']:.0f}",
                            f"{x['secret_fraction_mean']:.4f}", "yes" if x["all_accepted_keys_match"] else "NO",
                            ", ".join(f"{k}: {v}" for k, v in x["abort_reasons"].items()) or "—"]
                           for x in block["rows"]]))
    L.append("\n![E4 acceptance](figures/fig4_acceptance.png)\n\n![E4 key rate](figures/fig5_key_rate.png)\n")

    e5 = r["e5"]
    L.append("\n## E5 · QBER estimation accuracy\n")
    L.append(md_table(["Metric", "Value"], [
        ["Runs", e5["config"]["runs"]],
        ["Channel", f"depolarizing {e5['config']['noise']} → error probability {pct(e5['config']['error_probability'], 1)}"],
        ["Mean test-sample size", f"{e5['mean_sample_size']:.0f} bits"],
        ["Mean (estimate − true)", f"{e5['estimation_error_mean'] * 100:+.3f} pp"],
        ["Sd (estimate − true)", f"{e5['estimation_error_sd'] * 100:.3f} pp (theory ≈ {e5['estimation_error_sd_theory'] * 100:.3f} pp)"],
        ["Clopper–Pearson 99.9% upper bound ≥ true error probability", pct(e5["upper_bound_coverage"], 1)],
    ]))
    L.append("\n![E5](figures/fig6_estimation_error.png)\n")

    L.append("\n## E6 · Cascade reconciliation\n")
    L.append(md_table(["Error rate", "Leak / n·h(e)", "± sd", "Leaked bits", "Shannon limit", "Residual errors", "Verified"],
                      [[pct(x["error_rate"], 0), f"{x['efficiency_mean']:.3f}", f"{x['efficiency_sd']:.3f}",
                        f"{x['leaked_bits_mean']:.0f}", f"{x['shannon_limit_bits']:.0f}",
                        x["residual_error_bits_total"], pct(x["verified_fraction"], 0)] for x in r["e6"]["rows"]]))
    L.append(f"\n{r['e6']['config']['n']:,}-bit keys, {r['e6']['config']['trials']} trials per rate.\n")
    L.append("\n![E6](figures/fig7_cascade_efficiency.png)\n")

    L.append("\n## E7 · NumPy model vs Qiskit Aer circuits\n")
    L.append(md_table(["Eve p", "NumPy QBER", "Qiskit QBER", "Theory", "Difference", "z (two-sample)", "Qiskit z vs theory"],
                      [[pct(x["eve_probability"], 0), pct(x["numpy_qber"], 2), pct(x["qiskit_qber"], 2), pct(x["theory"], 2),
                        f"{x['difference'] * 100:+.2f} pp", z_fmt(x["z_two_sample"]), z_fmt(x["qiskit_z_vs_theory"])]
                       for x in r["e7"]["rows"]]))

    L.append("\n## Performance (this machine)\n")
    L.append("\n**P1 · BB84 transmission + sifting** (Eve 50%, depolarizing 5%)\n")
    L.append(md_table(["Backend", "Qubits", "Median ms", "p95 ms", "Qubits / s"],
                      [[x["backend"], f"{x['n_qubits']:,}", f"{x['median_ms']:.2f}", f"{x['p95_ms']:.2f}",
                        f"{x['qubits_per_second']:,.0f}"] for x in r["p1"]["rows"]]))
    L.append("\n**P2 · Key-exchange stage medians (ms)**\n")
    L.append(md_table(["Qubits", "BB84", "Estimation", "Cascade", "Privacy amp.", "Total"],
                      [[f"{x['n_qubits']:,}", f"{x['bb84_median_ms']:.2f}", f"{x['estimation_median_ms']:.2f}",
                        f"{x['cascade_median_ms']:.2f}", f"{x['privacy_amplification_median_ms']:.2f}",
                        f"{x['total_median_ms']:.2f}"] for x in r["p2"]["rows"]]))
    p3 = r["p3"]
    L.append(f"\n**P3 · Classical cryptography** ({p3['config']['payload_bytes']}-byte payload, {p3['config']['ops']} operations)\n")
    L.append(md_table(["Operation", "Median µs", "p95 µs"], [
        ["HKDF-SHA256: derive session keys", f"{p3['hkdf_session_keys']['median_ms'] * 1e3:.1f}", f"{p3['hkdf_session_keys']['p95_ms'] * 1e3:.1f}"],
        ["AES-256-GCM encrypt", f"{p3['aes_gcm_encrypt']['median_ms'] * 1e3:.1f}", f"{p3['aes_gcm_encrypt']['p95_ms'] * 1e3:.1f}"],
        ["AES-256-GCM decrypt + verify", f"{p3['aes_gcm_decrypt_verify']['median_ms'] * 1e3:.1f}", f"{p3['aes_gcm_decrypt_verify']['p95_ms'] * 1e3:.1f}"],
    ]))
    p4 = r["p4"]
    L.append(f"\n**P4 · End-to-end transfer** (fresh 4,096-qubit QKD session + HKDF + AES-GCM + SQLite writes, "
             f"{p4['repeats']} transfers): median **{p4['median_ms']:.1f} ms**, p95 {p4['p95_ms']:.1f} ms.\n")
    L.append("\n![Performance](figures/fig8_performance.png)\n")
    return "\n".join(L) + "\n"


def write_all(results, out: Path):
    out.mkdir(parents=True, exist_ok=True)
    (out / "figures").mkdir(exist_ok=True)
    (out / "csv").mkdir(exist_ok=True)
    (out / "results.json").write_text(json.dumps(results, indent=2, default=float), encoding="utf-8")
    for name, rows in tables(results).items():
        write_csv(out / "csv" / f"{name}.csv", rows)
    for filename, fn, _ in FIGURES:
        fn(results, out / "figures" / filename)
    (out / "RESULTS.md").write_text(results_markdown(results), encoding="utf-8")
