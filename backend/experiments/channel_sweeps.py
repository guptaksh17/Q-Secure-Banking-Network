"""Phase 3 experiments: how Eve and channel noise drive QBER.

Run from the repository root:
    macOS:   python3.12 dev.py experiment channel_sweeps
    Windows: py -3.12 dev.py experiment channel_sweeps

Writes backend/experiments/output/channel_sweeps.json (regenerable, git-ignored)
and prints a summary table. Re-running with the same --seed gives identical numbers.
"""

import argparse
import json
from pathlib import Path

import numpy as np

from app.qkd.backends import get_backend
from app.qkd.channel import ChannelConfig
from app.qkd.experiments import sweep

OUTPUT_DIR = Path(__file__).resolve().parent / "output"


def _table(result: dict) -> str:
    lines = [f"\n== {result['parameter']} sweep "
             f"(n_qubits={result['config']['n_qubits']}, trials={result['config']['trials']}, "
             f"noise_model={result['config']['noise_model']}) =="]
    lines.append(f"{'value':>8} {'QBER mean':>10} {'± std':>8} {'theory':>8} {'sifted':>9} {'Eve knows':>10}")
    for p in result["points"]:
        lines.append(
            f"{p['value']:>8} {p['qber']['mean']:>10.4f} {p['qber']['std']:>8.4f} "
            f"{p['expected_qber']:>8.4f} {p['sifted_key_length']['mean']:>9.1f} "
            f"{p['eve_known_sifted_fraction']['mean']:>10.4f}"
        )
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seed", type=int, default=2024)
    parser.add_argument("--trials", type=int, default=30)
    parser.add_argument("--n-qubits", type=int, default=4096)
    parser.add_argument("--backend", choices=["numpy", "qiskit"], default="numpy")
    args = parser.parse_args()

    backend = get_backend(args.backend)
    grid = [round(x, 2) for x in np.linspace(0, 1, 11)]
    common = dict(n_qubits=args.n_qubits, trials=args.trials, seed=args.seed, backend=backend)

    results = {
        "eve_vs_qber": sweep("eve_probability", grid, **common),
        "depolarizing_noise_vs_qber": sweep(
            "noise", [round(x, 2) for x in np.linspace(0, 0.5, 11)], **common,
            base_channel=ChannelConfig(noise_model="depolarizing"),
        ),
        "bit_phase_flip_noise_vs_qber": sweep(
            "noise", [round(x, 2) for x in np.linspace(0, 0.5, 11)], **common,
            base_channel=ChannelConfig(noise_model="bit_phase_flip"),
        ),
        "qubits_vs_sifted_length": sweep(
            "n_qubits", [256, 512, 1024, 2048, 4096, 8192, 16384], **common,
        ),
    }

    OUTPUT_DIR.mkdir(exist_ok=True)
    out = OUTPUT_DIR / "channel_sweeps.json"
    out.write_text(json.dumps(results, indent=2))
    for result in results.values():
        print(_table(result))
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
