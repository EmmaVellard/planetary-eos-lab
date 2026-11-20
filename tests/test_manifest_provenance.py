from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

import export_planetprofile
from test_lunar_pipeline import make_config, make_fake_perplex, run_pipeline, write_executable


def run_export(tmp_path: Path) -> tuple[dict, Path, Path]:
    perplex_dir = make_fake_perplex(tmp_path)
    # Fake BUILD that prints the release banner real Perple_X BUILD prints.
    write_executable(
        perplex_dir / "bin" / "build",
        """
from pathlib import Path
import sys

project = sys.stdin.readline().strip()
Path(f"{project}.dat").write_text("fake dat\\n")
print("Perple_X release 7.2.5 June 1, 2026.")
""",
    )
    config_path, _ = make_config(tmp_path, perplex_dir)
    run_result = run_pipeline(config_path)
    assert run_result.returncode == 0, run_result.stderr + run_result.stdout

    export_dir = tmp_path / "export"
    assert export_planetprofile.main(["--config", str(config_path), "--planetprofile-export-dir", str(export_dir)]) == 0
    manifest_path = export_dir / "planetprofile_export_manifest.json"
    return json.loads(manifest_path.read_text()), export_dir, tmp_path / "build.in"


def test_manifest_records_reproducibility_provenance(tmp_path: Path) -> None:
    manifest, export_dir, build_template = run_export(tmp_path)

    assert manifest["schema_version"] == 3
    eos_lab = manifest["eos_lab"]
    if eos_lab["git_commit"] is None:
        assert eos_lab["git_dirty"] is None and eos_lab["git_unavailable_reason"]
    else:
        assert re.fullmatch(r"[0-9a-f]{40}", eos_lab["git_commit"])
        assert isinstance(eos_lab["git_dirty"], bool)

    table = manifest["tables"][0]
    assert table["perplex_version"] == "7.2.5"
    exported = export_dir / table["exported_filename"]
    assert table["exported_table_sha256"] == hashlib.sha256(exported.read_bytes()).hexdigest()
    assert table["build_template_sha256"] == hashlib.sha256(build_template.read_bytes()).hexdigest()
    assert table["perplex_dir"] == "fake_perplex"
    assert table["database_file"] == "fake_perplex/datafiles/stx21ver.dat"
    assert "export_destination" not in table


def test_manifest_contains_no_absolute_paths(tmp_path: Path) -> None:
    _, export_dir, _ = run_export(tmp_path)
    text = (export_dir / "planetprofile_export_manifest.json").read_text()

    assert str(tmp_path) not in text
    assert str(Path.home()) not in text
    assert str(export_planetprofile.run_perplex.BASE_DIR) not in text


def test_perplex_version_is_null_without_build_log(tmp_path: Path) -> None:
    model = type("Model", (), {"output_dir": tmp_path})()
    assert export_planetprofile.perplex_version(model) is None


def test_git_provenance_is_null_with_reason_outside_a_repository(tmp_path: Path) -> None:
    if subprocess.run(["git", "-C", str(tmp_path), "rev-parse"], capture_output=True).returncode == 0:
        return  # tmp_path sits inside a git work tree on this machine; nothing to check
    provenance = export_planetprofile.eos_lab_git_provenance(tmp_path)
    assert provenance["git_commit"] is None
    assert provenance["git_dirty"] is None
    assert provenance["git_unavailable_reason"]
