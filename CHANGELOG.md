# Changelog

All notable changes to Planetary EOS Lab will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0] - 2024-07-01

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
