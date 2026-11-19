from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, replace
from pathlib import Path

from planetary_eos_lab.core.config import DATABASES, register_custom_databases
from planetary_eos_lab.core.database_utils import get_database_components, get_source_only_oxides


BASE_DIR = Path(__file__).resolve().parent
DEFAULT_CONFIG = BASE_DIR / "configs" / "models.json"
OUTDIR = BASE_DIR / "compositions"

# Keep this order fixed. Use the same order when answering BUILD prompts.
# Extended to include all common rock-forming oxides supported by thermodynamic databases
OXIDE_ORDER = [
    "SiO2",
    "TiO2",
    "Al2O3",
    "Cr2O3",
    "FeO",
    "MnO",
    "NiO",
    "MgO",
    "CaO",
    "Na2O",
    "K2O",
    "P2O5",
    "H2O",
]

MODEL_STATUS = (
    "SURFACE PROXY SMOKE TEST ONLY: these near/far compositions are first-pass "
    "surface terrane proxies for pipeline testing, not final lunar mantle models."
)

# Status line and notes used for BSM compositions with model_scope
# 'bulk_silicate_body'. Distinguishes two sub-classes via the (optional)
# `composition_class` and `study_role` fields:
#   - published_bsm_reference   / primary_reference        -> BSM_REFERENCE_STATUS
#   - published_bsm_alternative / within_framework_sensitivity
#                                                          -> BSM_ALTERNATIVE_STATUS
# Both classes share the caveat that a BSM inventory is not automatically a
# homogeneous present-day mantle.
BSM_REFERENCE_STATUS = (
    "BULK SILICATE MOON reference composition: this record is a published "
    "global lunar silicate inventory after core formation. It is NOT "
    "automatically equivalent to a homogeneous present-day lunar mantle."
)
BSM_ALTERNATIVE_STATUS = (
    "BULK SILICATE MOON published alternative / within-framework "
    "sensitivity composition: this record is a published alternative row "
    "from a BSM reference paper and represents a within-framework "
    "sensitivity to that paper's preferred model. It is NOT an "
    "independent literature-level BSM estimate, and it is NOT "
    "automatically equivalent to a homogeneous present-day lunar mantle."
)
# Retained for backward compatibility with any external code that imported
# BSM_STATUS by name. New code should use BSM_REFERENCE_STATUS or
# BSM_ALTERNATIVE_STATUS explicitly.
BSM_STATUS = BSM_REFERENCE_STATUS

# Status line and notes used for models whose model_scope is 'mantle_candidate'
# (hybrid mixtures, IBC-derived oxide vectors, etc). Kept generic; specific
# derivations belong in the per-model composition_interpretation.
MANTLE_CANDIDATE_STATUS = (
    "MANTLE CANDIDATE composition: this record is a derived or hybridized "
    "lunar mantle scenario, not a published Bulk Silicate Moon inventory."
)

# `literature_proxy` flag semantics (module-wide contract):
#   True  -> the composition (or its numerical values) is derived from published
#            literature. Says NOTHING about scope: a `literature_proxy=True`
#            model may be a surface proxy, a BSM, a derived mantle, an IBC, etc.
#   False -> the composition was constructed ad-hoc (typically a user_defined
#            composition entered through the GUI or a placeholder).
# Do not use this flag to distinguish surface-proxy from mantle/BSM scope; use
# `scientific_status` and `model_scope` for that.


def _status_line_for_model(model: LunarComposition) -> str:
    """Return the top-line scope status string for a lunar composition.

    Resolution order:
    1. `composition_class` (most specific): distinguishes
       published_bsm_reference from published_bsm_alternative.
    2. `scientific_status` / `model_scope` fallback.
    3. Neutral summary for unrecognised scopes.
    """
    composition_class = getattr(model, "composition_class", "") or ""
    status = getattr(model, "scientific_status", "")
    scope = getattr(model, "model_scope", "")

    if composition_class == "published_bsm_reference":
        return BSM_REFERENCE_STATUS
    if composition_class == "published_bsm_alternative":
        return BSM_ALTERNATIVE_STATUS
    if composition_class == "surface_proxy":
        return MODEL_STATUS
    if status == "surface_proxy_smoke_test" or scope == "surface_terrane_proxy":
        return MODEL_STATUS
    if scope == "bulk_silicate_body":
        # Backward-compatible fallback for a BSM entry that predates the
        # composition_class field.
        return BSM_REFERENCE_STATUS
    if scope == "mantle_candidate":
        return MANTLE_CANDIDATE_STATUS
    return (
        f"Composition scope: {scope or 'unspecified'}; scientific status: "
        f"{status or 'unspecified'}. Review the composition_interpretation "
        "and source_note fields before scientific use."
    )


