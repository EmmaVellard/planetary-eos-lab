# Contributing to Planetary EOS Lab

Thank you for your interest in contributing to Planetary EOS Lab! This document provides guidelines and instructions for contributing.

## Quick Start for Contributors

1. **Fork and clone the repository**
   ```bash
   git clone https://github.com/YOUR_USERNAME/planetary-eos-lab.git
   cd planetary-eos-lab
   ```

2. **Set up development environment**
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -e ".[dev]"
   ```

3. **Install Perple_X** (required for full testing)
   - Download from https://github.com/jadconnolly/Perple_X
   - Set `perplex_dir` in `configs/models.json`

4. **Run tests**
   ```bash
   pytest
   ```

## Development Workflow

### Making Changes

1. **Create a feature branch**
   ```bash
   git checkout -b feature/your-feature-name
   ```

2. **Make your changes**
   - Follow the code style (see below)
   - Add tests for new functionality
   - Update documentation as needed

3. **Test your changes**
   ```bash
   # Run all tests
   pytest
   
   # Run specific test file
   pytest tests/test_lunar_pipeline.py
   
   # Test the GUI locally
   streamlit run planetary_eos_lab/gui/streamlit_app.py
   ```

4. **Commit with clear messages**
   ```bash
   git add .
   git commit -m "Add feature: brief description"
   ```

5. **Push and create pull request**
   ```bash
   git push origin feature/your-feature-name
   ```
   Then open a pull request on GitHub.

## Code Style Guidelines

### Python Style
- Follow PEP 8
- Use type hints where possible
- Line length: 120 characters max
- Use `from __future__ import annotations` for forward compatibility

### Naming Conventions
- Functions and variables: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_SNAKE_CASE`
- Private methods: `_leading_underscore`

### Documentation
- Add docstrings to public functions and classes
- Include parameter types and return types
- Example:
  ```python
  def normalize_wt_percent(composition: dict[str, float]) -> dict[str, float]:
      """Normalize composition to 100 wt%.
      
      Args:
          composition: Oxide weight percentages
          
      Returns:
          Normalized composition totaling 100 wt%
          
      Raises:
          ValueError: If total is zero or negative
      """
  ```

### Imports
- Group imports: standard library, third-party, local
- Use absolute imports from package root
- Avoid circular imports

### Testing
- Write tests for new features
- Use descriptive test names: `test_function_name_does_what_when_condition`
- Use fake Perple_X executables in tests (see `tests/test_lunar_pipeline.py`)
- Test both success and failure cases

## Project Structure

```
planetary-eos-lab/
├── planetary_eos_lab/        # Main package
│   ├── core/                 # Core business logic
│   │   ├── config_io.py      # Config file handling
│   │   ├── model_schema.py   # Data validation and schemas
│   │   ├── pipeline_runner.py
│   │   └── validation_summary.py
│   ├── gui/                  # Streamlit GUI
│   │   └── streamlit_app.py
│   └── cli/                  # Command-line entry points
├── tests/                    # Test suite
├── configs/                  # Config files (models.json)
├── compositions/             # Generated composition files
├── outputs/                  # Perple_X outputs
└── build_inputs/             # BUILD templates

# Root-level scripts (backward compatibility)
├── run_perplex.py
├── make_compositions.py
├── export_planetprofile.py
├── plot_comparisons.py
└── run_full_pipeline.py
```

## Adding New Features

### Adding a New Oxide
1. Update `OXIDE_ORDER` in `make_compositions.py`
2. Update `PERPLEX_COMPONENTS` in `run_perplex.py` if thermodynamically modeled
3. Update BUILD template if needed
4. Add tests for the new oxide
5. Update documentation

### Adding a New Thermodynamic Database
1. Create new BUILD template in `build_inputs/`
2. Update config schema to support database selection
3. Add validation for new database format
4. Document compatibility and limitations
5. Add example configuration

### Extending the GUI
1. Maintain the step-by-step workflow structure
2. Use `st.session_state` for persistence
3. Show warnings for scientific caveats
4. Test with multiple models
5. Keep mobile-friendly (reasonable column widths)

## Scientific Guidelines

### Composition Provenance
- Always document composition sources
- Use `scientific_status` field appropriately:
  - `surface_proxy_smoke_test` - testing only
  - `literature_candidate` - from publications but not final
  - `publication_ready` - peer-reviewed and validated
- Track which oxides are omitted from BUILD
- Include reference citations

### Validation
- Validate all outputs before marking as success
- Check for NaN, Inf, bad-number sentinels
- Verify solution models are loaded
- Check column ranges (e.g., non-zero alpha)
- Document assumptions and exclusions

### PlanetProfile Export
- Include provenance manifest
- Warn about scientific readiness
- Document P-T range and resolution
- List excluded phases
- Record database and solution model versions

## Pull Request Guidelines

### Before Submitting
- [ ] Tests pass locally
- [ ] Code follows style guidelines
- [ ] Documentation updated
- [ ] No merge conflicts with main
- [ ] Commit messages are clear

### PR Description Template
```markdown
## Description
Brief description of changes

## Type of Change
- [ ] Bug fix
- [ ] New feature
- [ ] Breaking change
- [ ] Documentation update

## Testing
How was this tested?

## Checklist
- [ ] Tests added/updated
- [ ] Documentation updated
- [ ] Scientific caveats documented
- [ ] Backward compatible (or breaking changes documented)
```

## Reporting Issues

### Bug Reports
Include:
- Operating system and Python version
- Perple_X version
- Full error message and traceback
- Minimal reproduction example
- Expected vs. actual behavior

### Feature Requests
Include:
- Use case description
- Why existing features don't work
- Proposed solution (optional)
- Impact on scientific workflow

## Questions and Support

- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: General questions and ideas
- **Documentation**: Check README.md and composition.md first

## Code of Conduct

- Be respectful and constructive
- Welcome newcomers and diverse perspectives
- Focus on what's best for the scientific community
- Give credit where due

## License

By contributing, you agree that your contributions will be licensed under the MIT License.

## Recognition

Contributors are listed in the GitHub contributors page. Significant contributions may be acknowledged in publications using this software.

---

Thank you for making Planetary EOS Lab better!
