# Using exported tables in PlanetProfile

[PlanetProfile](https://github.com/vancesteven/PlanetProfile) reads Perple_X mantle tables by file
name. To use a table made with Planetary EOS Lab:

1. Run the model and export it:

   ```bash
   planetary-eos-run --config configs/models.json --project my_mantle
   planetary-eos-export --config configs/models.json --project my_mantle
   ```

   The table is written to `outputs/planetprofile_export/` under the name given by the model's
   `planetprofile_filename` (default `<project>_PerpleX.tab`), with
   `planetprofile_export_manifest.json` next to it.

2. Copy the `.tab` file into PlanetProfile's Perple_X table folder,
   `PlanetProfile/Thermodynamics/EOStables/Perple_X/`.

3. In the body's configuration file (`PP<Body>.py`, e.g. `Luna/PPLuna.py`), name it:

   ```python
   Planet.Sil.mantleEOS = 'my_mantle_PerpleX.tab'
   ```

   A core table (database `se15_fes_core`) is named the same way in the core settings:

   ```python
   Planet.Core.coreEOS = 'Fe95S5_core_PerpleX.tab'
   ```

   PlanetProfile treats a file whose name contains `3D_EOS` as a 3-D Fe–S stack interpolated in
   wFe; a single-composition table must not contain `3D_EOS` in its name.

4. Keep the manifest with your results. It records the EoS Lab commit (and whether the code had
   uncommitted changes), the Perple_X version, the database, solution models, excluded phases, P–T
   range and grid, the composition and its provenance, and the sha256 of the table and of its BUILD
   template.

Before a PlanetProfile run, check that the table covers the pressures and temperatures the model will
ask for, for example with the P–T profile of a previous run:

```bash
planetary-eos-check-table domain outputs/planetprofile_export/my_mantle_PerpleX.tab --points my_profile.csv
```

PlanetProfile versions differ in how they cache and look up tables; if a table is not found, check
the `mantleEOS` handling in `PlanetProfile/Thermodynamics/InnerEOS.py` of your version.
