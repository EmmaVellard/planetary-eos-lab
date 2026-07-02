# Quick Start Guide - v1.0

Get started with Planetary EOS Lab in 5 minutes.

## 1. Install

```bash
# Clone repository
git clone https://github.com/EmmaVellard/planetary-eos-lab.git
cd planetary-eos-lab

# Install
pip install -e .

# Verify installation
planetary-eos-gui --version
```

## 2. Configure

```bash
# Copy example config
cp configs/models.example.json configs/models.json

# Edit config - set your Perple_X path
nano configs/models.json
```

Or use environment variables:
```bash
export PERPLEX_DIR=/path/to/perplex
export PERPLEX_DATABASE=stx21
```

## 3. Launch GUI

```bash
planetary-eos-gui
```

Opens at: http://localhost:8501

## 4. Run Pipeline (CLI)

```bash
# Generate compositions
planetary-eos-compositions

# Run Perple_X
planetary-eos-run --project moon_far_highlands_surface_proxy

# Export tables
planetary-eos-export --planetprofile-export-dir outputs/export
```

## 5. Docker (Alternative)

```bash
# Build
docker build -t planetary-eos-lab .

# Run
docker run -p 8501:8501 \
  -v /path/to/perplex:/opt/perplex:ro \
  planetary-eos-lab
```

## Common Commands

### GUI
```bash
planetary-eos-gui                    # Launch GUI
planetary-eos-gui --port 8502        # Custom port
planetary-eos-gui --version          # Show version
```

### CLI
```bash
# Run with options
planetary-eos-run --verbose --log-file run.log

# Select database
planetary-eos-run --database hp633

# Run specific project
planetary-eos-run --project my_project
```

### Docker
```bash
# Start
docker-compose up -d

# View logs
docker-compose logs -f

# Stop
docker-compose down

# Run command
docker exec planetary-eos-lab planetary-eos-run --help
```

## Database Selection

### stx21 (Default)
```bash
planetary-eos-run --database stx21
```
- Oxides: Na2O, MgO, Al2O3, SiO2, CaO, FeO
- Best for: Standard silicate compositions

### hp633
```bash
planetary-eos-run --database hp633
```
- Oxides: + TiO2, K2O, P2O5
- Best for: Ti/K/P-bearing compositions

## Environment Variables

```bash
# Set configuration
export PERPLEX_DIR=/opt/perplex
export PERPLEX_DATABASE=stx21
export PERPLEX_LOG_LEVEL=INFO
export PERPLEX_LOG_FILE=/tmp/perplex.log

# Run (uses environment automatically)
planetary-eos-gui
```

## Common Issues

### "PERPLEX_DIR not found"
```bash
# Check path
ls /path/to/perplex/bin/
# Should show: build, vertex, werami

# Set in config
{"perplex_dir": "/correct/path/to/perplex"}
```

### "Database file not found"
```bash
# Check database files
ls /path/to/perplex/datafiles/
# Should include: stx21ver.dat, stx21_solution_model.dat

# Or use different database
planetary-eos-run --database hp633
```

### "Port already in use"
```bash
# Use different port
planetary-eos-gui --port 8502

# Or kill existing process
lsof -ti:8501 | xargs kill
```

## Next Steps

- Read [README.md](README.md) for full documentation
- See [DOCKER.md](DOCKER.md) for Docker details
- Check [CONTRIBUTING.md](CONTRIBUTING.md) to contribute
- Review [composition.md](composition.md) for lunar examples

## Getting Help

- Issues: https://github.com/EmmaVellard/planetary-eos-lab/issues
- Discussions: https://github.com/EmmaVellard/planetary-eos-lab/discussions
- Documentation: All *.md files in repository

---

**Version:** 1.0  
**Updated:** 2024-07-01
