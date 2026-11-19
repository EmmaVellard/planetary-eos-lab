from __future__ import annotations

import json
from pathlib import Path

import pytest

import make_compositions
import run_perplex
from planetary_eos_lab.core.database_utils import get_database_components

CATALOGUE = Path(__file__).resolve().parents[1] / "configs" / "lunar_bsm_models.json"


def warren_preferred_entry() -> dict:
    models = json.loads(CATALOGUE.read_text())["models"]
    return next(m for m in models if m["project"] == "moon_w05_preferred_bsm")


def test_hp636_uses_the_hp633_components_and_its_own_data_file() -> None:
    assert get_database_components("hp636") == get_database_components("hp633")
    template = run_perplex.default_build_template_for_database("hp636").read_text()
    assert "hp636ver.dat" in template and "hp633ver.dat" not in template
    assert run_perplex.default_werami_sequence_for_database("hp636") == run_perplex.HP633_WERAMI_INPUT_SEQUENCE


def test_excluded_tio2_gives_the_ti_free_warren_preferred_composition(tmp_path: Path) -> None:
    """Ti-free Warren (2005) Preferred used for the August 2026 stx24 tables:
    SiO2 47.285113, Al2O3 3.907033, FeO 9.336806, MgO 36.375476, CaO 3.095572 wt%."""
    entry = {**warren_preferred_entry(), "project": "w05_ti_free", "database": "hp636", "excluded_oxides": ["TiO2"]}
    model = make_compositions.model_from_config_entry(entry)
    make_compositions.write_composition(model, outdir=tmp_path)

    document = json.loads((tmp_path / "w05_ti_free.json").read_text())
    normalized = document["composition_normalized"]
    expected = {"SiO2": 47.285113, "Al2O3": 3.907033, "FeO": 9.336806, "MgO": 36.375476, "CaO": 3.095572}
    for oxide, value in expected.items():
        assert normalized[oxide] == pytest.approx(value, abs=5e-7)
    assert normalized["TiO2"] == 0.0
    assert document["excluded_oxides"]["oxides"] == ["TiO2"]
    assert document["excluded_oxides"]["removed_raw_wt_percent"] == {"TiO2": 0.18}


def test_unknown_excluded_oxide_is_rejected() -> None:
    with pytest.raises(ValueError, match="unknown oxide"):
        make_compositions.model_from_config_entry({**warren_preferred_entry(), "excluded_oxides": ["Ti"]})
