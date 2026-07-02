"""Utilities for working with different thermodynamic databases."""
from __future__ import annotations

from pathlib import Path

from planetary_eos_lab.core.config import DATABASES
from planetary_eos_lab.core.constants import OXIDE_ORDER


def get_database_components(database_name: str) -> tuple[tuple[str, str], ...]:
    """Get the oxide-to-component mapping for a database.

    Args:
        database_name: Name of the database (e.g., "stx21", "hp633")

    Returns:
        Tuple of (oxide, component) pairs

    Raises:
        ValueError: If database is unknown
    """
    if database_name not in DATABASES:
        raise ValueError(f"Unknown database: {database_name}")

    if database_name == "stx21":
        return (
            ("Na2O", "NA2O"),
            ("MgO", "MGO"),
            ("Al2O3", "AL2O3"),
            ("SiO2", "SIO2"),
            ("CaO", "CAO"),
            ("FeO", "FEO"),
        )

    elif database_name == "hp633":
        # Match the component names declared by hp633ver.dat. It does not declare P2O5.
        return (
            ("Na2O", "Na2O"),
            ("MgO", "MgO"),
            ("Al2O3", "Al2O3"),
            ("SiO2", "SiO2"),
            ("K2O", "K2O"),
            ("CaO", "CaO"),
            ("TiO2", "TiO2"),
            ("FeO", "FeO"),
        )

    # Default: return stx21 components
    return get_database_components("stx21")


def get_active_oxides(database_name: str) -> set[str]:
    """Get oxides that are modeled by the database.

    Args:
        database_name: Name of the database

    Returns:
        Set of oxide names
    """
    components = get_database_components(database_name)
    return {oxide for oxide, _ in components}


def get_source_only_oxides(database_name: str) -> tuple[str, ...]:
    """Get oxides that are tracked but not modeled.

    Args:
        database_name: Name of the database

    Returns:
        Tuple of oxide names
    """
    active = get_active_oxides(database_name)
    return tuple(oxide for oxide in OXIDE_ORDER if oxide not in active)


def format_bulk_components(
    composition: dict[str, float],
    database_name: str,
) -> str:
    """Format composition as BUILD bulk component string.

    Args:
        composition: Normalized oxide composition
        database_name: Name of the database

    Returns:
        Space-separated string of component values
    """
    components = get_database_components(database_name)

    values = []
    for oxide, _ in components:
        value = composition.get(oxide, 0.0)
        values.append(f"{value:.8f}")

    return " ".join(values)


def describe_database(database_name: str) -> str:
    """Get human-readable description of database capabilities.

    Args:
        database_name: Name of the database

    Returns:
        Description string
    """
    if database_name not in DATABASES:
        return f"Unknown database: {database_name}"

    db = DATABASES[database_name]
    active = get_active_oxides(database_name)
    source_only = get_source_only_oxides(database_name)

    lines = [
        f"Database: {db.name}",
        f"File: {db.database_file}",
        f"Description: {db.description}",
        "",
        f"Modeled oxides: {', '.join(sorted(active))}",
    ]

    if source_only:
        lines.append(f"Source-only oxides: {', '.join(source_only)}")

    lines.append("")
    lines.append(f"Excluded phases: {', '.join(db.excluded_phases) or 'none'}")
    lines.append(f"Solution models: {', '.join(db.solution_models)}")

    pt = db.pt_range
    lines.append("")
    lines.append(f"Default P range: {pt['pressure_bar']['min']:.0f}–{pt['pressure_bar']['max']:.0f} bar")
    lines.append(f"Default T range: {pt['temperature_k']['min']:.0f}–{pt['temperature_k']['max']:.0f} K")

    return "\n".join(lines)


def list_available_databases() -> list[str]:
    """List all available database names.

    Returns:
        List of database names
    """
    return list(DATABASES.keys())


def validate_database_files(perplex_dir: Path, database_name: str) -> tuple[bool, list[str]]:
    """Validate that database files exist.

    Args:
        perplex_dir: Perple_X installation directory
        database_name: Name of the database

    Returns:
        Tuple of (all_valid, error_messages)
    """
    if database_name not in DATABASES:
        return False, [f"Unknown database: {database_name}"]

    db = DATABASES[database_name]
    datafiles_dir = perplex_dir / "datafiles"
    errors = []

    # Check datafiles directory
    if not datafiles_dir.exists():
        errors.append(f"Datafiles directory not found: {datafiles_dir}")
        return False, errors

    # Check database file
    db_file = datafiles_dir / db.database_file
    if not db_file.exists():
        errors.append(f"Database file not found: {db_file}")

    # Check solution model file
    sol_file = datafiles_dir / db.solution_model_file
    if not sol_file.exists():
        errors.append(f"Solution model file not found: {sol_file}")

    return len(errors) == 0, errors
