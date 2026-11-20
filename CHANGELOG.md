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
- `se15_fes_core` database (Saxena & Eriksson 2015) for Fe–S metallic cores, with an Fe-5 wt% S example.
- GUI form to add or edit a database (*Composition > Thermodynamic Models*); `examples/first_run.py` and the
  editable study script `examples/my_study.py`.
- Perple_X runs stop with an error showing the last prompt when BUILD or WERAMI waits for an answer
  the template does not give (time limit, `PLANETARY_EOS_PERPLEX_TIMEOUT`), and a one-node WERAMI grid is
  rejected; databases can carry a caveat shown in the GUI and at every run (Fe–S core: checked 4–9 GPa only).
- `docs/python_api.md`, `docs/planetprofile_usage.md`, `examples/warren_mantle_stx24.py`, `CITATION.cff`.

### Changed
- README rewritten for a new user (what the lab does, quick start, interface, scripts, databases,
  configuration, outputs, checks, limits, citation); INSTALL.md rewritten step by step (Perple_X on macOS,
  100-character paths, self-test, first run); database details in docs/databases.md; QUICKSTART.md removed
  (outdated, replaced by the README quick start); copyright year 2026.
- `validate_tab.py` accepts up to 0.15 % non-finite values in large tables (was 0.1 %).
- Component status shows an oxide split into several components (FeO -> Fe + O).
- Export manifest schema 3: EoS Lab commit and dirty flag, Perple_X version, sha256 of tables and BUILD
  templates, no local absolute paths.
- `planetary-eos-gui` runs Streamlit with the current Python, so it works without an activated venv.
- `--database` accepts any registered database; lunar BUILD templates take their P–T range from
  `${P_RANGE_BAR}` and `${T_RANGE_K}`.
- numpy is a declared dependency.
- stx24 excludes O2 (required by the corrected stx24 of Perple_X 7.2.13+; no effect beyond numerical noise with 7.2.5);
  the self-test warns about a pre-correction `stx24ver.dat`.
- WERAMI runs adapt to Perple_X versions that ask whether to include fluids (the answers are rerun with 'n');
  BUILD errors when it cannot open a file, and file names longer than Perple_X's 100 characters are refused.
- Cleaning a project's work files no longer removes `perplex_option.dat` or another project's files.
- `sample_on_grid` now defaults to true (pipeline and GUI): with false, WERAMI asks for grid nodes that the
  default answers do not provide, and the run never ends.

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