def _scope_specific_notes(model: LunarComposition) -> list[str]:
    """Return scope-specific notes appended to the JSON output.

    Preserves the strong surface-proxy warning for actual surface proxies.
    For BSM models, produces notes that correctly describe the composition
    as a published global silicate inventory (not a present-day mantle),
    and distinguishes published_bsm_reference from published_bsm_alternative.
    """
    composition_class = getattr(model, "composition_class", "") or ""
    study_role = getattr(model, "study_role", "") or ""
    status = getattr(model, "scientific_status", "")
    scope = getattr(model, "model_scope", "")

    bsm_present_day_caveat = (
        "Do not silently identify this Bulk Silicate Moon composition with "
        "a homogeneous present-day mantle: any workflow step that requires "
        "that identification must state the assumption explicitly."
    )

    if composition_class == "published_bsm_reference" or (
        not composition_class and scope == "bulk_silicate_body"
        and status != "surface_proxy_smoke_test"
        and getattr(model, "composition_class", "") != "published_bsm_alternative"
    ):
        role_note = (
            f"Study role: {study_role or 'primary_reference'}. This entry "
            "is a published primary BSM reference."
        )
        return [BSM_REFERENCE_STATUS, role_note, bsm_present_day_caveat]
    if composition_class == "published_bsm_alternative":
        role_note = (
            f"Study role: {study_role or 'within_framework_sensitivity'}. "
            "This entry is a published ALTERNATIVE row from a BSM paper; it "
            "represents a within-framework sensitivity to that paper's "
            "preferred model and must NOT be presented as an independent "
            "literature-level BSM estimate."
        )
        return [BSM_ALTERNATIVE_STATUS, role_note, bsm_present_day_caveat]
    if composition_class == "surface_proxy" or status == "surface_proxy_smoke_test" \
            or scope == "surface_terrane_proxy":
        return [
            MODEL_STATUS,
            (
                "These source oxides represent lunar surface/terrane proxies, "
                "not final lunar mantle compositions."
            ),
        ]
    if scope == "mantle_candidate":
        return [
            MANTLE_CANDIDATE_STATUS,
            (
                "This composition is a derived or hybridized mantle scenario "
                "and is excluded from the BSM reference set."
            ),
        ]
    return [
        (
            "Composition scope is not one of the recognised lunar categories "
            "(surface_terrane_proxy, bulk_silicate_body, mantle_candidate). "
            "Review the composition_interpretation and source_note fields."
        )
    ]

PERPLEX_BUILD_COMPONENTS = (
    ("Na2O", "NA2O"),
    ("MgO", "MGO"),
    ("Al2O3", "AL2O3"),
    ("SiO2", "SIO2"),
    ("CaO", "CAO"),
    ("FeO", "FEO"),
)
ACTIVE_BUILD_OXIDES = {oxide for oxide, _ in PERPLEX_BUILD_COMPONENTS}
SOURCE_ONLY_OXIDES = tuple(oxide for oxide in OXIDE_ORDER if oxide not in ACTIVE_BUILD_OXIDES)
OMITTED_OXIDE_THRESHOLD = 1.0e-12
DEFAULT_DATABASE = "stx21"
COMPONENT_COMPOSITION_BASIS = "perplex_components"
COMPONENT_COMPOSITION_KEYS = (
    "components_wt_percent",
    "elements_wt_percent",
    "perplex_components_wt_percent",
)


