# Running GeoTest-Atlas

Run commands from the Atlas directory. Enrichment and exposure are independent:
enrichment adds centre-based ecological attributes; exposure compares footprints
and proximity. Exposure does not require enriched Parquet files.

## 1. Environment

```powershell
Set-Location D:\UNI\geotest-atlas
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
& "D:\UNI\ANCILLARY WORK\.venv\Scripts\Activate.ps1"
```

Paste activation and Python commands on separate lines. Alternatively, replace
`python` with `& "D:\UNI\ANCILLARY WORK\.venv\Scripts\python.exe"`.
No additional environment is needed.

## 2. Exposure for all downstream chips

```powershell
python -u scripts/geographical_exposure.py --map-chip Ghana_313799 --view-km 25 --output outputs/exposure/all_chips
```

**Omit `--chip` to analyse all downstream split members.** `--map-chip` only selects
the chip for the local figure; it does not restrict the quantitative analysis.
With the current splits this means 446 chips: 252 train, 89 validation, 90 test
and 15 Bolivia. `all_chips` preserves the previous single-chip results in
`outputs/exposure/`. Reusing a destination overwrites its previous named results.

The command scans the pretraining inventories and writes:

- `exposure_summary.csv`: one row per chip and inventory/source (normally four
  rows per chip: CROMA SSL4EO, TerraMind SSL4EO, MajorTOM and TerraMind union).
- `local_exposure.png`: only the selected chip, with matched map extents.
- `exposure_summary.png`: coverage and distance summaries across analysed chips.
- `provenance.json`: inventory counts, arguments, split counts and raster checks.

Check completeness after the command finishes:

```powershell
$rows = Import-Csv outputs/exposure/all_chips/exposure_summary.csv
($rows | Select-Object -ExpandProperty chip_id -Unique).Count
$rows.Count
$rows | Group-Object pretraining_inventory | Select-Object Name,Count
$rows | Select-Object chip_id,split -Unique | Group-Object split | Select-Object Name,Count
Get-Content outputs/exposure/all_chips/provenance.json
```

Expected with the current inputs: 446 unique chips, 1,784 rows and 446 rows per
source/union. These are completeness checks, not independent scientific validation.

For a single chip:

```powershell
python -u scripts/geographical_exposure.py --chip Ghana_313799 --map-chip Ghana_313799 --view-km 25 --output outputs/exposure/ghana
```

Repeat `--chip` to select several chips. Even one chip requires scanning inventory
metadata. Exposure has no checkpoint/resume or report-only mode: rerunning performs
the calculation again. Do not assume an interrupted directory is complete.

## 3. World inventory map

```powershell
python -u scripts/geographical_exposure.py --world-map-only --output outputs/exposure/world
Start-Process outputs/exposure/world/world_inventory_map.html
```

This shows downstream chips and toggleable pretraining centres. It reads inventory
metadata but skips overlap calculations. It does not create the all-chip exposure
CSV. Do not combine it with `--chip`. HTML files may be large; online basemap tiles
require network access and are subject to the tile provider's policy.

## 4. Ecological enrichment

A bounded initial check:

```powershell
python -u scripts/enrich_metadata.py --sample-records 1024 --batch-size 256
```

This writes `outputs/enrichment_subsets/`. SSL4EO uses a fixed-seed sample;
TerraMesh uses distributed row-group prefixes, not a globally uniform sample.
All supplied STAC items are included.

Full inventories, with Pandas reporting by default:

```powershell
python -u scripts/enrich_metadata.py --full
```

Select individual inventories, or multiple names after `--dataset`:

```powershell
python -u scripts/enrich_metadata.py --full --dataset ssl4eo
python -u scripts/enrich_metadata.py --full --dataset terramesh
python -u scripts/enrich_metadata.py --full --dataset sen1floods11
```

`sen1floods11` selects the downstream catalogue (STAC format); `stac` remains a legacy alias. The default TerraMesh inventory
is training metadata, not validation metadata. Full runs still compare original
and repaired assignments on bounded diagnostic subsets (default 4,096 records,
except STAC). `--sample-records` controls that diagnostic, not the full inventory.

Under `outputs/enrichment/`:

```text
enriched/               Parquet inventories and adjacent provenance manifests
validation/             repair comparisons, discrepancies, validation summary
statistics/<dataset>/   biome/eco-region counts and summary.json
figures/<dataset>/      category PDFs and sampled-centre PDF
figures/                biome_comparison.pdf
```

Validated RESOLVE geometry and its repair audit are shared at
`outputs/enrichment/validation/resolve_2017_validated.parquet` and companion files.
The source shapefile is unchanged. `--validated` changes this location independently
of `--output-dir`.

