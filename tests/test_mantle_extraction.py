from __future__ import annotations

import json
from pathlib import Path

import pytest

import make_compositions

CATALOGUE = Path(__file__).resolve().parents[1] / "configs" / "lunar_bsm_models.json"

# Taylor (1999), "The Moon", Encyclopedia of the Solar System, Table III, Highlands;
# Cr2O3 and MnO converted from Cr 800 ppm and Mn 570 ppm (as in lunar-bsm-interior-models,
# scripts/stage_e3/e3_chemistry.py).
TAYLOR_1999_HIGHLANDS = {
    "SiO2": 45.0, "TiO2": 0.56, "Al2O3": 24.6, "FeO": 6.6, "MgO": 6.8, "CaO": 15.8,
    "Na2O": 0.45, "K2O": 0.03, "Cr2O3": 0.1169, "MnO": 0.0736,
}
# f_crust and residual mantle of Warren Preferred with crust architecture A, from
# lunar-bsm-interior-models results/stage_e3_m1/M1_COMPOSITIONS_FULL.csv
# (row moon_w05_preferred_M1A_stx24_unified, 2 September 2026).
F_CRUST_A = 0.05680851535394975
WARREN_M1A = {
    "SiO2": 47.01963933352659, "TiO2": 0.15754745758679578, "Al2O3": 2.6310109689943033,
    "FeO": 9.420925340953733, "MnO": 0.13583017043774712, "MgO": 37.84376585108638,
    "CaO": 2.3001770944146256, "Na2O": 0.027096761374314576, "K2O": 0.00350659323103949,
    "Cr2O3": 0.46050042839447103,
}


def warren_published() -> dict:
    models = json.loads(CATALOGUE.read_text())["models"]
    entry = next(m for m in models if m["project"] == "moon_w05_preferred_bsm")
    return entry["source_transformation"]["source_oxides_wt_percent"]


def test_residual_mantle_reproduces_the_lunar_study_m1_composition() -> None:
    mantle = make_compositions.residual_mantle_composition(warren_published(), TAYLOR_1999_HIGHLANDS, F_CRUST_A)
    for oxide, value in WARREN_M1A.items():
        assert mantle[oxide] == pytest.approx(value, abs=1e-6), oxide
    assert sum(mantle.values()) == pytest.approx(100.0, abs=1e-9)


def test_mantle_extraction_in_a_model_entry_writes_its_provenance(tmp_path: Path) -> None:
    entry = {
        "project": "w05_mantle",
        "oxides_wt_percent": warren_published(),
        "scientific_status": "literature_based",
        "model_scope": "bulk_silicate_body",
        "composition_class": "published_bsm_reference",
        "mantle_extraction": {
            "crust_oxides_wt_percent": TAYLOR_1999_HIGHLANDS,
            "crust_mass_fraction": F_CRUST_A,
            "crust_source": "Taylor (1999), Highlands",
        },
        "excluded_oxides": ["TiO2"],
    }
    model = make_compositions.model_from_config_entry(entry)
    make_compositions.write_composition(model, outdir=tmp_path)
    document = json.loads((tmp_path / "w05_mantle.json").read_text())

    assert document["model_scope"] == "mantle_candidate"
    assert document["composition_class"] == "residual_mantle_after_crust_extraction"
    provenance = document["mantle_extraction"]
    assert provenance["crust_mass_fraction"] == F_CRUST_A
    assert provenance["crust_source"] == "Taylor (1999), Highlands"
    assert provenance["mantle_wt_percent_before_exclusions"]["TiO2"] == pytest.approx(WARREN_M1A["TiO2"], abs=1e-9)
    # the mass balance is done before TiO2 is dropped, as in the lunar study
    expected_si = WARREN_M1A["SiO2"] * 100.0 / (100.0 - WARREN_M1A["TiO2"])
    assert document["composition_normalized"]["SiO2"] == pytest.approx(expected_si, abs=1e-9)
    assert document["composition_normalized"]["TiO2"] == 0.0


@pytest.mark.parametrize(
    ("crust", "f", "message"),
    [
        ({"SiO2": 40.0, "Al2O3": 60.0}, 0.2, "negative"),
        ({"SiO2": 100.0}, 1.0, "between 0 and 1"),
        ({"Si": 100.0}, 0.1, "Unknown oxide"),
    ],
)
def test_impossible_extractions_are_rejected(crust: dict, f: float, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        make_compositions.residual_mantle_composition(warren_published(), crust, f)


def test_gui_helpers_build_a_derived_entry_and_add_the_catalogue_once() -> None:
    from planetary_eos_lab.core.config_io import add_missing_model_entries, derived_mantle_entry

    catalogue = json.loads(CATALOGUE.read_text())["models"]
    config = {"models": [{"project": "moon_h15_lowFe", "oxides_wt_percent": {"SiO2": 1.0}}]}
    updated, added = add_missing_model_entries(config, catalogue)
    assert added == [m["project"] for m in catalogue if m["project"] != "moon_h15_lowFe"]
    assert updated["models"][0] == config["models"][0]  # existing entry untouched
    assert add_missing_model_entries(updated, catalogue)[1] == []

    source = next(m for m in catalogue if m["project"] == "moon_w05_preferred_bsm")
    entry = derived_mantle_entry(source, "w05_mantle", {**TAYLOR_1999_HIGHLANDS, "NiO": 0.0}, F_CRUST_A, "Taylor (1999)")
    # the full published composition is used, then the catalogue's dropped oxides are dropped again
    assert entry["oxides_wt_percent"] == warren_published()
    assert entry["excluded_oxides"] == source["source_transformation"]["excluded_oxides"]
    assert "NiO" not in entry["mantle_extraction"]["crust_oxides_wt_percent"]
    model = make_compositions.model_from_config_entry(entry)
    assert model.model_scope == "mantle_candidate"
    for oxide in ("SiO2", "TiO2", "Al2O3", "FeO", "MgO", "CaO"):
        retained = ("SiO2", "TiO2", "Al2O3", "FeO", "MgO", "CaO")
        expected = WARREN_M1A[oxide] * 100.0 / sum(WARREN_M1A[o] for o in retained)
        assert model.raw_wt_percent[oxide] * 100.0 / sum(model.raw_wt_percent.values()) == pytest.approx(expected, abs=1e-9)