@dataclass(frozen=True)
class LunarComposition:
    project: str
    description: str
    raw_wt_percent: dict[str, float]
    source_note: str = MODEL_STATUS
    scientific_status: str = "surface_proxy_smoke_test"
    model_scope: str = "surface_terrane_proxy"
    planetprofile_readiness: str = "mechanically_exportable_not_scientifically_final"
    composition_interpretation: str = (
        "Average lunar surface terrane oxide composition used to test Perple_X and "
        "PlanetProfile table mechanics; not a sampled mantle composition."
    )
    literature_proxy: bool = True
    database: str = DEFAULT_DATABASE
    # Optional machine-readable role fields (introduced with the tracked BSM
    # catalogue). Defaulting to empty strings preserves backward compatibility
    # for any caller constructing LunarComposition without these fields.
    #   composition_class:
    #     "published_bsm_reference"    -> primary literature BSM (Hauri, Warren
    #                                     Preferred)
    #     "published_bsm_alternative"  -> published alternative row from a BSM
    #                                     paper (Warren Alt Model 5)
    #     "surface_proxy"              -> a lunar surface terrane average
    #     "" (default)                 -> unspecified; falls back to
    #                                     model_scope-based handling
    #   study_role:
    #     "primary_reference"          -> primary literature-level BSM in the
    #                                     reference set
    #     "within_framework_sensitivity"
    #                                  -> a within-paper sensitivity variant
    #                                     (must not be presented as
    #                                     independent literature uncertainty)
    #     "" (default)                 -> unspecified
    composition_class: str = ""
    study_role: str = ""


@dataclass(frozen=True)
class ComponentComposition:
    project: str
    description: str
    raw_wt_percent: dict[str, float]
    component_order: list[str]
    component_label: str = "component"
    source_note: str = "Component composition entered in the model config."
    scientific_status: str = "user_defined"
    model_scope: str = "icy_world_component_model"
    planetprofile_readiness: str = "not_assessed_for_planetprofile_science"
    composition_interpretation: str = (
        "User-defined Perple_X component composition. Review thermodynamic data, solution models, "
        "phase exclusions, and P-T grid before scientific use."
    )
    literature_proxy: bool = False
    database: str = DEFAULT_DATABASE


CompositionConfig = LunarComposition | ComponentComposition


def _recompute_mg_number(oxides: dict[str, float]) -> float | None:
    """Recompute Mg# = 100 * Mg / (Mg + Fe) in mol% from the wt% oxides.

    Uses molar masses M(MgO) = 40.30 g/mol and M(FeO) = 71.85 g/mol. Returns
    None when both FeO and MgO are zero (e.g., non-lunar user compositions).
    Rounds to 2 decimals.
    """
    mgo = float(oxides.get("MgO", 0.0) or 0.0)
    feo = float(oxides.get("FeO", 0.0) or 0.0)
    mg_mol = mgo / 40.30
    fe_mol = feo / 71.85
    total = mg_mol + fe_mol
    if total <= 0.0:
        return None
    return round(100.0 * mg_mol / total, 2)


def ordered_composition(composition: dict[str, float]) -> dict[str, float]:
    unknown = sorted(set(composition) - set(OXIDE_ORDER))
    if unknown:
        raise ValueError(f"Unknown oxide(s): {', '.join(unknown)}")
    return {oxide: float(composition.get(oxide, 0.0)) for oxide in OXIDE_ORDER}


def normalize_wt_percent(composition: dict[str, float]) -> dict[str, float]:
    ordered = ordered_composition(composition)
    total = sum(ordered.values())
    if total <= 0:
        raise ValueError("Composition total must be positive.")
    return {oxide: value * 100.0 / total for oxide, value in ordered.items()}


def ordered_component_composition(
    composition: dict[str, float],
    component_order: list[str],
) -> dict[str, float]:
    unknown = sorted(set(composition) - set(component_order))
    if unknown:
        raise ValueError(f"Unknown component(s): {', '.join(unknown)}")
    return {component: float(composition.get(component, 0.0)) for component in component_order}


def normalize_ordered_values(composition: dict[str, float]) -> dict[str, float]:
    total = sum(composition.values())
    if total <= 0:
        raise ValueError("Composition total must be positive.")
    return {key: value * 100.0 / total for key, value in composition.items()}


