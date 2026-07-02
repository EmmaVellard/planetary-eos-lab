# Migration Guide: Version 1.0

This document explains the improvements made to Planetary EOS Lab and how to use the new features.

## What's New

### 1. **Proper Python Package Structure**

**Before:**
- Scripts in repository root
- Manual `python3 script.py` execution
- No pip installation

**After:**
- Proper package structure with `pyproject.toml`
- CLI entry points: `planetary-eos-gui`, `planetary-eos-run`, etc.
- Install with `pip install -e .`
- Backward compatible: old scripts still work

**Migration:**
```bash
# Old way (still works)
python3 run_perplex.py --config configs/models.json

# New way (recommended)
pip install -e .
planetary-eos-run --config configs/models.json
```

### 2. **MIT License Added**

The project now has an MIT license, making it legally usable by others. No action needed from existing users.

### 3. **Improved Error Handling**

**New features:**
- Centralized logging framework (`planetary_eos_lab/core/logging_config.py`)
- Custom exception hierarchy (`planetary_eos_lab/core/exceptions.py`)
- Better error messages

**Example usage in custom scripts:**
```python
from planetary_eos_lab.core.logging_config import setup_logging, get_logger
from planetary_eos_lab.core.exceptions import PerplexExecutableError

# Setup logging
setup_logging(level=logging.INFO, verbose=True)
logger = get_logger(__name__)

# Use logger instead of print
logger.info("Starting pipeline")
logger.error("Failed to run BUILD")

# Raise typed exceptions
raise PerplexExecutableError("BUILD", "Executable not found")
```

### 4. **Constants Module**

**Before:**
- Magic strings throughout codebase
- Duplicate definitions

**After:**
- Centralized constants in `planetary_eos_lab/core/constants.py`
- Single source of truth

**Example:**
```python
from planetary_eos_lab.core.constants import (
    OXIDE_ORDER,
    PERPLEX_COMPONENTS,
    STATUS_SMOKE_TEST,
    DEFAULT_DATABASE_FILE,
)
```

### 5. **Enhanced GUI Features**

**New modules:**
- `planetary_eos_lab/gui/session_state.py` - Persistent state management
- `planetary_eos_lab/gui/progress.py` - Background task execution
- `planetary_eos_lab/gui/visualization.py` - Result visualization helpers

**Features:**
- Better session state management
- Progress indication for long-running tasks
- Result visualization (P-T coverage, property statistics)
- Improved notification system

### 6. **GitHub Infrastructure**

**Added:**
- `.github/workflows/tests.yml` - CI/CD for automated testing
- `.github/workflows/publish.yml` - PyPI publishing workflow
- Issue templates for bug reports and feature requests
- Pull request template
- `CONTRIBUTING.md` with development guidelines

### 7. **Documentation Improvements**

**New files:**
- `CONTRIBUTING.md` - Contributor guidelines
- `CHANGELOG.md` - Version history
- `MIGRATION_GUIDE.md` - This document

**Updated:**
- `README.md` - Installation instructions, badges, CLI commands
- `.gitignore` - Build artifacts, IDE files

## Breaking Changes

**None.** This release is 100% backward compatible:
- Old scripts (`run_perplex.py`, etc.) still work
- Config file format unchanged
- Output format unchanged
- Test format unchanged

## Recommended Workflow Changes

### For End Users

**Before:**
```bash
git clone repo
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 planetary_eos_lab/gui/streamlit_app.py
```

**After:**
```bash
git clone repo
pip install -e .
planetary-eos-gui
```

### For Developers

**Before:**
```bash
git clone repo
pip install -r requirements.txt
pip install -r requirements-dev.txt
python3 -m pytest
```

**After:**
```bash
git clone repo
pip install -e ".[dev]"
pytest
```

### For Custom Scripts

**Before:**
```python
import sys
sys.path.insert(0, '/path/to/planetary-eos-lab')
import run_perplex
```

**After:**
```python
# Install package first: pip install -e /path/to/planetary-eos-lab
from planetary_eos_lab.core import model_schema, config_io
from planetary_eos_lab.core.constants import OXIDE_ORDER
```

## Testing Your Installation

After upgrading, verify everything works:

```bash
# 1. Install with dev dependencies
pip install -e ".[dev]"

# 2. Run tests
pytest

# 3. Test GUI import
python -c "from planetary_eos_lab.gui.streamlit_app import main; print('GUI OK')"

# 4. Test CLI entry points
planetary-eos-gui --help 2>&1 | head -5

# 5. Launch GUI
planetary-eos-gui
```

## Configuration Changes

**No changes required** to `configs/models.json`. The format is unchanged.

However, you may want to add:

```json
{
  "perplex_dir": "/path/to/perplex",
  "log_level": "INFO",
  "verbose_logging": false
}
```

## New Optional Dependencies

None. Only `streamlit>=1.39.0` is required (same as before, just version-pinned now).

## Future Deprecations

**None planned.** The root-level scripts (`run_perplex.py`, etc.) will remain for the foreseeable future.

## Getting Help

- **Bug reports**: [GitHub Issues](https://github.com/EmmaVellard/planetary-eos-lab/issues)
- **Questions**: [GitHub Discussions](https://github.com/EmmaVellard/planetary-eos-lab/discussions)
- **Contributing**: See [CONTRIBUTING.md](CONTRIBUTING.md)

## Rollback

If you encounter issues, you can rollback by:

1. Uninstall: `pip uninstall planetary-eos-lab`
2. Use old workflow: `python3 -m venv .venv && pip install -r requirements.txt`
3. Run scripts directly: `python3 run_perplex.py`

However, please report issues instead of rolling back so we can fix them!

## Summary of File Changes

### Added Files
```
LICENSE
CHANGELOG.md
CONTRIBUTING.md
MIGRATION_GUIDE.md
pyproject.toml
planetary_eos_lab/cli/__init__.py
planetary_eos_lab/cli/gui.py
planetary_eos_lab/cli/run_perplex.py
planetary_eos_lab/cli/make_compositions.py
planetary_eos_lab/cli/export_planetprofile.py
planetary_eos_lab/cli/plot_comparisons.py
planetary_eos_lab/cli/run_full_pipeline.py
planetary_eos_lab/core/logging_config.py
planetary_eos_lab/core/exceptions.py
planetary_eos_lab/core/constants.py
planetary_eos_lab/gui/session_state.py
planetary_eos_lab/gui/progress.py
planetary_eos_lab/gui/visualization.py
.github/workflows/tests.yml
.github/workflows/publish.yml
.github/ISSUE_TEMPLATE/bug_report.md
.github/ISSUE_TEMPLATE/feature_request.md
.github/PULL_REQUEST_TEMPLATE.md
```

### Modified Files
```
README.md (improved installation, added badges, CLI docs)
requirements.txt (version pins)
.gitignore (build artifacts, IDE files)
```

### Unchanged Files
```
All core functionality files (run_perplex.py, make_compositions.py, etc.)
All test files
Config files
Composition files
```
