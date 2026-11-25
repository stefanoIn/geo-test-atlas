# Pretraining locations

Geographic metadata for the datasets used to pretrain the models evaluated in GeoTest. These files describe source dataset coverage; they are separate from pretrained weights and downstream training, validation and test splits.

## Organisation

Group metadata by **dataset and release**, rather than by model. Multiple models can share one source dataset, and a model can use several datasets. Store each metadata file only once.

```text
pretrained_models/
├── CROMA_large.pt
├── TerraMind_v1_large.pt
└── pretraining_locations/
    ├── README.md
    └── SSL4EO-S12/
        └── ssl4eo-s12_center_coords.csv
```

This tree shows the files currently present. Checkpoint filenames are unchanged because experiment configurations reference them.

For future additions, use distinct folders such as `SSL4EO-S12-v1.1/` and `TerraMesh/<revision>/`. Do not overwrite metadata from an earlier release. Record the source URL, dataset version or repository commit, retrieval date, coordinate reference system, available fields and associated model checkpoint here. Keep source filenames and distinguish pretraining train/validation partitions when provided.

## Available metadata: original SSL4EO-S12

- **Local file:** [SSL4EO-S12/ssl4eo-s12_center_coords.csv](SSL4EO-S12/ssl4eo-s12_center_coords.csv).
- **Official source:** [SSL4EO-S12 repository, Access the dataset](https://github.com/zhu-xlab/SSL4EO-S12#access-the-dataset).
- **Download linked by the dataset authors:** [ssl4eo-s12_center_coords.csv](https://drive.google.com/file/d/1RyJnGznSbMparS88BhHkXxETf0K-qYqI/view).
- **Release:** original SSL4EO-S12, not SSL4EO-S12 v1.1.
- **Coverage described by the authors:** 251,079 locations, four seasonal acquisitions per location, approximately 2.64 km × 2.64 km per patch.
- **Meaning:** patch-centre coordinates. These are not patch footprint polygons or the coordinates of random crops sampled during pretraining.
- **Provenance status:** supplied locally by the user; the original download date and file checksum have not been recorded. Confirm the CSV coordinate fields and reference system before spatial processing.

### Relationship to the models

| Model/checkpoint | Documented pretraining source | Use of this metadata |
|---|---|---|
| CROMA (`CROMA_large.pt`) | Original SSL4EO-S12, using paired Sentinel-1 GRD and Sentinel-2 L2A imagery | Relevant source-dataset location catalogue; not an independently verified log of samples consumed by the checkpoint. |
| TerraMind v1 (`TerraMind_v1_large.pt`) | TerraMesh, built from SSL4EO-S12 v1.1 and MajorTOM-derived data | This original SSL4EO-S12 CSV is not a complete or exact TerraMind pretraining catalogue. The copied TerraMesh metadata is stored separately. |

References: [CROMA paper](https://arxiv.org/abs/2311.00566), [TerraMind paper](https://arxiv.org/abs/2504.11171), [TerraMesh dataset](https://huggingface.co/datasets/ibm-esa-geospatial/TerraMesh).

## TerraMesh metadata

The public TerraMesh repository provides `train_metadata.parquet` and `val_metadata.parquet`, including sample IDs, centre longitude/latitude, CRS, bounds, geometry and acquisition timestamps. Only metadata is needed for coverage analysis; downloading imagery is unnecessary.

TerraMesh has been revised since the original TerraMind pretraining. Its documented August 2026 update removed some training samples near validation areas. Preserve the downloaded repository revision and establish its relationship to the pretrained checkpoint before describing it as the exact pretraining inventory. Current metadata can support a coverage analysis, but is not automatically the historical training manifest.

## Interpretation for geographic evaluation

- Distinguish unique geographic locations from repeated seasonal acquisitions.
- Use patch footprints for overlap analysis where available; matching centres alone can miss spatial overlap.
- Compare acquisition dates and product identifiers to distinguish geographic overlap from reuse of the same observation.
- Keep downstream train, validation, test and Bolivia partitions separate in analyses.
- Geographic exposure during self-supervised pretraining is not evidence that downstream labels were used. Report spatial exposure, observation overlap and supervised label leakage as separate questions.