def component_order_for_entry(entry: dict, composition: dict[str, float], database: str) -> list[str]:
    configured = entry.get("component_order") or entry.get("element_order")
    if configured is not None:
        if not isinstance(configured, list) or not all(isinstance(item, str) for item in configured):
            raise ValueError("component_order must be a JSON list of strings.")
        return configured
    order = [component for _, component in build_components_for_database(database)]
    order.extend(sorted(component for component in composition if component not in order))
    return order


def config_base_dir(config_path: Path) -> Path:
    if config_path.parent.name == "configs":
        return config_path.parent.parent
    return config_path.parent


def resolve_path(value: str | Path, base_dir: Path = BASE_DIR) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    return (base_dir / path).resolve()


def resolve_database_name(database: str | None) -> str:
    name = database or DEFAULT_DATABASE
    if name not in DATABASES:
        available = ", ".join(sorted(DATABASES))
        raise ValueError(f"Unknown thermodynamic database '{name}'. Available: {available}")
    return name


def build_components_for_database(database: str) -> tuple[tuple[str, str], ...]:
    return get_database_components(resolve_database_name(database))


def write_composition(
    model: LunarComposition,
    outdir: Path = OUTDIR,
    database: str | None = None,
) -> None:
    database_name = resolve_database_name(database or model.database)
    db = DATABASES[database_name]
    build_components = build_components_for_database(database_name)
    source_only_oxides = get_source_only_oxides(database_name)
    outdir.mkdir(parents=True, exist_ok=True)
    raw = ordered_composition(model.raw_wt_percent)
    normalized = normalize_wt_percent(raw)
    omitted_oxides = omitted_oxides_from_default_build(raw, normalized, database=database_name)
    build_bulk_values = {
        oxide: normalized[oxide]
        for oxide, _ in build_components
    }

    build_metadata = {
        "database_name": database_name,
        "thermodynamic_database": db.database_file,
        "solution_model_file": db.solution_model_file,
        "active_components": [
            {"oxide": oxide, "component": component}
            for oxide, component in build_components
        ],
        "source_only_oxides": list(source_only_oxides),
        "bulk_values_normalized_wt_percent": build_bulk_values,
        "bulk_values_order": [component for _, component in build_components],
        "omitted_oxides": omitted_oxides,
        "omission_caveat": (
            f"The {database_name} BUILD profile passes only the active component list to "
            "Perple_X. Source-only oxides are retained for provenance and plotting but are "
            "not modeled by this thermodynamic setup unless the database, solution model, "
            "and BUILD template are changed together."
        ),
    }

    document = {
        "project": model.project,
        "description": model.description,
        "units": "wt%",
        "oxide_order": OXIDE_ORDER,
        "composition_raw": raw,
        "composition_normalized": normalized,
        "scientific_status": model.scientific_status,
        "composition_class": getattr(model, "composition_class", "") or "",
        "study_role": getattr(model, "study_role", "") or "",
        "model_scope": model.model_scope,
        "planetprofile_readiness": model.planetprofile_readiness,
        "composition_interpretation": model.composition_interpretation,
        "placeholder": False,
        "literature_proxy": model.literature_proxy,
        "source_note": model.source_note,
        "source_transformation": getattr(model, "_source_transformation", None),
        "excluded_oxides": getattr(model, "_excluded_oxides", None),
        "mg_number_recomputed_mol_percent": _recompute_mg_number(normalized),
        "perplex_build": build_metadata,
        "default_perplex_build": build_metadata,
        "omitted_oxides_from_build": omitted_oxides,
        "omitted_oxides_from_default_build": omitted_oxides,
        "notes": [
            *_scope_specific_notes(model),
            "Use normalized values in Perple_X BUILD unless you intentionally want unnormalized amounts.",
            "Fe is represented as FeO for the silicate component.",
            "Do not include native Fe, Ni, or Cu unless metallic phases and their elastic properties are intentionally modeled.",
            "KREEP/Th/U/K radiogenic effects should mostly be represented in PlanetProfile thermal/radiogenic parameters.",
            (
                f"The {db.database_file} Perple_X profile models "
                + ", ".join(component for _, component in build_components)
                + (
                    f"; {', '.join(source_only_oxides)} are retained as source-only oxides and omitted from BUILD."
                    if source_only_oxides
                    else "; no configured oxides are source-only for this profile."
                )
            ),
        ],
    }

    json_path = outdir / f"{model.project}.json"
    json_path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")

    values_path = outdir / f"{model.project}_bulk_values.txt"
    with values_path.open("w", encoding="utf-8") as handle:
        handle.write(" ".join(f"{build_bulk_values[oxide]:.8f}" for oxide, _ in build_components))
        handle.write("\n")

    summary_path = outdir / f"{model.project}_summary.txt"
    with summary_path.open("w", encoding="utf-8") as handle:
        handle.write(f"{model.project}\n")
        handle.write(f"{model.description}\n")
        handle.write(f"{_status_line_for_model(model)}\n\n")
        handle.write("Normalized oxide composition, wt%:\n")
        for oxide in OXIDE_ORDER:
            handle.write(f"{oxide:8s} {normalized[oxide]:10.5f}\n")
        handle.write(f"\nTotal: {sum(normalized.values()):.5f}\n")
        handle.write(f"\n{database_name} BUILD values, normalized wt%:\n")
        for oxide, component in build_components:
            handle.write(f"{component:8s} {normalized[oxide]:10.5f}\n")
        if omitted_oxides:
            handle.write(f"\nSource-only / omitted from {database_name} BUILD:\n")
            for item in omitted_oxides:
                handle.write(f"{item['oxide']:8s} {item['normalized_wt_percent']:10.5f}\n")

    print(f"Wrote {json_path}")
    print(f"Wrote {values_path}")
    print(f"Wrote {summary_path}")


