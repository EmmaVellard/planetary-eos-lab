from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONFIG_PATH = REPO_ROOT / "configs" / "models.json"
EXAMPLE_CONFIG_PATH = REPO_ROOT / "configs" / "models.example.json"


def resolve_path(value: str | Path, base_dir: Path = REPO_ROOT) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return (base_dir / path).resolve()


def config_base_dir(config_path: str | Path) -> Path:
    path = resolve_path(config_path)
    if path.parent.name == "configs":
        return path.parent.parent
    return path.parent


def load_config_json(config_path: str | Path = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    path = resolve_path(config_path)
    return json.loads(path.read_text(encoding="utf-8"))


def load_example_config_json() -> dict[str, Any]:
    return load_config_json(EXAMPLE_CONFIG_PATH)


def save_config_json(config_path: str | Path, data: dict[str, Any]) -> Path:
    path = resolve_path(config_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    return path


def copy_example_config(destination: str | Path = DEFAULT_CONFIG_PATH) -> Path:
    data = load_example_config_json()
    return save_config_json(destination, data)


def list_model_entries(config: dict[str, Any]) -> list[dict[str, Any]]:
    models = config.get("models", [])
    if not isinstance(models, list):
        return []
    return [model for model in models if isinstance(model, dict)]


def replace_model_entry(config: dict[str, Any], project: str, replacement: dict[str, Any]) -> dict[str, Any]:
    updated = deepcopy(config)
    models = updated.setdefault("models", [])
    if not isinstance(models, list):
        raise ValueError("Config field 'models' must be a list.")
    for index, model in enumerate(models):
        if isinstance(model, dict) and model.get("project") == project:
            models[index] = replacement
            return updated
    models.append(replacement)
    return updated


LUNAR_BSM_CATALOGUE_PATH = REPO_ROOT / "configs" / "lunar_bsm_models.json"
OXIDE_COMPOSITION_KEYS = ("oxides_wt_percent", "raw_wt_percent", "composition_raw")


def add_missing_model_entries(config: dict[str, Any], entries: list[dict[str, Any]]) -> tuple[dict[str, Any], list[str]]:
    """Append the entries whose project is not in the config yet; existing ones are left untouched."""
    updated = deepcopy(config)
    models = updated.setdefault("models", [])
    if not isinstance(models, list):
        raise ValueError("Config field 'models' must be a list.")
    existing = {model.get("project") for model in models if isinstance(model, dict)}
    added = []
    for entry in entries:
        if entry.get("project") and entry["project"] not in existing:
            models.append(deepcopy(entry))
            existing.add(entry["project"])
            added.append(entry["project"])
    return updated, added


def derived_mantle_entry(
    source: dict[str, Any],
    project: str,
    crust_oxides_wt_percent: dict[str, float],
    crust_mass_fraction: float,
    crust_source: str,
) -> dict[str, Any]:
    """A new model entry: the source composition with a mantle_extraction block (see make_compositions).

    When the source records its published composition (source_transformation, as in the
    lunar BSM catalogue), the extraction starts from that full composition and the oxides
    the catalogue dropped are dropped again afterwards, so the mass balance is not done on
    a truncated basis.
    """
    transformation = source.get("source_transformation") or {}
    bulk = transformation.get("source_oxides_wt_percent") or next(
        (source[key] for key in OXIDE_COMPOSITION_KEYS if isinstance(source.get(key), dict)), None
    )
    excluded = list(dict.fromkeys([*transformation.get("excluded_oxides", []), *source.get("excluded_oxides", [])]))
    if bulk is None:
        raise ValueError(f"{source.get('project', 'source model')} has no oxide composition to extract a mantle from.")
    entry = {key: deepcopy(value) for key, value in source.items() if key not in OXIDE_COMPOSITION_KEYS}
    entry.update({
        "project": project,
        "description": f"Mantle of {source.get('project', 'the source composition')} after extracting a crust "
                       f"({crust_source}, f = {crust_mass_fraction:g})",
        "oxides_wt_percent": deepcopy(bulk),
        "mantle_extraction": {
            "crust_oxides_wt_percent": {k: float(v) for k, v in crust_oxides_wt_percent.items() if float(v)},
            "crust_mass_fraction": float(crust_mass_fraction),
            "crust_source": crust_source,
        },
        "planetprofile_filename": f"{project}_PerpleX.tab",
    })
    if excluded:
        entry["excluded_oxides"] = excluded
    entry.pop("source_transformation", None)
    entry["derived_from"] = source.get("project", "")
    for key in ("composition_file", "output_dir", "work_dir"):
        entry.pop(key, None)
    return entry


def delete_model_entry(config: dict[str, Any], project: str) -> dict[str, Any]:
    return delete_model_entries(config, [project])


def delete_model_entries(config: dict[str, Any], projects: list[str]) -> dict[str, Any]:
    updated = deepcopy(config)
    models = updated.setdefault("models", [])
    if not isinstance(models, list):
        raise ValueError("Config field 'models' must be a list.")
    project_set = set(projects)
    updated["models"] = [
        model
        for model in models
        if not (isinstance(model, dict) and model.get("project") in project_set)
    ]
    return updated


def update_perplex_dir(config: dict[str, Any], perplex_dir: str) -> dict[str, Any]:
    updated = deepcopy(config)
    updated["perplex_dir"] = perplex_dir
    return updated
