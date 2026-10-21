"""Smoke test: the Phase 8 evaluation runs end to end and produces every artifact."""

import json
import math
import sys

import pytest

pytest.importorskip("matplotlib")
pytest.importorskip("qiskit_aer")


@pytest.mark.slow
def test_quick_evaluation_produces_all_artifacts(tmp_path, monkeypatch):
    from experiments import final_evaluation, report

    monkeypatch.setattr(sys, "argv", ["final_evaluation", "--quick", "--out", str(tmp_path)])
    final_evaluation.main()

    results = json.loads((tmp_path / "results.json").read_text())
    for key in ("e1", "e2", "e3", "e4", "e5", "e6", "e7", "p1", "p2", "p3", "p4", "validation", "environment"):
        assert key in results
    for filename, _, _ in report.FIGURES:
        assert (tmp_path / "figures" / filename).stat().st_size > 5_000
    assert len(list((tmp_path / "csv").glob("*.csv"))) >= 10

    md = (tmp_path / "RESULTS.md").read_text()
    assert "root seed **7**" in md and "Statistical validation" in md
    for filename, _, _ in report.FIGURES:
        assert f"figures/{filename}" in md

    # Even the tiny run must agree with theory and keep keys consistent.
    assert all(v["points_abs_z_gt_3"] == 0 for v in results["validation"])
    for block in results["e4"].values():
        assert all(r["all_accepted_keys_match"] for r in block["rows"])
    assert results["e6"]["rows"][0]["residual_error_bits_total"] == 0


def test_z_score_handles_zero_variance():
    from experiments.final_evaluation import z_score

    assert z_score(0.0, 0.0, 10, 0.0) == 0.0
    assert math.isinf(z_score(0.1, 0.0, 10, 0.0))
    assert z_score(0.26, 0.01, 25, 0.25) == pytest.approx(5.0)


def test_same_seed_reproduces_experiment_tables():
    from experiments.final_evaluation import QUICK, e1_eve, e3_sifting

    assert e1_eve(QUICK["e1"], 3) == e1_eve(QUICK["e1"], 3)
    assert e3_sifting(QUICK["e3"], 3) == e3_sifting(QUICK["e3"], 3)
    assert e1_eve(QUICK["e1"], 3) != e1_eve(QUICK["e1"], 4)