def write_component_composition(
    model: ComponentComposition,
    outdir: Path = OUTDIR,
    database: str | None = None,
) -> None:
    database_name = resolve_database_name(database or model.database)
    db = DATABASES[database_name]
    build_components = build_components_for_database(database_name)
    outdir.mkdir(parents=True, exist_ok=True)
    raw = ordered_component_composition(model.raw_wt_percent, model.component_order)
    normalized = normalize_ordered_values(raw)
    build_bulk_values = {}
    missing = []
    for source_name, component in build_components:
        value = aliased_component_value(normalized, source_name, component)
        if value is None:
            missing.append(source_name)
        else:
            build_bulk_values[source_name] = value
    if missing:
        all_components = [comp for _, comp in build_components]
        provided_components = sorted(normalized.keys())
        available_databases = ", ".join(sorted(DATABASES.keys()))
        raise ValueError(
            f"Component composition for {model.project} is missing BUILD component(s): "
            f"{', '.join(missing)}\n\n"
            f"Your database '{database_name}' requires all these components:\n"
            f"  {', '.join(all_components)}\n\n"
            f"Your composition provides:\n"
            f"  {', '.join(provided_components)}\n\n"
            f"Solutions:\n"
            f"  1. Add the missing component(s) to components_wt_percent in your model\n"
            f"  2. Switch to a database that matches your composition\n"
            f"  3. Available databases: {available_databases}\n"
            f"  See docs/icy_worlds_guide.md for database selection guidance."
        )

    build_metadata = {
        "database_name": database_name,
        "thermodynamic_database": db.database_file,
        "solution_model_file": db.solution_model_file,
        "active_components": [
            {"source_name": source_name, "component": component}
            for source_name, component in build_components
        ],
        "bulk_values_normalized_wt_percent": build_bulk_values,
        "bulk_values_order": [component for _, component in build_components],
        "excluded_phases": list(db.excluded_phases),
        "solution_models": list(db.solution_models),
    }

    document = {
        "project": model.project,
        "description": model.description,
        "units": "wt%",
        "composition_basis": COMPONENT_COMPOSITION_BASIS,
        "component_label": model.component_label,
        "component_order": model.component_order,
        "composition_raw": raw,
        "composition_normalized": normalized,
        "scientific_status": model.scientific_status,
        "model_scope": model.model_scope,
        "planetprofile_readiness": model.planetprofile_readiness,
        "composition_interpretation": model.composition_interpretation,
        "placeholder": False,
        "literature_proxy": model.literature_proxy,
        "source_note": model.source_note,
        "perplex_build": build_metadata,
        "default_perplex_build": build_metadata,
        "omitted_oxides_from_build": [],
        "omitted_oxides_from_default_build": [],
        "notes": [
            "Use normalized values in Perple_X BUILD unless you intentionally want unnormalized amounts.",
            "This component composition is not an oxide GUI model; it is intended for element/volatile-bearing icy-world recipes.",
            "Check that the selected thermodynamic data file, solution model file, excluded phases, and P-T range match the intended science case.",
        ],
    }

    json_path = outdir / f"{model.project}.json"
    json_path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")

    values_path = outdir / f"{model.project}_bulk_values.txt"
    with values_path.open("w", encoding="utf-8") as handle:
        handle.write(" ".join(f"{build_bulk_values[source_name]:.8f}" for source_name, _ in build_components))
        handle.write("\n")

    summary_path = outdir / f"{model.project}_summary.txt"
    with summary_path.open("w", encoding="utf-8") as handle:
        handle.write(f"{model.project}\n")
        handle.write(f"{model.description}\n")
        handle.write(f"{model.source_note}\n\n")
        handle.write(f"Normalized {model.component_label} composition, wt%:\n")
        for component in model.component_order:
            handle.write(f"{component:8s} {normalized[component]:10.5f}\n")
        handle.write(f"\nTotal: {sum(normalized.values()):.5f}\n")
        handle.write(f"\n{database_name} BUILD values, normalized wt%:\n")
        for source_name, component in build_components:
            handle.write(f"{component:8s} {build_bulk_values[source_name]:10.5f}\n")

    print(f"Wrote {json_path}")
    print(f"Wrote {values_path}")
    print(f"Wrote {summary_path}")


