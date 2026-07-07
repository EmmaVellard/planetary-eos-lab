"""Constants used throughout Planetary EOS Lab."""
from __future__ import annotations

from typing import Final

# Oxide ordering - must match BUILD input order
# Extended to include all common rock-forming oxides supported by thermodynamic databases
OXIDE_ORDER: Final[tuple[str, ...]] = (
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
)

# Perple_X component mapping (oxide name -> Perple_X component name)
PERPLEX_COMPONENTS: Final[tuple[tuple[str, str], ...]] = (
    ("Na2O", "NA2O"),
    ("MgO", "MGO"),
    ("Al2O3", "AL2O3"),
    ("SiO2", "SIO2"),
    ("CaO", "CAO"),
    ("FeO", "FEO"),
)

# Active oxides that are modeled by default stx21 BUILD
ACTIVE_BUILD_OXIDES: Final[set[str]] = {oxide for oxide, _ in PERPLEX_COMPONENTS}

# Source-only oxides (tracked but not passed to BUILD by default)
SOURCE_ONLY_OXIDES: Final[tuple[str, ...]] = tuple(
    oxide for oxide in OXIDE_ORDER if oxide not in ACTIVE_BUILD_OXIDES
)

# Validation constants
OMITTED_OXIDE_THRESHOLD: Final[float] = 1.0e-12
BAD_NUMBER_PATTERN: Final[str] = "0.100000E+100"
WARNING_VER177_PATTERN: Final[str] = "warning ver177"
SOLUTION_MODEL_NOT_REQUESTED: Final[str] = "Reading solution models from file: not requested"

# Scientific status values
STATUS_SMOKE_TEST: Final[str] = "surface_proxy_smoke_test"
STATUS_LITERATURE_CANDIDATE: Final[str] = "literature_candidate"
STATUS_PUBLICATION_READY: Final[str] = "publication_ready"

# Model scope values
SCOPE_SURFACE_PROXY: Final[str] = "surface_terrane_proxy"
SCOPE_MANTLE_CANDIDATE: Final[str] = "mantle_candidate"
SCOPE_BULK_SILICATE: Final[str] = "bulk_silicate_body"

# PlanetProfile readiness values
READINESS_MECHANICALLY_EXPORTABLE: Final[str] = "mechanically_exportable_not_scientifically_final"
READINESS_VALIDATED: Final[str] = "validated_for_testing"
READINESS_PUBLICATION: Final[str] = "publication_ready"

# Default thermodynamic setup
DEFAULT_DATABASE_FILE: Final[str] = "stx21ver.dat"
DEFAULT_SOLUTION_MODEL_FILE: Final[str] = "stx21_solution_model.dat"
DEFAULT_EXCLUDED_PHASES: Final[tuple[str, ...]] = ("qtz",)
DEFAULT_SOLUTION_MODELS: Final[tuple[str, ...]] = ("O", "Opx", "Cpx", "Gt", "Sp", "Pl", "C2/c", "NaAl")

# Default P-T range
DEFAULT_PT_RANGE: Final[dict[str, dict[str, float]]] = {
    "pressure_bar": {"min": 1000.0, "max": 50000.0},
    "temperature_k": {"min": 800.0, "max": 2200.0},
}

# PlanetProfile column mapping
PLANETPROFILE_COLUMNS: Final[tuple[tuple[str, str], ...]] = (
    ("t_k", "T(K)"),
    ("p_bar", "P(bar)"),
    ("rho_kgm3", "rho_kgm3"),
    ("vp_kms", "VP_kms"),
    ("vs_kms", "VS_kms"),
    ("cp_jm3k", "Cp_Jm3K"),
    ("alpha_pk", "alpha_pK"),
    ("ks_bar", "KS_bar"),
    ("gs_bar", "GS_bar"),
)

# WERAMI input sequence (historical default)
DEFAULT_WERAMI_INPUT_SEQUENCE: Final[tuple[str, ...]] = (
    "2",    # 2D grid table
    "38",   # System properties
    "1",    # Independent variable 1
    "2",    # P(bar) and T(K)
    "13",   # rho
    "14",   # Vp
    "3",    # Vs
    "4",    # Cp
    "10",   # alpha
    "11",   # Ks
    "0",    # Done selecting properties
    "n",    # No more properties
    "1",    # Grid output
    "0",    # Exit
)

# File naming patterns
COMPOSITION_FILE_SUFFIX: Final[str] = ".json"
BULK_VALUES_SUFFIX: Final[str] = "_bulk_values.txt"
SUMMARY_SUFFIX: Final[str] = "_summary.txt"
BUILD_LOG_NAME: Final[str] = "build.log"
VERTEX_LOG_NAME: Final[str] = "vertex.log"
WERAMI_LOG_NAME: Final[str] = "werami.log"
VALIDATION_REPORT_NAME: Final[str] = "validation_report.txt"
OXIDE_OMISSIONS_NAME: Final[str] = "oxide_omissions.txt"
EXPORT_MANIFEST_NAME: Final[str] = "planetprofile_export_manifest.json"

# Perple_X file extensions
PERPLEX_DAT_EXT: Final[str] = ".dat"
PERPLEX_TAB_EXT: Final[str] = ".tab"
PERPLEX_PLT_EXT: Final[str] = ".plt"
PERPLEX_BLK_EXT: Final[str] = ".blk"
