# Installation Guide

Detailed installation instructions for Planetary EOS Lab.

## System Requirements

- **Operating System**: Linux, macOS, or Windows
- **Python**: 3.9 or later
- **Perple_X**: Latest version from [jadconnolly/Perple_X](https://github.com/jadconnolly/Perple_X)
- **Disk Space**: ~100 MB for code, additional space for outputs

## Step 1: Install Python

### macOS
```bash
brew install python@3.11
```

### Linux (Ubuntu/Debian)
```bash
sudo apt update
sudo apt install python3.11 python3.11-venv python3-pip
```

### Windows
Download from [python.org](https://www.python.org/downloads/)

## Step 2: Install Perple_X

1. **Download Perple_X**
   - Visit https://github.com/jadconnolly/Perple_X
   - Download the appropriate version for your OS
   - Or use the official Perple_X website: https://www.perplex.ethz.ch

2. **Extract to a permanent location**
   ```bash
   # Example locations
   # macOS/Linux: /opt/perplex or ~/perplex
   # Windows: C:\perplex
   
   mkdir -p ~/perplex
   cd ~/perplex
   # Extract archive here
   ```

3. **Verify installation**
   ```bash
   # Should contain:
   ls ~/perplex
   # bin/          (or executables: BUILD, VERTEX, WERAMI)
   # datafiles/    (thermodynamic databases)
   ```

## Step 3: Install Planetary EOS Lab

### Option A: From PyPI (Recommended when published)

```bash
pip install planetary-eos-lab
```

### Option B: From GitHub (Latest)

```bash
# Clone repository
git clone https://github.com/EmmaVellard/planetary-eos-lab.git
cd planetary-eos-lab

# Install
pip install -e .
```

### Option C: Development Install

```bash
# Clone repository
git clone https://github.com/EmmaVellard/planetary-eos-lab.git
cd planetary-eos-lab

# Install with development dependencies
pip install -e ".[dev]"

# Verify tests pass
pytest
```

### Using a Virtual Environment (Recommended)

```bash
# Create virtual environment
python3 -m venv perplex-env

# Activate (macOS/Linux)
source perplex-env/bin/activate

# Activate (Windows)
perplex-env\Scripts\activate

# Install
pip install planetary-eos-lab
# or: pip install -e .
```

## Step 4: Initial Configuration

1. **Copy example config**
   ```bash
   cd planetary-eos-lab
   cp configs/models.example.json configs/models.json
   ```

2. **Edit config with your Perple_X path**
   ```bash
   # macOS/Linux
   nano configs/models.json
   
   # Or use GUI (Step 5) to set the path
   ```

   ```json
   {
     "perplex_dir": "/Users/yourname/perplex",
     "models": [ ... ]
   }
   ```

## Step 5: Launch GUI

```bash
planetary-eos-gui
```

The GUI will open in your browser at http://localhost:8501

**First-time setup in GUI:**
1. Go to "1. Setup & Select Model"
2. Enter your Perple_X directory path
3. Click "Save Perple_X path to config"

## Verification

Test your installation:

```bash
# 1. Check Python version
python --version  # Should be 3.9+

# 2. Check planetary-eos-lab is installed
pip show planetary-eos-lab

# 3. Test CLI commands
planetary-eos-gui --help
planetary-eos-run --version

# 4. Run tests (if dev install)
pytest

# 5. Test Perple_X executables
ls ~/perplex/bin/  # Should show BUILD, VERTEX, WERAMI
```

## Common Issues

### Issue: `planetary-eos-gui: command not found`

**Solution:**
```bash
# Ensure pip install location is in PATH
python -m site --user-base
# Add <user-base>/bin to your PATH

# Or run directly:
python -m planetary_eos_lab.cli.gui
```

### Issue: `ModuleNotFoundError: No module named 'streamlit'`

**Solution:**
```bash
pip install streamlit
# or reinstall:
pip install -e .
```

### Issue: Perple_X executables not found

**Solution:**
```bash
# Verify Perple_X path
ls ~/perplex
ls ~/perplex/bin/BUILD    # Should exist

# Update config
nano configs/models.json
# Set "perplex_dir": "/correct/path/to/perplex"
```

### Issue: Permission denied when running Perple_X

**Solution (macOS/Linux):**
```bash
chmod +x ~/perplex/bin/*
```

**Solution (Windows):**
Right-click executables → Properties → Unblock

### Issue: GUI doesn't open in browser

**Solution:**
```bash
# Check if streamlit is running
ps aux | grep streamlit

# Manually open: http://localhost:8501

# Try different port
streamlit run planetary_eos_lab/gui/streamlit_app.py --server.port 8502
```

## Upgrading

### From Git
```bash
cd planetary-eos-lab
git pull
pip install -e . --upgrade
```

### From PyPI
```bash
pip install --upgrade planetary-eos-lab
```

## Uninstalling

```bash
pip uninstall planetary-eos-lab

# Remove config (optional)
rm -rf configs/models.json

# Remove outputs (optional)
rm -rf outputs/ compositions/
```

## Next Steps

- Read [README.md](README.md) for workflow overview
- Check [composition.md](composition.md) for lunar proxy details
- See [CONTRIBUTING.md](CONTRIBUTING.md) to contribute
- Review example compositions in `configs/models.example.json`

## Getting Help

- **Installation issues**: [GitHub Issues](https://github.com/EmmaVellard/planetary-eos-lab/issues)
- **Perple_X questions**: [Perple_X documentation](https://www.perplex.ethz.ch)
- **General questions**: [GitHub Discussions](https://github.com/EmmaVellard/planetary-eos-lab/discussions)