def aliased_component_value(
    composition: dict[str, float],
    source_name: str,
    component: str,
) -> float | None:
    """Return a bulk value from either the oxide-style source name or Perple_X alias."""
    if source_name == component:
        return composition.get(source_name)
    source_present = source_name in composition
    component_present = component in composition
    if not source_present and not component_present:
        return None
    if source_present and not component_present:
        return composition[source_name]
    if component_present and not source_present:
        return composition[component]

    source_value = composition[source_name]
    component_value = composition[component]
    if abs(source_value) <= OMITTED_OXIDE_THRESHOLD and abs(component_value) > OMITTED_OXIDE_THRESHOLD:
        return component_value
    return source_value


def write_configured_composition(model: CompositionConfig, outdir: Path = OUTDIR) -> None:
    if isinstance(model, ComponentComposition):
        write_component_composition(model, outdir=outdir)
    else:
        write_composition(model, outdir=outdir)


def omitted_oxides_from_default_build(
    raw: dict[str, float],
    normalized: dict[str, float],
    database: str = DEFAULT_DATABASE,
) -> list[dict[str, float | str]]:
    database_name = resolve_database_name(database)
    active_oxides = {oxide for oxide, _ in build_components_for_database(database_name)}
    omitted: list[dict[str, float | str]] = []
    for oxide in OXIDE_ORDER:
        value = normalized[oxide]
        if oxide not in active_oxides and abs(value) > OMITTED_OXIDE_THRESHOLD:
            omitted.append(
                {
                    "oxide": oxide,
                    "raw_wt_percent": raw[oxide],
                    "normalized_wt_percent": value,
                    "reason": f"not_in_{database_name}_active_component_list",
                }
            )
    return omitted