## 5. Regenerate statistics and figures without enrichment

```powershell
python -u scripts/enrich_metadata.py --report-only
python -u scripts/enrich_metadata.py --report-only --dataset terramesh
python -u scripts/enrich_metadata.py --report-only --aggregation-backend sqlite
python -u scripts/enrich_metadata.py --report-only --output-dir outputs/enrichment_subsets
```

Report-only reads enriched files and checks their saved hashes. It does not read
raw inventories or recompute assignments. Pandas loads the necessary columns in
memory; SQLite is the lower-RAM alternative using temporary disk storage. Both use
the same counts, exact centre deduplication, filtering and all-record denominators.
Regenerated reports replace previous reports. A cross-inventory figure contains
only inventories selected in that invocation.

## 6. Paths and CLI options

All paths are relative to the current working directory unless absolute paths are
supplied. Default downstream paths point into `../GeoTest/data/sen1floods11/`;
no GeoTest model code is imported and no imagery is copied.

Override external downstream paths:

```powershell
python -u scripts/geographical_exposure.py --catalog "../GeoTest/data/sen1floods11/catalog/sen1floods11_hand_labeled_label/collection.json" --splits-dir "../GeoTest/data/sen1floods11/splits/all_hand_labels" --raster-dir "../GeoTest/data/sen1floods11/HandLabeled/LabelHand" --output outputs/exposure/all_chips
```

For custom splits, repeat `--split`, e.g. `--split train=path/train.csv --split test=path/test.csv`.
Supplying any `--split` replaces the default set; list every split you want analysed.
The existing downstream adapter still requires Sen1Floods11 naming conventions.

| Script | Option | Purpose |
|---|---|---|
| exposure | `--ssl4eo PATH`, `--terramesh PATH` | Pretraining inventory overrides |
| exposure | `--radii 5 10 25 50 100` | Centre-proximity count radii in km |
| exposure | `--view-km 25` | Local map half-width; does not limit nearest search |
| exposure | `--batch-size 65536` | Inventory read batch size |
| exposure | `--output PATH` | Exposure output destination |
| enrichment | `--inventory KIND=PATH` | Override ssl4eo, terramesh or sen1floods11 input; repeatable |
| enrichment | `--resolve-source PATH` | Original RESOLVE shapefile |
| enrichment | `--validated PATH` | Validated RESOLVE cache location |
| enrichment | `--output-dir PATH` | Ecological output destination |
| enrichment | `--batch-size 65536` | Enrichment batch size |
| enrichment | `--aggregation-backend pandas` or `sqlite` | Reporting backend |

Without `--dataset`, explicit `--inventory` arguments select only those inventories.
For example:

```powershell
python -u scripts/enrich_metadata.py --full --inventory "sen1floods11=../GeoTest/data/sen1floods11/catalog/sen1floods11_hand_labeled_label/collection.json" --output-dir outputs/custom_enrichment
```

## 7. Tests and optional assignment benchmark

```powershell
python -m unittest tests.test_geography -v
python scripts/geographical_exposure.py --self-test
python scripts/enrich_metadata.py --help
python scripts/geographical_exposure.py --help
python scripts/benchmark_assignment.py --help
```

The optional benchmark requires a trusted Python file containing the original
`_assign` implementation. That reference was not bundled during extraction. Replace
the placeholder below with its actual path; the function is executed for comparison:

```powershell
python -u scripts/benchmark_assignment.py --reference "path/to/original_enrichment.py" --output outputs/enrichment/validation/assignment_benchmark.json
```

It compares identical representative batches of 65,536 records per pretraining
inventory, checks exact output equivalence and reports timing/RSS. It requires the
validated RESOLVE file at its default location. It does not process full inventories.

## 8. Progress, interruption and interpretation

Enrichment progress updates at batch boundaries. Hashing and geometry preparation
can be quiet; reporting announces reading, grouping/deduplication and plotting.
Completed enrichment caches are reused only when signatures and fingerprints match.
After Ctrl+C, rerun the same enrichment command: the interrupted inventory restarts,
while completed matching caches are reused. Keep Parquet and provenance together.
Exposure prints scanned-record progress and a final destination/elapsed time; it
can be quiet while building indexes and evaluating candidates. It does not use the
enrichment cache or its interruption-safe publication mechanism.

Ecological assignment describes the centre, not the entire footprint. Unmatched,
unclassified and ambiguous cases remain explicit. SSL4EO original footprints are
reconstructed approximations. TerraMind union coverage is a geometric union, not
an addition of source percentages. Exposure is not proof of label leakage or of
which observations a historical model checkpoint actually consumed.