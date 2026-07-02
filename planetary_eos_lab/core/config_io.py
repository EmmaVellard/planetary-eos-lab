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
