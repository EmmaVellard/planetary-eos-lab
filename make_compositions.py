from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, replace
from pathlib import Path

from planetary_eos_lab.core.config import DATABASES
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
        "model_scope": model.model_scope,
        "planetprofile_readiness": model.planetprofile_readiness,
        "composition_interpretation": model.composition_interpretation,
        "placeholder": False,
        "literature_proxy": model.literature_proxy,
        "source_note": model.source_note,
        "perplex_build": build_metadata,
        "default_perplex_build": build_metadata,
        "omitted_oxides_from_build": omitted_oxides,
        "omitted_oxides_from_default_build": omitted_oxides,
        "notes": [
            MODEL_STATUS,
            "Use normalized values in Perple_X BUILD unless you intentionally want unnormalized amounts.",
            "These source oxides represent lunar surface/terrane proxies, not final lunar mantle compositions.",
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
        handle.write(f"{MODEL_STATUS}\n\n")
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
    return LunarComposition(
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
    )


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
        choices=sorted(DATABASES),
        help="Thermodynamic database profile to use instead of the config value.",
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
