# Changelog

All notable changes to Planetary EOS Lab will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- stx24 database (Stixrude & Lithgow-Bertelloni 2024) with its BUILD template; FeO passed as Fe + O.
- Tracked BSM catalogue `configs/lunar_bsm_models.json` with `composition_class` and `study_role`.
- GUI run history kept on disk (`.jobs/`), with status, exit codes and a kill button.
- `docs/icy_worlds_guide.md` is now tracked (the README linked to it).
- hp636 database (Holland & Powell v6.36) and the `excluded_oxides` model option (e.g. a Ti-free control).
- Databases declared in the config (`custom_databases`), with `docs/adding_a_database.md`.
- `mantle_extraction`: mantle after extracting a crust by mass balance, in the config and in the GUI
  (*Composition > Build*); "Add the published lunar BSMs" in *Composition > Catalog*.
- `pt_range` per model and `phase_modes` (second WERAMI pass, `<project>_phase_modes.tab`).
- `planetary_eos_lab.analysis` and `planetary-eos-check-table`: table quality, validity masks, P–T domain
  checks, properties along a P–T path, table comparison and resolution convergence.
- `planetary-eos-selftest`: checks a real Perple_X installation against reference values (Perple_X 7.2.5).
- `docs/python_api.md`, `docs/planetprofile_usage.md`, `examples/warren_mantle_stx24.py`, `CITATION.cff`.

### Changed
- `validate_tab.py` accepts up to 0.15 % non-finite values in large tables (was 0.1 %).
- Component status shows an oxide split into several components (FeO -> Fe + O).
- Export manifest schema 3: EoS Lab commit and dirty flag, Perple_X version, sha256 of tables and BUILD
  templates, no local absolute paths.
- `planetary-eos-gui` runs Streamlit with the current Python, so it works without an activated venv.
- `--database` accepts any registered database; lunar BUILD templates take their P–T range from
  `${P_RANGE_BAR}` and `${T_RANGE_K}`.
- numpy is a declared dependency.

## [1.0] - 2026-07-01

### Added
- Initial public release
- Streamlit GUI for composition building and pipeline execution
- Command-line interface for all operations
- **Multi-database support**: stx21 (default) and hp633 with database selection
- **Centralized configuration**: Config class with environment variable support
- **Docker support**: Dockerfile, docker-compose, and comprehensive Docker documentation
- Improved CLI with --version, --verbose, --log-file flags
- PlanetProfile table export with provenance manifest
- Composition validation and normalization
- Oxide omission tracking for incomplete thermodynamic models
- Example lunar surface proxy compositions (near-side maria, far-side highlands)
- Comprehensive test suite with fake Perple_X executables
- Validation pipeline for output quality checking
- Comparison plotting for multiple compositions
- Scientific metadata tracking (status, scope, readiness)
- MIT License
- Contributing guidelines
- GitHub Actions CI/CD workflows

### Infrastructure
- pyproject.toml for pip installation
- Proper package structure with CLI entry points
- Logging framework with configurable verbosity
- Custom exception hierarchy
- Constants module to eliminate magic strings
- Session state management for GUI
- Background task runner with progress indication
- Result visualization helpers

### Documentation
- README with quick start guide
- composition.md documenting lunar proxy provenance
- CONTRIBUTING.md with development guidelines
- GitHub issue and PR templates
- API documentation in docstrings

### Testing
- 29+ unit tests covering core functionality
- Fake Perple_X executables for testing without installation
- Test coverage for validation, pipeline, export, and plotting
- CI running on Linux, macOS, and Windows
- Python 3.9–3.12 compatibility testing

[Unreleased]: https://github.com/EmmaVellard/planetary-eos-lab/compare/v1.0...HEAD
[1.0]: https://github.com/EmmaVellard/planetary-eos-lab/releases/tag/v1.0
