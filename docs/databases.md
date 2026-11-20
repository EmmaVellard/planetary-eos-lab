# Thermodynamic databases

Each database is a Perple_X data file, the solution models chosen in it, a BUILD template in
`build_inputs/`, and the answers given to WERAMI. The built-in ones are defined in
`planetary_eos_lab/core/config.py`; *Composition > Thermodynamic Models* in the interface shows the
same information. To add another one, see [adding_a_database.md](adding_a_database.md).

Compositions are given in wt%. Oxides a database does not model are kept in the composition file
(source-only) and reported as left out of BUILD.

## Silicate mantles

### stx21 (default)

Stixrude & Lithgow-Bertelloni (2021). Components Na2O, MgO, Al2O3, SiO2, CaO, FeO. Files
`stx21ver.dat`, `stx21_solution_model.dat`. Default range 0.1–5 GPa, 800–2200 K; quartz excluded.
TiO2, K2O and P2O5 are source-only.

### stx24

Stixrude & Lithgow-Bertelloni (2024). Components Na2O, MgO, Al2O3, SiO2, CaO, Fe, O, Cr2O3. Files
`stx24ver.dat`, `stx24_solution_model.dat`. Default range 0.1–5 GPa, 300–2200 K.

- **FeO is passed as Fe + O**, split by the molar weights of `stx24ver.dat` (Fe 55.842, O 15.999):
  iron is taken as ferrous and Perple_X computes the Fe²⁺/Fe³⁺ partitioning.
- **O2 is excluded**, as the data file asks since Perple_X 7.2.13 ("exclude O2 for all calculations
  other than those as a function of f(O2) or a(O2)"); without it, Perple_X 7.3.3 finds no valid
  assemblage at any node. With 7.2.5 the exclusion changes the tables by numerical noise only.
- **Use Perple_X 7.2.13 or later.** Perple_X 7.2.13 (October 2026) corrected the stx24 data and
  solution models; `planetary-eos-selftest` warns about an older `stx24ver.dat`. For the three lunar
  bulk compositions (50 × 50 nodes, 0.1–5 GPa, 300–2200 K), 7.3.3 against 7.2.5: density, Vp and Vs
  differ by 0.01 % on average; the plagioclase–spinel–garnet transitions (0.8–1.6 GPa, 900–1500 K)
  move slightly, changing the assemblage at about 1 % of the nodes, where density differs by up to
  1.2 % and Gs by up to 5 %.
- The template was reconstructed in November 2026 from the recipe of the August 2026 lunar tables;
  tables rebuilt with it differ from those on about 5 % of the nodes (median relative difference 1e-5).

### hp633 and hp636

Holland & Powell (2011), data sets 6.33 and 6.36. Components SiO2, TiO2, Al2O3, Cr2O3, FeO, MnO, NiO,
MgO, CaO, Na2O, K2O, H2O; P2O5 is source-only. Files `hp633ver.dat` or `hp636ver.dat`, with
`solution_model.dat`. Solution models O(HP), Opx(HP), Cpx(HP), Gt(HP), Sp(HP), Pl(I1,HP), Ilm(WPH);
quartz, cristobalite and tridymite excluded so the seismic tables stay finite. hp636 uses the hp633
setup (checked with a real BUILD); for a Ti-free control of the same composition, add
`"excluded_oxides": ["TiO2"]` to the model.

## Metallic cores

### se15_fes_core

Saxena & Eriksson (2015), "Thermodynamics of Fe-S at ultra-high pressure" (`se15ver.dat`).
Components Fe and S, given as `components_wt_percent` (e.g. `{"Fe": 95, "S": 5}`); solution models
pyrrhotite `Po(SE)` and Fe–S liquid `FeS_liq`; default range 4–9 GPa, 500–2000 K. This is the setup of
PlanetProfile's `<x>Fe<y>S_core.tab` tables; molten nodes take the properties of the liquid.

Checked for Fe-5 wt% S with Perple_X 7.2.5 against PlanetProfile's `95Fe5S_core.tab` (made with
Perple_X 6.6.6): density and Ks agree to 0.01 % and 0.07 % on average. Limits, also shown in the
interface and at every run:

- checked between 4 and 9 GPa only, and the data set was published for ultra-high pressures;
- the liquid (above about 1260 K at 4 GPa and 1120 K at 9 GPa for Fe-5 wt% S) has Gs = 0 here, while
  the PlanetProfile table gives it a modulus estimated from a Poisson ratio;
- the shear moduli of solid Fe (FeBCC, FeSIV) are not in the data set: WERAMI estimates them from a
  Poisson ratio of 0.35, so Vs and Gs of the core are not data;
- `phase_modes` shows where the core is molten.

PlanetProfile reads the exported table with `Planet.Core.coreEOS`
(see [planetprofile_usage.md](planetprofile_usage.md)).

## Icy worlds and chondritic bodies

`dew17_hhph`, `dew13_hydrous`, `hpha02_hydrous` and `dew17_comet` take element or hydrous-oxide
compositions (`components_wt_percent`) for undifferentiated chondritic interiors, hydrous silicates,
cold shallow layers and cometary material. Their choice, ranges and examples are explained in
[icy_worlds_guide.md](icy_worlds_guide.md); `configs/icy_worlds.example.json` has example models.

## Perple_X versions

Tested with Perple_X 7.2.5 and 7.3.3. WERAMI's questions can change between versions (7.3 asks
whether to include fluids where 7.2.5 did not); the lab answers that question when it appears and
stops a program that waits for an answer it never gets, with its last question in the error message.
Perple_X reads file names of at most 100 characters: keep the Perple_X folder path short.
