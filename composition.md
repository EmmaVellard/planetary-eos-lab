# Lunar Composition Notes

This file documents the first-pass lunar compositions used by the pipeline. These are literature-based surface/terrane proxies for testing and comparison, not final lunar mantle compositions.

## Model Intent

The two configured models are meant to bracket a simple near-side/far-side surface contrast:

- `moon_far_highlands_surface_proxy`: farside/highlands-like surface proxy, with high Al2O3 and CaO and low FeO and TiO2.
- `moon_near_maria_surface_proxy`: nearside/maria-like surface proxy, with higher FeO and TiO2 and lower Al2O3.

Their scientific metadata is:

| Field | Value |
| --- | --- |
| `scientific_status` | `surface_proxy_smoke_test` |
| `model_scope` | `surface_terrane_proxy` |
| `planetprofile_readiness` | `mechanically_exportable_not_scientifically_final` |

The oxide numbers below are surface/terrane averages. They should not be presented as directly sampled mantle compositions.

Editable source definitions live in `configs/models.example.json` or the local ignored `configs/models.json`. Files under `compositions/` are generated normalized artifacts.

## Source Values

The starting numbers reproduce commonly tabulated average lunar highlands and maria oxide compositions. The table is useful because it captures the major compositional contrast between the farside-dominated highlands and nearside mare regions.

| Oxide | Far side / highlands proxy raw wt% | Near side / maria proxy raw wt% |
| --- | ---: | ---: |
| SiO2 | 45.5 | 45.4 |
| TiO2 | 0.6 | 3.9 |
| Al2O3 | 24.0 | 14.9 |
| FeO | 5.9 | 14.1 |
| MgO | 7.5 | 9.2 |
| CaO | 15.9 | 11.8 |
| Na2O | 0.6 | 0.6 |
| K2O | 0.0 | 0.0 |
| P2O5 | 0.0 | 0.0 |
| Total | 100.0 | 99.9 |

The pipeline normalizes these values before writing the composition artifacts. The near-side total is 99.9 wt%, so its normalized values differ slightly from the raw table.

## Normalized Values

| Oxide | Far side / highlands proxy normalized wt% | Near side / maria proxy normalized wt% |
| --- | ---: | ---: |
| SiO2 | 45.50000 | 45.44545 |
| TiO2 | 0.60000 | 3.90390 |
| Al2O3 | 24.00000 | 14.91491 |
| FeO | 5.90000 | 14.11411 |
| MgO | 7.50000 | 9.20921 |
| CaO | 15.90000 | 11.81181 |
| Na2O | 0.60000 | 0.60060 |
| K2O | 0.00000 | 0.00000 |
| P2O5 | 0.00000 | 0.00000 |

## Values Passed To BUILD

The default BUILD transcript uses `stx21ver.dat` and `stx21_solution_model.dat`. The upstream Perple_X `stx21ver.dat` component block declares `NA2O`, `MGO`, `AL2O3`, `SIO2`, `CAO`, `FEO`, and `O2`. The workbench treats `O2` as a redox/internal database component and passes the six bulk oxide components below to BUILD:

```text
NA2O MGO AL2O3 SIO2 CAO FEO
```

Therefore `run_perplex.py` expands `${PERPLEX_BULK_VALUES}` in this order:

| Project | BUILD values in `NA2O MGO AL2O3 SIO2 CAO FEO` order |
| --- | --- |
| `moon_far_highlands_surface_proxy` | `0.60000000 7.50000000 24.00000000 45.50000000 15.90000000 5.90000000` |
| `moon_near_maria_surface_proxy` | `0.60060060 9.20920921 14.91491491 45.44544545 11.81181181 14.11411411` |

TiO2, K2O, and P2O5 remain in the JSON composition records, but with the default stx21 profile they are source-only oxides. They are useful for provenance and plotting, but they are omitted from BUILD because they are not part of this stx21 component list. The runner prints and writes an `oxide_omissions.txt` warning whenever a nonzero source-only oxide is detected. The generated composition JSON also contains `omitted_oxides_from_build` and the backward-compatible `omitted_oxides_from_default_build`; the export manifest repeats the omitted oxide list.

This matters scientifically: the near-side/maria proxy is Ti-rich in the source table, but the default `stx21` setup does not pass TiO2 to BUILD. Any near-side versus far-side comparison that depends on Ti-bearing phases is therefore incomplete. The workbench also provides an `hp633` profile using `hp633ver.dat` and `solution_model.dat`; it passes `TiO2` and `K2O` to BUILD, while `P2O5` remains source-only because the default `hp633ver.dat` component block does not declare P2O5. Its default BUILD template excludes the silica phases `q`, `crst`, and `trd` because they can produce incomplete seismic properties over the smoke-test grid. Switching profiles is a thermodynamic-model change, not just a plotting option; the database, solution model file, BUILD prompts, phases, and validation assumptions must be reviewed together.

## Current Thermodynamic Caveat

The default BUILD transcripts currently exclude silica phases that can yield incomplete seismic properties on the smoke-test grid: `qtz` for `stx21`, and `q`, `crst`, plus `trd` for `hp633`. Without those exclusions, the highlands-like proxy can stabilize these phases over part of the P-T grid, leading to `NaN` Vp, Vs, bulk modulus, and shear modulus values in the WERAMI table.

This exclusion keeps the PlanetProfile-facing smoke-test tables finite. It is a numerical/modeling guard, not a final scientific statement about lunar crust or mantle mineralogy. If the goal becomes a publication-quality crustal, mantle, or mantle-crust model, quartz stability and the database/solution-model choice should be revisited.

## Reference Trail

- Lunar surface maria/highlands oxide table: https://en.wikipedia.org/wiki/Geology_of_the_Moon#Elemental_composition
- Lu et al. (2020), "Seamless maps of major elements of the Moon": https://arxiv.org/abs/2007.15858
- Sossi et al. (2024), "Composition, Structure and Origin of the Moon": https://arxiv.org/abs/2408.16840
- Perple_X upstream repository and datafiles: https://github.com/jadconnolly/Perple_X
- Default stx21 thermodynamic datafile: https://raw.githubusercontent.com/jadconnolly/Perple_X/main/datafiles/stx21ver.dat

## Refinement Path

Good next refinements would be:

- Separate surface terrane, crust, and mantle hypotheses instead of using one project name for all of them.
- Add a KREEP-rich nearside/PKT scenario, with heat-producing elements handled in PlanetProfile rather than only as bulk oxides.
- Test a thermodynamic dataset that includes Ti-bearing phases if TiO2 is important to the scientific question.
- Build a small ensemble of compositions from published lunar mantle or bulk silicate Moon estimates.
- Compare Perple_X output sensitivity to database choice, solution model list, phase exclusions, and P-T grid resolution.
