from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))
import make_compositions
import run_perplex

OXIDE_ORDER = tuple(make_compositions.OXIDE_ORDER)
ACTIVE_BUILD_COMPONENTS = tuple(run_perplex.PERPLEX_COMPONENTS)
ACTIVE_BUILD_OXIDES = {oxide for oxide, _ in ACTIVE_BUILD_COMPONENTS}
SOURCE_ONLY_OXIDES = tuple(oxide for oxide in OXIDE_ORDER if oxide not in ACTIVE_BUILD_OXIDES)
DEFAULT_SCIENTIFIC_STATUS = "surface_proxy_smoke_test"
DEFAULT_MODEL_SCOPE = "surface_terrane_proxy"
DEFAULT_PLANETPROFILE_READINESS = "mechanically_exportable_not_scientifically_final"


@dataclass(frozen=True)
class ModelValidation:
    errors: list[str]
    warnings: list[str]

    @property
    def ok(self) -> bool:
        return not self.errors


def composition_from_model(model: dict[str, Any]) -> dict[str, float]:
    composition = (
        model.get("oxides_wt_percent")
        or model.get("raw_wt_percent")
        or model.get("composition_raw")
        or {}
    )
    if not isinstance(composition, dict):
        raise ValueError("Composition must be a JSON object.")
    return {oxide: float(composition.get(oxide, 0.0)) for oxide in OXIDE_ORDER}


def validate_model_entry(model: dict[str, Any]) -> ModelValidation:
    errors: list[str] = []
    warnings: list[str] = []

    project = model.get("project")
    if not isinstance(project, str) or not project.strip():
        errors.append("Missing project name.")

    composition = (
        model.get("oxides_wt_percent")
        or model.get("raw_wt_percent")
        or model.get("composition_raw")
    )
    if composition is None:
        errors.append("Missing oxides_wt_percent composition.")
        composition = {}
    if not isinstance(composition, dict):
        errors.append("Composition must be a JSON object.")
        composition = {}

    unknown = sorted(set(composition) - set(OXIDE_ORDER))
    if unknown:
        errors.append(f"Unknown oxide(s): {', '.join(unknown)}.")

    total = 0.0
    for oxide in OXIDE_ORDER:
        value = composition.get(oxide, 0.0)
        try:
            total += float(value)
        except (TypeError, ValueError):
            errors.append(f"Non-numeric value for {oxide}.")

    if total <= 0 and not errors:
        errors.append("Composition total must be positive.")

    for key in ("scientific_status", "model_scope", "planetprofile_readiness"):
        if not model.get(key):
            warnings.append(f"Missing recommended metadata field: {key}.")

    return ModelValidation(errors=errors, warnings=warnings)


def normalize_composition(composition: dict[str, float]) -> dict[str, float]:
    return make_compositions.normalize_wt_percent(composition)


def normalized_model_composition(model: dict[str, Any]) -> dict[str, float]:
    return normalize_composition(composition_from_model(model))


def omitted_oxides_for_composition(composition: dict[str, float]) -> list[dict[str, float | str]]:
    raw = make_compositions.ordered_composition(composition)
    normalized = normalize_composition(raw)
    return make_compositions.omitted_oxides_from_default_build(raw, normalized)


def omitted_oxides_for_model(model: dict[str, Any]) -> list[dict[str, float | str]]:
    return omitted_oxides_for_composition(composition_from_model(model))


def oxide_table_rows(model: dict[str, Any]) -> list[dict[str, Any]]:
    raw = composition_from_model(model)
    normalized = normalize_composition(raw)
    omitted = {item["oxide"] for item in omitted_oxides_for_composition(raw)}
    return [
        {
            "oxide": oxide,
            "raw_wt_percent": raw[oxide],
            "normalized_wt_percent": normalized[oxide],
            "build_role": "modeled by default stx21 BUILD" if oxide in ACTIVE_BUILD_OXIDES else "source-only in default stx21",
            "active_in_default_build": oxide in ACTIVE_BUILD_OXIDES,
            "omitted_from_default_build": oxide in omitted,
        }
        for oxide in OXIDE_ORDER
    ]


def composition_plot_rows(model: dict[str, Any]) -> list[dict[str, Any]]:
    raw = composition_from_model(model)
    normalized = normalize_composition(raw)
    return [
        {
            "oxide": oxide,
            "raw_wt_percent": raw[oxide],
            "normalized_wt_percent": normalized[oxide],
        }
        for oxide in OXIDE_ORDER
    ]


def new_model_template(project: str) -> dict[str, Any]:
    safe_project = project.strip() or "new_surface_proxy"
    return {
        "project": safe_project,
        "description": "User-defined surface or composition proxy",
        "planetprofile_filename": f"{safe_project}_PerpleX.tab",
        "scientific_status": DEFAULT_SCIENTIFIC_STATUS,
        "model_scope": DEFAULT_MODEL_SCOPE,
        "planetprofile_readiness": DEFAULT_PLANETPROFILE_READINESS,
        "composition_interpretation": (
            "User-defined composition entered in the GUI. Review whether it represents "
            "a surface proxy, mantle candidate, or another scientific hypothesis before use."
        ),
        "literature_proxy": False,
        "source_note": "Entered through the Streamlit GUI.",
        "oxides_wt_percent": {oxide: 0.0 for oxide in OXIDE_ORDER},
    }


def raw_total(model: dict[str, Any]) -> float:
    return sum(composition_from_model(model).values())


def use_as_final_moon_mantle_eos(model: dict[str, Any]) -> bool:
    readiness = str(model.get("planetprofile_readiness", "")).lower()
    status = str(model.get("scientific_status", "")).lower()
    return readiness == "publication_ready" and status == "publication_ready"


def scientific_guardrail_text(model: dict[str, Any]) -> str:
    omitted = omitted_oxides_for_model(model)
    omitted_names = ", ".join(str(item["oxide"]) for item in omitted) or "none"
    return (
        f"Scientific status: {model.get('scientific_status', 'unknown')}\n"
        f"PlanetProfile readiness: {model.get('planetprofile_readiness', 'unknown')}\n"
        f"Source-only oxides in default stx21 BUILD: {', '.join(SOURCE_ONLY_OXIDES)}\n"
        f"Nonzero omitted oxides: {omitted_names}\n"
        f"Use as final Moon mantle EOS: {'yes' if use_as_final_moon_mantle_eos(model) else 'no'}"
    )
