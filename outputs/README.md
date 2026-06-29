# Example Outputs

This directory contains a small tracked example-output set from the smoke-test lunar runs:

- `comparisons/composition_oxides.svg`
- `comparisons/planetprofile_properties.svg`
- `moon_far_dry_mantle/moon_far_dry_mantle_planetprofile.tab`
- `moon_far_dry_mantle/oxide_omissions.txt`
- `moon_near_pkt_mantle/moon_near_pkt_mantle_planetprofile.tab`
- `moon_near_pkt_mantle/oxide_omissions.txt`

The Perple_X work files, raw WERAMI tables, and logs are intentionally not tracked here. They are larger, reproducible, and may contain machine-local paths from the Perple_X installation.

Regenerate the full output tree with:

```bash
python3 run_full_pipeline.py
```
