from __future__ import annotations

import json
from pathlib import Path

import make_compositions
import run_perplex
from planetary_eos_lab.core.database_utils import get_database_components


def test_fe5s_core_build_input_matches_the_planetprofile_setup(tmp_path: Path) -> None:
    """PlanetProfile's 95Fe5S_core.dat (input_data_v686): se15ver.dat, components S and Fe by mass,
    solution models Po(SE) and FeS_liq, 40000-90000 bar, 500-2000 K."""
    entry = {"project": "fe95s5_core", "database": "se15_fes_core", "components_wt_percent": {"Fe": 95.0, "S": 5.0}}
    make_compositions.write_configured_composition(make_compositions.model_from_config_entry(entry), outdir=tmp_path)
    model = run_perplex.ModelConfig(
        project="fe95s5_core", composition_file=tmp_path / "fe95s5_core.json",
        build_input_file=run_perplex.default_build_template_for_database("se15_fes_core"),
        output_dir=tmp_path, work_dir=tmp_path, database="se15_fes_core",
    )
    rendered = run_perplex.render_build_input(tmp_path / "perplex", model)

    assert get_database_components("se15_fes_core") == (("S", "S"), ("Fe", "Fe"))
    assert "/datafiles/se15ver.dat\n" in rendered
    assert "\nS\nFe\n\n" in rendered
    assert "\n40000 90000\n500 2000\n" in rendered
    assert "\n5.00000000 95.00000000\n" in rendered
    assert "\nPo(SE)\nFeS_liq\n\n" in rendered
    assert json.loads((tmp_path / "fe95s5_core.json").read_text())["project"] == "fe95s5_core"


def test_core_werami_answers_skip_the_liquid_and_the_default_grid_is_sampled() -> None:
    # The Fe-S liquid makes WERAMI ask whether to include fluids: the answer after "1" must be "n".
    assert run_perplex.default_werami_sequence_for_database("se15_fes_core")[:4] == ("2", "38", "1", "n")
    # With sample_on_grid F, WERAMI asks for grid nodes, which the default answers do not provide.
    assert run_perplex.DEFAULT_PERPLEX_OPTIONS.sample_on_grid is True
    assert "sample_on_grid T" in run_perplex.render_perplex_option_text()


def test_phase_mode_answers_include_the_fluid_question_where_werami_asks_it() -> None:
    assert run_perplex.phase_modes_sequence_for_database("stx24") == ("2", "25", "n", "n", "1", "0")
    for database in ("hp633", "hp636", "se15_fes_core"):
        assert run_perplex.phase_modes_sequence_for_database(database) == ("2", "25", "n", "y", "n", "1", "0")
