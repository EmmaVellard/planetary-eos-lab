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
        # Match the component names declared by hp633ver.dat
        # Includes all common rock-forming oxides
        # Does not include P2O5 (not declared by hp633ver.dat)
        return (
            ("SiO2", "SiO2"),
            ("TiO2", "TiO2"),
            ("Al2O3", "Al2O3"),
            ("Cr2O3", "Cr2O3"),
            ("FeO", "FeO"),
            ("MnO", "MnO"),
            ("NiO", "NiO"),
            ("MgO", "MgO"),
            ("CaO", "CaO"),
            ("Na2O", "Na2O"),
            ("K2O", "K2O"),
            ("H2O", "H2O"),
        )

    elif database_name == "dew17_hhph":
        # DEW17 element-based database - includes transition metals
        return (
            ("H2", "H2"),
            ("C", "C"),
            ("Mg", "Mg"),
            ("Al", "Al"),
            ("Si", "Si"),
            ("S2", "S2"),
            ("Ca", "Ca"),
            ("Ti", "Ti"),
            ("Mn", "Mn"),
            ("Fe", "Fe"),
            ("Ni", "Ni"),
            ("O2", "O2"),
        )

    elif database_name == "hpha02_hydrous":
        # Uses HP02 oxide system with basic rock-forming oxides + H2O
        # First element is standard oxide name, second is Perple_X component name (uppercase for HP databases)
        # Basic version includes: SiO2, Al2O3, FeO, MgO, CaO, Na2O, H2O
        # Does not include: P2O5, Cr2O3, MnO, NiO, TiO2, K2O (not in basic hpha02ver.dat)
        return (
            ("SiO2", "SIO2"),
            ("Al2O3", "AL2O3"),
            ("FeO", "FEO"),
            ("MgO", "MGO"),
            ("CaO", "CAO"),
            ("Na2O", "NA2O"),
            ("H2O", "H2O"),
        )

    elif database_name == "dew13_hydrous":
        return (
            ("H2", "H2"),
            ("C", "C"),
            ("Mg", "Mg"),
            ("Si", "Si"),
            ("S2", "S2"),
            ("Fe", "Fe"),
            ("O2", "O2"),
        )

    elif database_name == "dew17_comet":
        return (
            ("H2", "H2"),
            ("O2", "O2"),
            ("C", "C"),
            ("Fe", "Fe"),
            ("Si", "Si"),
            ("Mg", "Mg"),
            ("N2", "N2"),
            ("S2", "S2"),
        )

    # Should not be reached because DATABASES validation happens above.
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
    if not active.intersection(OXIDE_ORDER):
        return ()
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
        f"Modeled components/oxides: {', '.join(sorted(active))}",
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
