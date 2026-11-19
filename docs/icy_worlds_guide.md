# Icy Worlds Modeling Guide

This guide explains how to model icy worlds (moons, dwarf planets, comets) using Planetary EOS Lab. Unlike rocky bodies like the Moon, icy worlds require element-based or volatile-bearing thermodynamic databases.

## Table of Contents
- [Database Selection Guide](#database-selection-guide)
- [Component vs Oxide Compositions](#component-vs-oxide-compositions)
- [Quick Start Tutorial](#quick-start-tutorial)
- [Example Bodies](#example-bodies)
- [Composition Sources](#composition-sources)
- [Troubleshooting](#troubleshooting)

---

## Database Selection Guide

### Decision Flowchart

```
Is your body differentiated?
├─ YES → Differentiated icy world
│  ├─ Europa/Ganymede silicate core → dew13_hydrous
│  └─ Low-pressure differentiated → dew13_hydrous
│
└─ NO → Undifferentiated or primitive
   ├─ Chondritic bulk composition
   │  ├─ High pressure (>50 kbar) → dew17_hhph
   │  └─ With hydrous phases → hpha02_hydrous
   │
   └─ Volatile-rich cometary → dew17_comet
```

### Database Comparison

| Database | Best For | Components | PT Range | Key Features |
|----------|----------|------------|----------|--------------|
| **dew17_hhph** | Undifferentiated chondrites (CI, CM, CV) | H2, C, Mg, Al, Si, S2, Ca, Fe, O2 | 1-140k bar<br>250-3000K | High-pressure mantle phases; includes Al, Ca for CAI-bearing materials |
| **hpha02_hydrous** | Hydrous chondrites + water | SiO2, Al2O3, FeO, MgO, CaO, Na2O, H2O | 1-140k bar<br>250-3000K | Oxide + H2O hybrid; hydrous phases (Atg, Amph, melt) |
| **dew13_hydrous** | Differentiated silicate cores | H2, C, Mg, Si, S2, Fe, O2 | 1-50k bar<br>273-1000K | Lower pressure; no Al/Ca (assumes differentiation removed) |
| **dew17_comet** | Cometary nuclei, volatile-rich | H2, O2, C, Fe, Si, Mg, N2, S2 | 1-50k bar<br>273-1000K | Includes N2 for organic ices; low-temperature phases |

### When to Use Each Database

#### dew17_hhph: Undifferentiated High-Pressure Bodies
**Use for:**
- Bulk chondritic compositions (CI, CM, CV)
- Bodies with minimal differentiation
- High-pressure interiors (Titan, Callisto bulk)

**Example bodies:** Titan mantle, Callisto interior, Ceres core

**Component notes:**
- Includes Al and Ca for refractory-rich chondrites
- Full 9-component system handles CAIs and metal

**Excluded phases:** Liquid phases that cause computational issues (stv, perL, limL, foL, etc.)

#### hpha02_hydrous: Hydrous Chondrites
**Use for:**
- Chondrite + water mixtures
- Testing hydration effects
- Lower water content scenarios (0.5-5 wt% H2O)

**Example bodies:** CV3 with acquired water, altered asteroids

**Component notes:**
- Hybrid oxide-component system
- H2O as explicit component for hydrous phases
- Uses HP02 thermodynamic data

**Excluded phases:** stv, coe, h2oL

#### dew13_hydrous: Differentiated Icy-World Cores
**Use for:**
- Differentiated rocky cores of icy moons
- Post-magma-ocean silicate mantles
- Low-pressure equilibrated silicates

**Example bodies:** Europa core (after metal separation), Ganymede silicate mantle

**Component notes:**
- 7 components only (no Al, Ca - lost to crust/floated)
- Lower temperature/pressure range
- Hydrous phases for water-saturated conditions

**Excluded phases:** h2oL, SO2, CO (assumes aqueous/gaseous phases handled separately)

#### dew17_comet: Volatile-Rich Cometary Bodies
**Use for:**
- Cometary nuclei
- Extremely volatile-rich outer solar system objects
- C-O-H-N-S dominated compositions

**Example bodies:** Comet 67P/Churyumov-Gerasimenko, Kuiper belt objects

**Component notes:**
- Includes N2 for organic ices
- Low-temperature solution models (Fsp, Bi, Chl)
- Large excluded phase list to avoid unstable phases

---

## Component vs Oxide Compositions

### Oxide-Based Models (Moon, Mars, rocky planets)
```json
"oxides_wt_percent": {
  "SiO2": 45.5,
  "Al2O3": 24.0,
  "FeO": 5.9,
  "MgO": 7.5,
  ...
}
```
- Traditional silicate petrology approach
- Components are oxide formulas (SiO2, Al2O3, etc.)
- Best for anhydrous silicate-dominated systems

### Component-Based Models (Icy worlds)
```json
"components_wt_percent": {
  "H2": 2.07,
  "C": 3.53,
  "Mg": 9.94,
  "Si": 10.9,
  "O2": 47.54,
  ...
}
```
- Element-based thermodynamic approach
- Components are elements (H2, O2, Mg, Fe) or diatomic gases (S2, N2)
- Allows modeling of reduced/oxidized phases, hydrous minerals, organics

### Why Elements Instead of Oxides?

For icy worlds, element-based databases offer key advantages:
1. **Redox flexibility**: Can model both FeO and Fe-metal simultaneously
2. **Hydrous phases**: H2 and O2 balance allows hydrous minerals (serpentine, amphibole)
3. **Volatile species**: C, S, N can partition into multiple phases (graphite, sulfides, N-ices)
4. **Organic chemistry**: C-H-O system captures organic compounds at low T

---

## Quick Start Tutorial

### Step 1: Choose Your Database

Decide which database fits your body (see [Database Selection Guide](#database-selection-guide)).

For this tutorial, we'll model **CI chondrite bulk composition** using `dew17_hhph`.

### Step 2: Create Configuration File

Copy the example:
```bash
cp configs/icy_worlds.example.json configs/my_icy_models.json
```

Or start from scratch:
```json
{
  "perplex_dir": "/path/to/perplex",
  "database": "dew17_hhph",
  "models": [
    {
      "project": "my_ci_model",
      "description": "CI chondrite test composition",
      "database": "dew17_hhph",
      "planetprofile_filename": "CI_chondrite_generated.tab",
      "planetprofile_first_axis": "T",
      "scientific_status": "literature_candidate",
      "model_scope": "undifferentiated_chondrite",
      "component_label": "element",
      "components_wt_percent": {
        "H2": 2.07,
        "C": 3.53,
        "Mg": 9.94,
        "Al": 0.89,
        "Si": 10.9,
        "S2": 5.54,
        "Ca": 0.95,
        "Fe": 18.65,
        "O2": 47.54
      }
    }
  ]
}
```

### Step 3: Generate Composition Files

```bash
planetary-eos-compositions --config configs/my_icy_models.json
```

This creates:
- `compositions/my_ci_model.json` - Full composition record
- `compositions/my_ci_model_bulk_values.txt` - Normalized component values for BUILD
- `compositions/my_ci_model_summary.txt` - Human-readable summary

### Step 4: Run Perple_X Pipeline

```bash
planetary-eos-run --config configs/my_icy_models.json --project my_ci_model
```

This runs:
1. **BUILD**: Creates thermodynamic problem definition
2. **VERTEX**: Computes phase equilibria
3. **WERAMI**: Extracts physical properties
4. **Validation**: Checks output quality

### Step 5: Export for PlanetProfile

```bash
planetary-eos-export --config configs/my_icy_models.json \
  --planetprofile-export-dir outputs/for_planetprofile
```

Copy the `.tab` file into your PlanetProfile directory.

### Step 6 (Optional): Use the GUI

```bash
planetary-eos-gui
```

1. Set Perple_X path in Step 1
2. Select database (e.g., `dew17_hhph`)
3. Go to "Build Composition" workspace
4. Enter component values
5. Save to config
6. Switch to "Run Pipeline" and execute

---

## Example Bodies

### 1. Europa Core (Differentiated Silicate)

**Database:** `dew13_hydrous`  
**Rationale:** Post-differentiation, rocky core, water-saturated

```json
{
  "project": "europa_core_silicate",
  "database": "dew13_hydrous",
  "components_wt_percent": {
    "H2": 1.5,
    "C": 0.3,
    "Mg": 14.2,
    "Si": 15.8,
    "S2": 2.1,
    "Fe": 19.5,
    "O2": 46.6
  }
}
```

### 2. Titan Mantle (Undifferentiated Chondrite)

**Database:** `dew17_hhph`  
**Rationale:** High pressure, chondritic bulk, minimal differentiation

```json
{
  "project": "titan_mantle_cm_like",
  "database": "dew17_hhph",
  "components_wt_percent": {
    "H2": 1.44,
    "C": 2.26,
    "Mg": 11.8,
    "Al": 1.16,
    "Si": 13.04,
    "S2": 2.77,
    "Ca": 1.32,
    "Fe": 21.86,
    "O2": 44.34
  }
}
```

### 3. Enceladus Core (Hydrous Chondrite)

**Database:** `hpha02_hydrous`  
**Rationale:** Hydrated chondrite + ~2% water

```json
{
  "project": "enceladus_core_hydrous",
  "database": "hpha02_hydrous",
  "components_wt_percent": {
    "SIO2": 35.2,
    "AL2O3": 3.1,
    "FEO": 24.5,
    "MGO": 26.8,
    "CAO": 2.4,
    "NA2O": 0.6,
    "H2O": 2.1
  }
}
```

### 4. Comet 67P Nucleus (Volatile-Rich)

**Database:** `dew17_comet`  
**Rationale:** Organic-rich, low temperature, includes N2

```json
{
  "project": "comet_67p_nucleus",
  "database": "dew17_comet",
  "components_wt_percent": {
    "H2": 11.4,
    "O2": 41.06,
    "C": 27.08,
    "Fe": 6.1,
    "Si": 10.54,
    "Mg": 0.99,
    "N2": 1.03,
    "S2": 1.81
  }
}
```

---

## Composition Sources

### Chondritic Compositions (CI, CM, CV)

**Source:** Lodders & Fegley (1998); Lodders (2003)

Standard CI chondrite composition (element wt%):
- **H2**: ~2.0% (from H2O and hydrous minerals)
- **C**: ~3.5% (organic matter, carbonates)
- **O2**: ~47% (oxides, silicates, water)
- **Mg, Si, Fe**: Primary rock-forming elements
- **S2**: ~5.5% (sulfides, FeS)
- **Al, Ca**: ~1-2% (refractory elements)

**Note:** Element abundances converted from elemental mass fractions. H2/O2 represents total hydrogen and oxygen, partitioned into minerals/ices by Perple_X.

**References:**
- Lodders, K., & Fegley, B. (1998). *The Planetary Scientist's Companion*
- Lodders, K. (2003). Solar system abundances. *ApJ*, 591, 1220

### Cometary Compositions

**Source:** Rosetta mission results (67P/Churyumov-Gerasimenko)

Comet 67P nucleus composition:
- High C/O ratio (~0.66)
- Substantial N2 content (organics)
- Depleted in rock-forming elements
- Low Mg/Si ratio

**References:**
- Bardyn et al. (2017). Carbon-rich dust in comet 67P. *MNRAS*, 469, S712
- Altwegg et al. (2019). Cometary composition. *AREPS*, 47, 583

### Differentiated Icy Moons (Europa, Ganymede)

**Source:** Interior structure models + chondrite fractionation

Europa/Ganymede core models:
- Start with CM chondrite bulk
- Remove Al/Ca (assumes flotation to crust)
- Enhance Fe/Si (metal separation)
- Add water saturation (H2 + O2 balance)

**References:**
- Schubert et al. (2004). Interior composition of Europa. *Jupiter*, 281-306
- Kuskov & Kronrod (2005). Ganymede interior models. *Icarus*, 177, 550

### Hydrous Asteroids (CV3 + water)

**Source:** CV3 composition + acquired H2O

CV3 oxidized + water scenarios:
- Base CV3 oxide composition
- Add 0.5-5 wt% H2O (aqueous alteration)
- Model hydrous phase assemblages

**References:**
- McSween et al. (1988). Aqueous alteration. *Meteoritics*, 23, 151

---

## Troubleshooting

### Error: "Component composition missing BUILD component(s)"

**Cause:** Your model uses a database that expects specific components, but your composition doesn't include them all.

**Solution:**
1. Check which database you selected
2. View required components: `planetary-eos-database --describe <database>`
3. Ensure your `components_wt_percent` includes all listed components

**Example:**
```
Error: Component composition for my_model is missing BUILD component(s): O2

Your database 'dew17_hhph' requires: H2, C, Mg, Al, Si, S2, Ca, Fe, O2
Your composition has: H2, C, Mg, Si, S2, Fe

→ Add "O2": <value> to your components_wt_percent
```

### Warning: "Omitted from BUILD"

**Cause:** Your composition includes oxides/components that aren't modeled by the selected database.

**Solution:** This is informational. The pipeline tracks these for provenance but doesn't send them to Perple_X BUILD.

**Example:** Using TiO2 with stx21 database (stx21 doesn't model Ti).

### Validation Error: "Non-finite values in column"

**Cause:** Perple_X couldn't compute properties for some P-T conditions.

**Common reasons:**
1. PT range extends beyond database calibration
2. Composition is outside solution model bounds
3. Excluded phases are too aggressive

**Solutions:**
1. Narrow PT range in BUILD template
2. Check composition is reasonable (e.g., not 90% H2O)
3. Review excluded phases - remove some to allow more assemblages

### BUILD Failure: "Component not declared in database"

**Cause:** BUILD template lists a component that the thermodynamic data file doesn't define.

**Solution:**
1. Ensure you're using the correct database file in Perple_X datafiles/
2. Check `perplex_dir` path is correct
3. Verify database file matches database name (e.g., dew17hp622ver_elements.dat for dew17_hhph)

### GUI: "Database changed. Verify component values."

**Cause:** You switched databases mid-edit, and the new database has different component requirements.

**Solution:**
1. Review the new database's component list (shown below input fields)
2. Update component values to match new requirements
3. Zero out any components not used by the new database

---

## Advanced Topics

### Custom PT Ranges

Default PT ranges are conservative. For specific bodies, you may want custom ranges:

**Enceladus core** (small body, low pressure):
```
1 bar - 15 kbar (~1-15000 bar)
250 K - 400 K
```

**Titan mantle** (large body, high pressure):
```
1 kbar - 150 kbar (~1000-150000 bar)
500 K - 2000 K
```

Edit BUILD template or create custom template with desired ranges.

### Mixing Databases

Some bodies may require multiple database runs:
- **Differentiated interior:** Deep mantle (dew17_hhph) + shallow silicate (dew13_hydrous)
- **Hybrid compositions:** Rocky core (hp633) + icy shell (separate H2O EOS)

Run separate models and splice results in PlanetProfile.

### Solution Model Selection

Excluded phases and solution models are pre-configured but can be customized:

**To exclude additional phases:**
Edit BUILD template, add phase name to excluded list.

**To add solution models:**
Edit BUILD template, add model name. Ensure it's compatible with your database.

**Common customizations:**
- Remove `h2oL` exclusion to allow liquid water
- Add `Chl` (chlorite) for low-temperature hydrous assemblages
- Exclude `melt` phases if T range is subsolidus

---

## Database CLI Reference

```bash
# List available databases
planetary-eos-database --list

# Describe a specific database
planetary-eos-database --describe dew17_hhph

# Compare two databases
planetary-eos-database --compare dew17_hhph dew13_hydrous

# Validate database files exist
planetary-eos-database --validate --perplex-dir /path/to/perplex
```

*(Note: CLI tool not yet implemented - this is planned functionality)*

---

## References

### Thermodynamic Databases
- **DEW (Deep Earth Water model)**: Sverjensky et al. (2014), *GCA*, 129, 125
- **Holland & Powell**: Holland & Powell (2011), *J. Met. Geol.*, 29, 333
- **Stixrude & Lithgow-Bertelloni**: Stixrude & Lithgow-Bertelloni (2011), *Geophys. J. Int.*, 184, 1180

### Perple_X
- Connolly, J. A. D. (2005). Computation of phase equilibria. *EPSL*, 236, 524
- http://www.perplex.ethz.ch/

### PlanetProfile
- Vance et al. (2018). Geophysical properties of icy satellites. *JGR Planets*, 123, 180
- https://github.com/vancesteven/PlanetProfile

---

## Getting Help

- **Issues:** https://github.com/EmmaVellard/planetary-eos-lab/issues
- **Discussions:** https://github.com/EmmaVellard/planetary-eos-lab/discussions
- **Perple_X help:** http://www.perplex.ethz.ch/perplex_tutorial.html

---

*Last updated: 2026-07-06*