def component_composition_from_config_entry(
    entry: dict,
    default_database: str = DEFAULT_DATABASE,
) -> ComponentComposition | None:
    composition = None
    for key in COMPONENT_COMPOSITION_KEYS:
        if key in entry:
            composition = entry[key]
            break
    if composition is None:
        return None
    if not isinstance(composition, dict):
        raise ValueError(f"Component composition for {entry.get('project', '<unknown>')} must be a JSON object.")

    project = entry.get("project")
    if not project:
        raise ValueError("Each inline component model must define a project name.")
    database_name = resolve_database_name(entry.get("database", default_database))
    return ComponentComposition(
        project=project,
        description=entry.get("description", project),
        raw_wt_percent=composition,
        component_order=component_order_for_entry(entry, composition, database_name),
        component_label=entry.get("component_label", "component"),
        source_note=entry.get("source_note", "Component composition entered in the model config."),
        scientific_status=entry.get("scientific_status", "user_defined"),
        model_scope=entry.get("model_scope", "icy_world_component_model"),
        planetprofile_readiness=entry.get(
            "planetprofile_readiness",
            "not_assessed_for_planetprofile_science",
        ),
        composition_interpretation=entry.get(
            "composition_interpretation",
            "User-defined Perple_X component composition; scientific interpretation was not provided in the config.",
        ),
        literature_proxy=bool(entry.get("literature_proxy", False)),
        database=database_name,
    )


def model_from_config_entry(
    entry: dict,
    default_database: str = DEFAULT_DATABASE,
) -> CompositionConfig | None:
    component_model = component_composition_from_config_entry(entry, default_database=default_database)
    if component_model is not None:
        return component_model

    composition = (
        entry.get("oxides_wt_percent")
        or entry.get("raw_wt_percent")
        or entry.get("composition_raw")
    )
    if composition is None:
        return None
    if not isinstance(composition, dict):
        raise ValueError(f"Composition for {entry.get('project', '<unknown>')} must be a JSON object.")

    project = entry.get("project")
    if not project:
        raise ValueError("Each inline composition model must define a project name.")
    excluded = [str(oxide) for oxide in entry.get("excluded_oxides", []) or []]
    unknown = sorted(set(excluded) - set(OXIDE_ORDER))
    if unknown:
        raise ValueError(f"excluded_oxides of {project}: unknown oxide(s) {', '.join(unknown)}")
    if excluded:
        removed = {oxide: float(composition.get(oxide, 0.0) or 0.0) for oxide in excluded}
        composition = {oxide: value for oxide, value in composition.items() if oxide not in excluded}
    lc = LunarComposition(
        project=project,
        description=entry.get("description", project),
        raw_wt_percent=composition,
        source_note=entry.get("source_note", MODEL_STATUS),
        scientific_status=entry.get("scientific_status", "user_defined"),
        model_scope=entry.get("model_scope", "user_defined"),
        planetprofile_readiness=entry.get(
            "planetprofile_readiness",
            "not_assessed_for_planetprofile_science",
        ),
        composition_interpretation=entry.get(
            "composition_interpretation",
            "User-defined oxide composition; scientific interpretation was not provided in the config.",
        ),
        literature_proxy=bool(entry.get("literature_proxy", False)),
        database=resolve_database_name(entry.get("database", default_database)),
        composition_class=str(entry.get("composition_class", "") or ""),
        study_role=str(entry.get("study_role", "") or ""),
    )
    # source_transformation is optional catalogue metadata (structured
    # provenance record). Attach as an object attribute; write_composition
    # will emit it verbatim into the generated JSON. Frozen dataclass -->
    # bypass __setattr__ with object.__setattr__.
    source_transformation = entry.get("source_transformation")
    if source_transformation is not None:
        object.__setattr__(lc, "_source_transformation", source_transformation)
    if excluded:
        object.__setattr__(lc, "_excluded_oxides", {
            "oxides": excluded,
            "removed_raw_wt_percent": removed,
            "method": "removed from the raw composition before normalization; the other oxides are renormalized to 100 wt%",
        })
    return lc


def models_from_config(
    config_path: Path,
    project: str | None = None,
    database_override: str | None = None,
) -> list[CompositionConfig]:
    if not config_path.exists():
        raise FileNotFoundError(
            f"Missing config file: {config_path}. Copy configs/models.example.json to configs/models.json "
            "and set perplex_dir to your local Perple_X install."
        )
    data = json.loads(config_path.read_text(encoding="utf-8"))
    register_custom_databases(data, config_base_dir(config_path))
    default_database = resolve_database_name(database_override or data.get("database", DEFAULT_DATABASE))
    models: list[CompositionConfig] = []
    for entry in data.get("models", []):
        if project and entry.get("project") != project:
            continue
        model = model_from_config_entry(entry, default_database=default_database)
        if model is not None:
            models.append(model)

    if project and not models:
        configured_projects = {entry.get("project") for entry in data.get("models", [])}
        if project in configured_projects:
            return []
        raise ValueError(f"Project not found in config: {project}")

    return models


