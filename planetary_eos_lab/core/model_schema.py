from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import make_compositions
import run_perplex

from planetary_eos_lab.core.database_utils import (
    get_active_oxides,
    get_database_components,
    get_source_only_oxides,
)

OXIDE_ORDER = tuple(make_compositions.OXIDE_ORDER)
# Legacy constants for backward compatibility (stx21 defaults)
ACTIVE_BUILD_COMPONENTS = tuple(run_perplex.PERPLEX_COMPONENTS)
ACTIVE_BUILD_OXIDES = {oxide for oxide, _ in ACTIVE_BUILD_COMPONENTS}
SOURCE_ONLY_OXIDES = tuple(oxide for oxide in OXIDE_ORDER if oxide not in ACTIVE_BUILD_OXIDES)

DEFAULT_SCIENTIFIC_STATUS = "surface_proxy_smoke_test"
DEFAULT_MODEL_SCOPE = "surface_terrane_proxy"
DEFAULT_PLANETPROFILE_READINESS = "mechanically_exportable_not_scientifically_final"
COMPONENT_COMPOSITION_KEYS = (
    "components_wt_percent",
    "elements_wt_percent",
    "perplex_components_wt_percent",
)


def component_composition_from_model(model: dict[str, Any]) -> dict[str, float] | None:
    for key in COMPONENT_COMPOSITION_KEYS:
        value = model.get(key)
        if value is not None:
            if not isinstance(value, dict):
                raise ValueError("Component composition must be a JSON object.")
            return {str(component): float(amount) for component, amount in value.items()}
    return None


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

    try:
        component_composition = component_composition_from_model(model)
    except (TypeError, ValueError):
        component_composition = None
        errors.append("Component composition must contain numeric values.")
    if component_composition is not None:
        if sum(component_composition.values()) <= 0:
            errors.append("Component composition total must be positive.")
        for key in ("scientific_status", "model_scope", "planetprofile_readiness"):
            if not model.get(key):
                warnings.append(f"Missing recommended metadata field: {key}.")
        return ModelValidation(errors=errors, warnings=warnings)

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


def omitted_oxides_for_composition(
    composition: dict[str, float],
    database: str = "stx21",
) -> list[dict[str, float | str]]:
    raw = make_compositions.ordered_composition(composition)
    normalized = normalize_composition(raw)
    return make_compositions.omitted_oxides_from_default_build(raw, normalized, database=database)


def omitted_oxides_for_model(
    model: dict[str, Any],
    database: str = "stx21",
) -> list[dict[str, float | str]]:
    if component_composition_from_model(model) is not None:
        return []
    return omitted_oxides_for_composition(composition_from_model(model), database=database)


def oxide_table_rows(model: dict[str, Any], database: str = "stx21") -> list[dict[str, Any]]:
    """Generate oxide table rows for a model, database-aware.

    Args:
        model: Model configuration dictionary
        database: Database name (default: "stx21")

    Returns:
        List of dictionaries with oxide information
    """
    raw = composition_from_model(model)
    normalized = normalize_composition(raw)
    omitted = {item["oxide"] for item in omitted_oxides_for_composition(raw, database=database)}
    active_oxides = get_active_oxides(database)

    return [
        {
            "oxide": oxide,
            "raw_wt_percent": raw[oxide],
            "normalized_wt_percent": normalized[oxide],
            "build_role": f"modeled by {database} BUILD" if oxide in active_oxides else f"source-only in {database}",
            "active_in_default_build": oxide in active_oxides,
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


def scientific_guardrail_text(model: dict[str, Any], database: str = "stx21") -> str:
    """Generate scientific guardrail text for a model, database-aware.

    Args:
        model: Model configuration dictionary
        database: Database name (default: "stx21")

    Returns:
        Formatted guardrail text
    """
    component_composition = component_composition_from_model(model)
    if component_composition is not None:
        active_components = ", ".join(component for _, component in get_database_components(database))
        return (
            f"Scientific status: {model.get('scientific_status', 'unknown')}\n"
            f"PlanetProfile readiness: {model.get('planetprofile_readiness', 'unknown')}\n"
            "Composition basis: Perple_X components\n"
            f"Input component total: {sum(component_composition.values()):.2f} wt%\n"
            f"BUILD components in {database}: {active_components}\n"
            "Use as final scientific EOS: no"
        )

    omitted = omitted_oxides_for_model(model, database=database)
    omitted_names = ", ".join(str(item["oxide"]) for item in omitted) or "none"
    source_only = get_source_only_oxides(database)

    return (
        f"Scientific status: {model.get('scientific_status', 'unknown')}\n"
        f"PlanetProfile readiness: {model.get('planetprofile_readiness', 'unknown')}\n"
        f"Source-only oxides in {database} BUILD: {', '.join(source_only) if source_only else 'none'}\n"
        f"Nonzero omitted oxides: {omitted_names}\n"
        f"Use as final scientific EOS: {'yes' if use_as_final_moon_mantle_eos(model) else 'no'}"
    )
