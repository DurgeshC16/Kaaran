"""CLI and name-set switch. A second seed also exercises the generator's self-check."""

import json

from kaaran.synth.__main__ import main


def test_cli_fictional_names_other_seed(tmp_path, capsys):
    assert main(["--seed", "7", "--out", str(tmp_path), "--names", "fictional"]) == 0
    assert "SYNTHETIC" in capsys.readouterr().out
    gt = json.loads((tmp_path / "ground_truth.json").read_text(encoding="utf-8"))
    assert gt["synthetic"] is True and gt["seed"] == 7 and gt["taluka_name_set"] == "fictional"
    assert "Pandharpur" not in json.dumps(gt, ensure_ascii=False)
    assert gt["truths"][0]["entities"]["talukas"] == ["Shivtara"]
