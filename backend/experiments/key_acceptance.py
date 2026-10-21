"""Phase 4 experiments: key acceptance under attack and noise, estimated vs true QBER.

Run from the repository root:
    macOS:   python3.12 dev.py experiment key_acceptance
    Windows: py -3.12 dev.py experiment key_acceptance

Writes backend/experiments/output/key_acceptance.json and prints a summary table.
Each point runs the complete pipeline (BB84 -> sampling -> abort rule -> Cascade ->
Toeplitz privacy amplification) ``--trials`` times with independent seeded streams.
"""

import argparse
import json
from pathlib import Path

import numpy as np

from app.qkd.backends import get_backend
from app.qkd.channel import ChannelConfig
from app.qkd.experiments import key_exchange_sweep

OUTPUT_DIR = Path(__file__).resolve().parent / "output"


def _table(name: str, result: dict) -> str:
    cfg = result["config"]
    lines = [f"\n== {name} (n_qubits={cfg['n_qubits']}, trials={cfg['trials']}, "
             f"threshold={cfg['processing']['qber_threshold']}) =="]
    lines.append(f"{'value':>6} {'accept':>7} {'est QBER':>9} {'true QBER':>10} {'theory':>7} "
                 f"{'final bits':>11} {'keys ok':>8}  aborts")
    for p in result["points"]:
        bits = p["final_key_length_accepted"]
        bits_text = f"{bits['mean']:.0f}" if bits else "-"
        lines.append(
            f"{p['value']:>6} {p['acceptance_rate']:>7.2f} {p['estimated_qber']['mean']:>9.4f} "
            f"{p['true_qber']['mean']:>10.4f} {p['expected_qber']:>7.4f} "
            f"{bits_text:>11} {str(p['all_accepted_keys_match']):>8}  "
            f"{p['abort_reasons'] or ''}"
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seed", type=int, default=2024)
    parser.add_argument("--trials", type=int, default=30)
    parser.add_argument("--n-qubits", type=int, default=8192)
    parser.add_argument("--backend", choices=["numpy", "qiskit"], default="numpy")
    args = parser.parse_args()

    common = dict(n_qubits=args.n_qubits, trials=args.trials, seed=args.seed,
                  backend=get_backend(args.backend))
    results = {
        "acceptance_vs_eve": key_exchange_sweep(
            "eve_probability", [round(x, 2) for x in np.linspace(0, 1, 11)], **common),
        "acceptance_vs_depolarizing_noise": key_exchange_sweep(
            "noise", [round(x, 2) for x in np.linspace(0, 0.3, 13)], **common,
            base_channel=ChannelConfig(noise_model="depolarizing")),
        "acceptance_vs_bit_phase_flip_noise": key_exchange_sweep(
            "noise", [round(x, 3) for x in np.linspace(0, 0.15, 13)], **common,
            base_channel=ChannelConfig(noise_model="bit_phase_flip")),
    }

    OUTPUT_DIR.mkdir(exist_ok=True)
    out = OUTPUT_DIR / "key_acceptance.json"
    out.write_text(json.dumps(results, indent=2))
    for name, result in results.items():
        print(_table(name, result))
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
