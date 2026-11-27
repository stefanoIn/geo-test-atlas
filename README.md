# GeoTest-Atlas

See [RUNNING.md](RUNNING.md) for the complete command reference, including exposure for all downstream chips.

Work in progress: a standalone companion to GeoTest for geographical metadata,
centre-based ecological characterisation and geographical pretraining exposure.
It contains no training, evaluation or model-architecture components.
The extraction has not been executed or tested; verify it locally before relying
on regenerated results.

## Contents

- `geography/`: metadata adapters, RESOLVE repair/assignment and footprint analysis.
- `scripts/enrich_metadata.py`: enrichment, descriptive statistics and figures.
- `scripts/geographical_exposure.py`: footprint exposure and local/world maps.
- `scripts/assets/`: Leaflet assets, its licence and country outlines.
- `scripts/benchmark_assignment.py`: optional bounded comparison against an
  explicitly supplied trusted reference source file, without GeoTest Git history.
- `tests/`: copied geography regression tests with updated import/output paths.
- `data/environmental/resolve_2017/`: original RESOLVE shapefile and sidecars.
- `data/inventories/`: SSL4EO-S12 coordinates and TerraMesh train/validation metadata.

No generated outputs or downstream imagery were copied. GeoTest remains intact.
TerraMesh exposure/enrichment defaults to training metadata; the copied validation
metadata is not included unless explicitly selected with a path override.
Inventory release caveats and source links are retained in `data/inventories/README.md`.

## Environment and local checks

Use the existing environment; no installation or new environment is required by
the extraction. `requirements.txt` lists dependencies, not a locked environment.
Run commands from the project directory so relative paths resolve consistently.

```powershell
Set-Location D:\UNI\geotest-atlas
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
& "D:\UNI\ANCILLARY WORK\.venv\Scripts\Activate.ps1"
python -m unittest tests.test_geography -v
python scripts/geographical_exposure.py --self-test
```

## Ecological enrichment

```powershell
# Bounded initial check: writes outputs/enrichment_subsets.
python -u scripts/enrich_metadata.py --sample-records 1024 --batch-size 256

# Full inventories: writes outputs/enrichment.
python -u scripts/enrich_metadata.py --full

# Regenerate reports from completed enrichment only.
python -u scripts/enrich_metadata.py --report-only

# Optional lower-memory reporting; Pandas is the default.
python -u scripts/enrich_metadata.py --report-only --dataset terramesh --aggregation-backend sqlite
```

Under the configured `--output-dir`:

```text
enriched/               <dataset>_enriched.parquet + provenance manifest
validation/             repair comparisons, discrepancies and validation summary
statistics/<dataset>/   category counts and statistical summary
figures/<dataset>/      dataset-specific PDFs
figures/                cross-inventory comparison
```

Validated RESOLVE geometry and its repair audit default to
`outputs/enrichment/validation/resolve_2017_validated.parquet` and companion files;
`--validated` changes this independently of `--output-dir`.
`--resolve-source`, `--inventory KIND=PATH`, `--dataset`, `--output-dir` and
`--aggregation-backend` remain configurable. Completed enrichment is reused only
when the existing provenance checks match. Report-only checks saved output hashes
without loading raw inventories. Progress and interruption-safe staging are retained.
No migration utility is needed: this project starts with no generated outputs.

## External downstream data

Default Sen1Floods11 paths point to `../GeoTest/data/sen1floods11/` solely as an
external data location. No GeoTest code is imported. Use other locations explicitly:

```powershell
python -u scripts/enrich_metadata.py --full --dataset sen1floods11 --inventory "sen1floods11=../GeoTest/data/sen1floods11/catalog/sen1floods11_hand_labeled_label/collection.json"

python -u scripts/geographical_exposure.py --chip Ghana_313799 --map-chip Ghana_313799 --view-km 25 --catalog ../GeoTest/data/sen1floods11/catalog/sen1floods11_hand_labeled_label/collection.json --splits-dir ../GeoTest/data/sen1floods11/splits/all_hand_labels --raster-dir ../GeoTest/data/sen1floods11/HandLabeled/LabelHand

python -u scripts/geographical_exposure.py --world-map-only
```

Exposure outputs go to `outputs/exposure/`, separate from ecological enrichment.
Override with `--output`; `--ssl4eo` and `--terramesh` select inventory paths.
Custom split CSVs use repeatable `--split NAME=CSV`. Existing Sen1Floods11 filename
and STAC conventions still apply to the downstream adapter; arbitrary new dataset
schemas may need an adapter. Selecting one chip still scans pretraining inventories.
World maps also read inventory metadata and can produce large HTML files.
Online basemap tiles require network access and remain subject to provider policies.

## Interpretation and attribution

Assignment uses the same geographical CRS, repaired polygons, `covers`/`touches`
semantics, precision and ambiguity handling as GeoTest. Category definitions,
exact centre deduplication, vectorised assignment and output schemas are preserved.
See `geography/README.md` for methodological details and limitations.
Geographical exposure is not proof of observation reuse or downstream label leakage.

Leaflet copyright and BSD-2-Clause licence are retained in
`scripts/assets/Leaflet-LICENSE.txt` and the bundled JavaScript. Country outlines
are attributed to Natural Earth (public-domain data); the exact source revision
was not recorded in GeoTest. Original RESOLVE attributes, including its licence
field, are retained. Local metadata copies do not establish redistribution rights;
check upstream dataset terms before publishing them. Raw metadata and generated
outputs are excluded by `.gitignore`. No new project-wide licence is assigned.