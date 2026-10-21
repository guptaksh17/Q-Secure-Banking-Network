import json

import numpy as np
import pytest

from app.qkd.channel import ChannelConfig
from app.qkd.experiments import sweep


def test_sweep_is_reproducible_and_json_serialisable():
    a = sweep("eve_probability", [0.0, 0.5, 1.0], n_qubits=1024, trials=5, seed=1)
    b = sweep("eve_probability", [0.0, 0.5, 1.0], n_qubits=1024, trials=5, seed=1)
    assert a == b
    json.dumps(a)  # must not raise


def test_different_seed_changes_results():
    a = sweep("eve_probability", [1.0], n_qubits=1024, trials=5, seed=1)
    b = sweep("eve_probability", [1.0], n_qubits=1024, trials=5, seed=2)
    assert a["points"][0]["qber"] != b["points"][0]["qber"]


def test_sweep_records_full_configuration():
    r = sweep("noise", [0.1], n_qubits=512, trials=3, seed=9,
              base_channel=ChannelConfig(eve_probability=0.2, noise_model="bit_phase_flip"))
    cfg = r["config"]
    assert (cfg["seed"], cfg["trials"], cfg["n_qubits"]) == (9, 3, 512)
    assert cfg["eve_probability"] == 0.2 and cfg["noise_model"] == "bit_phase_flip"
    assert cfg["simulation_kind"] == "mathematical_model"


def test_eve_sweep_qber_increases_and_tracks_theory():
    r = sweep("eve_probability", [0.0, 0.25, 0.5, 0.75, 1.0], n_qubits=4096, trials=20, seed=3)
    means = [p["qber"]["mean"] for p in r["points"]]
    assert means[0] == 0.0
    assert all(b > a for a, b in zip(means, means[1:]))
    for p in r["points"]:
        # std of the mean over 20 trials of ~2048 sifted bits is < 0.003
        assert p["qber"]["mean"] == pytest.approx(p["expected_qber"], abs=0.01)


def test_qubit_sweep_sifted_length_scales_linearly():
    r = sweep("n_qubits", [512, 2048, 8192], trials=10, seed=4)
    for p in r["points"]:
        assert p["sifted_key_length"]["mean"] == pytest.approx(p["n_qubits"] / 2, rel=0.05)


def test_sweep_input_validation():
    with pytest.raises(ValueError):
        sweep("eve_probability", [], trials=1)
    with pytest.raises(ValueError):
        sweep("eve_probability", [0.1], trials=0)
    with pytest.raises(ValueError):
        sweep("temperature", [0.1], trials=1)


def test_key_exchange_sweep_acceptance_falls_with_eve():
    from app.qkd.experiments import key_exchange_sweep

    r = key_exchange_sweep("eve_probability", [0.0, 1.0], n_qubits=4096, trials=5, seed=5)
    clean, attacked = r["points"]
    assert clean["acceptance_rate"] == 1.0 and clean["all_accepted_keys_match"]
    assert attacked["acceptance_rate"] == 0.0
    assert attacked["abort_reasons"] == {"qber_above_threshold": 5}
    assert r["config"]["processing"]["qber_threshold"] == 0.11
    json.dumps(r)
