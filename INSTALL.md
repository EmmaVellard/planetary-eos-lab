# Installing Planetary EOS Lab, step by step

About 15 minutes. You need a terminal; the commands are for macOS and Linux, with the Windows
equivalents where they differ.

## 1. Python 3.10 or later

Check what you have:

```bash
python3 --version
```

If it is older than 3.10 or missing, install a recent Python: on macOS `brew install python@3.12`
(with [Homebrew](https://brew.sh)) or the installer from [python.org](https://www.python.org/downloads/);
on Ubuntu/Debian `sudo apt install python3 python3-venv`; on Windows the installer from python.org
(tick "Add Python to PATH").

## 2. Perple_X

Planetary EOS Lab drives Perple_X but does not include it.

1. Download the release for your system from
   [github.com/jadconnolly/Perple_X/releases](https://github.com/jadconnolly/Perple_X/releases)
   (version 7.2.13 or later; the lab is tested with 7.2.5 and 7.3.3).
2. Unpack it in a folder with a **short path**, for example `~/perplex` or `C:\perplex`. Perple_X reads
   file names of at most 100 characters, and the path of its data files must fit.
3. Check that the folder contains `bin/` (with `build`, `vertex`, `werami`) and `datafiles/`:

   ```bash
   ls ~/perplex/bin ~/perplex/datafiles | head
   ```

4. Check that the programs start:

   ```bash
   cd /tmp && ~/perplex/bin/build < /dev/null | grep release
   ```

   It should print a line such as `Perple_X release 7.3.3 Nov 10, 2026.`

**If nothing is printed on macOS** (the program is stopped at once), macOS is refusing the downloaded
binaries. The release programs look for their libraries in `../lib` only after you add that path, and
they then need to be signed again on your computer. Run this once, in the Perple_X folder:

```bash
cd ~/perplex
for f in bin/*; do install_name_tool -add_rpath @executable_path/../lib "$f" 2>/dev/null; codesign --force --sign - "$f"; done
for f in lib/*.dylib; do codesign --force --sign - "$f"; done
```

These commands only change your local copy; deleting the folder undoes them. On Linux, if a program
is not executable: `chmod +x ~/perplex/bin/*`. On Windows, if Windows blocks the programs: right-click
each one, Properties, Unblock.

## 3. Planetary EOS Lab

```bash
git clone https://github.com/EmmaVellard/planetary-eos-lab.git
cd planetary-eos-lab
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e .
```

The virtual environment (`.venv`) keeps the lab's packages apart from the rest of your system; activate
it (`source .venv/bin/activate`) each time you open a new terminal. To also run the tests, install
`pip install -e ".[dev]"`.

## 4. Check the installation

```bash
planetary-eos-selftest --perplex-dir ~/perplex
```

Each line says PASS, WARN or FAIL: Python and its packages, the Perple_X programs and version, the data
files of every database, then a small real model (about 5 seconds) compared with reference values. The
last line says `SELFTEST PASSED` when everything works. A WARN about a database you do not use can be
ignored; a WARN about `stx24ver.dat` means your Perple_X predates the stx24 correction (update it before
using stx24).

## 5. First run

```bash
python examples/first_run.py --perplex-dir ~/perplex
```

This runs the check again, creates your configuration file `configs/models.json` from
`configs/models.example.json` with your Perple_X folder (an existing file is never replaced), runs the
first example model in about 10 seconds and prints where its table is.

## 6. Open the interface

```bash
planetary-eos-gui
```

Then open http://localhost:8501 in your browser (the terminal prints the address). The Perple_X
folder shown in the sidebar must be the one you installed; change it there and click *Save Perple_X
path* if needed. Stop the interface with Ctrl-C in the terminal.

## Updating

```bash
cd planetary-eos-lab
git pull
pip install -e .
```

Your `configs/models.json` and `outputs/` are not touched by an update.

## Common problems

| Problem | What to do |
| --- | --- |
| `planetary-eos-gui: command not found` | Activate the virtual environment (`source .venv/bin/activate`), or run `python -m planetary_eos_lab.cli.gui`. |
| `No module named ...` | `pip install -e .` again, inside the activated environment. |
| A Perple_X program stops at once on macOS | See the macOS paragraph of step 2. |
| `Perple_X reads file names of at most 100 characters` | Move the Perple_X folder to a shorter path (or point to a short symbolic link) and update the path in the sidebar or in `configs/models.json`. |
| `BUILD/WERAMI did not finish within ... s` | Perple_X waited for an answer the template did not give; the message shows its last question. Usually a template that does not match your Perple_X version or database: see [docs/adding_a_database.md](docs/adding_a_database.md). |
| `Missing Perple_X thermodynamic data file` | The database's data file is not in `datafiles/` of your Perple_X; update Perple_X or choose another database. |
| The port 8501 is taken | `planetary-eos-gui --port 8502`. |

## Uninstalling

Delete the `planetary-eos-lab` folder (it contains the virtual environment, your configuration and
your outputs: keep what you need first). Perple_X is a separate folder.
