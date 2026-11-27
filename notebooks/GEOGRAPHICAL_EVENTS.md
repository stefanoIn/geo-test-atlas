# Geographical event analysis

Open `notebooks/geographical_event_analysis.ipynb` and run its cells in order using the existing ancillary environment. No models, imagery, raw pretraining inventories or spatial calculations are used.

```powershell
Set-Location D:\UNI\geotest-atlas
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
& "D:\UNI\ANCILLARY WORK\.venv\Scripts\Activate.ps1"
code notebooks/geographical_event_analysis.ipynb
```

In VS Code select **D:\UNI\ANCILLARY WORK\.venv\Scripts\python.exe** as the notebook kernel, review configuration, then Run All. No new environment is needed. This implementation has not been executed or tested.

## Inputs and validation

Defaults use `outputs/exposure/all_chips/exposure_summary.csv`, its provenance, `outputs/enrichment/enriched/sen1floods11_enriched.parquet`, its manifest, full SSL4EO/TerraMesh biome/ecoregion CSVs and summary JSONs under `outputs/enrichment/statistics/`, and their enriched manifests. Only the downstream Parquet is read; large enriched inventories are not opened.

The adapter normalises a terminal `_label` and extracts event prefixes from numeric chip identifiers. All 446 chips, 11 events and four exposure inventories are expected. Bolivia remains included. These are events, not sovereign-country labels. Official splits are retained, not redesigned. Other downstream datasets can supply a `chip_id,event` CSV and explicit expected counts. Generic aggregation/plotting functions contain no event-name mappings.

Validation rejects duplicate/absent exposure pairs, conflicting splits, invalid counts/fractions, inconsistent overlap flags, incomplete event membership, downstream hash mismatches and incompatible RESOLVE versions. Missing ecological matches remain explicit, with missing/extra IDs recorded in provenance. Status counts and full-inventory totals are checked; no nearest-ecoregion substitution occurs.

**Provenance limits:** exposure records source sizes/timestamps rather than hashes. Category CSVs have no recorded hash linkage to the generating enriched Parquet. Recorded source names, inventory totals, statuses, ecological predicates and RESOLVE hashes can be compared, but cannot prove historical byte-for-byte equivalence. The analysis records this limitation, hashes the consumed saved files, and embeds the source manifests. Raw inputs and full pretraining Parquet are not rescanned.

## Definitions

- Event coverage: arithmetic chip mean of saved union coverage. Combined TerraMesh coverage is read directly, never summed from components.
- Positive overlap: positive area; zero nearest distance alone does not establish it.
- Distances: existing nearest-footprint kilometres, retaining the original AEQD approximation documented in exposure provenance.
- Dispersion: sample standard deviation (ddof=1), median and linear-interpolated quartiles; singleton standard deviation stays missing.
- Proximity: saved Haversine centre distances at 5/10/25/50/100 km. Record counts and exact-coordinate distinct-centre counts are averaged per chip. No globally unique event count is inferred.
- Ecology: existing non-unclassified, nonnull category filtering; ambiguous assignments may retain a common biome while lacking an ecoregion. Event composition keeps assignment statuses separate. Denominators include all event chips or all downstream/inventory records.
- Other assigned categories and unresolved assignments remain separate. Category presence/absence refers to complete validated category summaries. Residual distinct-centre counts are unavailable, not zero.
- Blank analytical CSV fields represent missing information. Plot filtering does not discard numerical categories.

## Outputs and figures

A fresh `outputs/analysis/geographical_events/` directory contains:

```text
chip_level_characterisation.csv
event_exposure_summary.csv
event_proximity_summary.csv
event_biome_composition.csv
event_ecoregion_composition.csv
ecological_inventory_representation.csv
provenance.json
figures/
  geographical_exposure_by_event.pdf / .png
  multiscale_geographical_proximity.pdf / .png
  ecological_composition_and_representation.pdf / .png
```

The first figure groups coverage, positive overlap and distance distributions by event; boxes retain zero observations and show 1.5-IQR whiskers/outliers. The second uses coordinated event/radius heatmaps of mean distinct centres with a common scale, optionally log1p, with missing cells hatched. The third integrates event biome composition, full-denominator global biome representation and a downstream-frequency-ranked ecoregion heatmap. All categories remain in the tables.

Plot functions reuse `scientific_style`, `compact_legend_layout` and `save_figure`. Native SciencePlots and the existing external stylesheet resolution are unchanged; RESOLVE colours are retained. Dimensions and ecoregion top-N are configurable without changing data.

To regenerate figures, set `REGENERATE_ONLY = True` in the notebook and run all cells. Only analytical CSVs and their provenance are read; the three figure files are refreshed. For a new numerical aggregation choose a fresh OUTPUT directory. Existing enrichment/exposure outputs are never overwritten.

## Interpretation

Exposure is potential geographical overlap, not proof of historical image reuse or supervised leakage. Reconstructed SSL4EO footprints are approximate. Record counts reflect inventory sizes and repeated acquisitions. Ecological categories describe centres, not footprint mixtures; membership establishes neither proximity nor spectral similarity. Event chips can be spatially correlated, and summaries describe sampled chips rather than complete territories. No temporal matching, hypothesis tests, performance correlations or geographical split generation are included.