def configured_or_default_models(
    config_path: Path,
    project: str | None = None,
    database_override: str | None = None,
) -> list[CompositionConfig]:
    if config_path.exists():
        models = models_from_config(config_path, project=project, database_override=database_override)
        data = json.loads(config_path.read_text(encoding="utf-8"))
        if models or data.get("models"):
            return models
    default_database = resolve_database_name(database_override)
    if project:
        selected = [model for model in lunar_models() if model.project == project]
        if not selected:
            raise ValueError(f"Project not found: {project}")
        return [replace(model, database=default_database) for model in selected]
    return [replace(model, database=default_database) for model in lunar_models()]


def lunar_models() -> list[CompositionConfig]:
    return [
        LunarComposition(
            project="moon_far_highlands_surface_proxy",
            description="Farside/highlands-like lunar surface terrane proxy based on published average highlands oxides",
            raw_wt_percent={
                "SiO2": 45.5,
                "TiO2": 0.60,
                "Al2O3": 24.0,
                "FeO": 5.90,
                "MgO": 7.50,
                "CaO": 15.90,
                "Na2O": 0.60,
                "K2O": 0.00,
                "P2O5": 0.00,
            },
            source_note=(
                "Major oxides use a commonly tabulated lunar highlands average surface composition "
                "(SiO2 45.5, Al2O3 24.0, CaO 15.9, FeO 5.9, MgO 7.5, TiO2 0.6, Na2O 0.6 wt%). "
                "Used here as a farside/highlands surface proxy; not a directly sampled mantle composition."
            ),
            composition_interpretation=(
                "Average highlands-like lunar surface oxide composition used to test the "
                "far-side end of a terrane contrast; it does not represent a final lunar mantle EOS composition."
            ),
        ),
        LunarComposition(
            project="moon_near_maria_surface_proxy",
            description="Nearside/maria-like lunar surface terrane proxy based on published average maria oxides",
            raw_wt_percent={
                "SiO2": 45.4,
                "TiO2": 3.90,
                "Al2O3": 14.9,
                "FeO": 14.1,
                "MgO": 9.20,
                "CaO": 11.8,
                "Na2O": 0.60,
                "K2O": 0.00,
                "P2O5": 0.00,
            },
            source_note=(
                "Major oxides use a commonly tabulated lunar maria average surface composition "
                "(SiO2 45.4, Al2O3 14.9, CaO 11.8, FeO 14.1, MgO 9.2, TiO2 3.9, Na2O 0.6 wt%). "
                "Used here as a nearside/maria surface proxy; PKT/KREEP heat-producing elements should be treated separately."
            ),
            composition_interpretation=(
                "Average maria-like lunar surface oxide composition used to test the near-side "
                "end of a terrane contrast; TiO2 is source-only in the default stx21 setup, "
                "so it is not a final Ti-bearing mantle EOS model."
            ),
        ),
    ]


def placeholder_models() -> list[CompositionConfig]:
    return lunar_models()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate normalized composition files.")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Path to models config.")
    parser.add_argument("--project", help="Generate only one project from the config.")
    parser.add_argument(
        "--database",
        help="Thermodynamic database to use instead of the config value (built-in or declared in custom_databases).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    config_path = resolve_path(args.config, BASE_DIR)
    models = configured_or_default_models(
        config_path,
        project=args.project,
        database_override=args.database,
    )
    if not models:
        print("No inline compositions to generate; using configured composition files as-is.")
        return
    wrote_lunar_proxy = False
    for model in models:
        outdir = resolve_path("compositions", config_base_dir(config_path))
        write_configured_composition(model, outdir=outdir)
        if isinstance(model, LunarComposition) and model.source_note == MODEL_STATUS:
            wrote_lunar_proxy = True
    if wrote_lunar_proxy:
        print("\nWARNING:", MODEL_STATUS)


if __name__ == "__main__":
    main()
