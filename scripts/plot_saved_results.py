"""Regenerate figures from saved CSV tables without running geographical analysis."""
import argparse
import json
from pathlib import Path
import sys

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from geography.plotting import plot_category, plot_biome_comparison, plot_exposure_summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--enrichment", type=Path, help="Enrichment output directory")
    parser.add_argument("--exposure", type=Path, help="Existing exposure_summary.csv")
    parser.add_argument("--no-titles", action="store_true")
    parser.add_argument("--legend-loc", default="best")
    parser.add_argument("--legend-columns", type=int, default=1)
    args = parser.parse_args()
    if args.enrichment is None and args.exposure is None:
        parser.error("Specify --enrichment and/or --exposure")
    options = dict(show_titles=not args.no_titles, legend_loc=args.legend_loc,
                   legend_ncol=args.legend_columns)
    if args.enrichment:
        biomes = []
        for folder in sorted((args.enrichment / "statistics").iterdir()):
            if not folder.is_dir():
                continue
            manifest = args.enrichment / "enriched" / f"{folder.name}_enriched.provenance.json"
            scope = "scope not recorded"
            if manifest.is_file():
                scope = json.loads(manifest.read_text(encoding="utf-8"))["signature"]["inputs"]["scope"].replace("_", " ")
            title = f"{folder.name}_enriched ({scope})"
            for category in ("biome", "ecoregion"):
                path = folder / f"{category}_counts.csv"
                if not path.is_file():
                    continue
                table = pd.read_csv(path)
                plot_category(table, category, title,
                              args.enrichment / "figures" / folder.name,
                              show_titles=not args.no_titles)
                if category == "biome":
                    table["inventory"] = folder.name
                    biomes.append(table)
        if biomes:
            plot_biome_comparison(pd.concat(biomes, ignore_index=True),
                                 args.enrichment / "figures/biome_comparison.pdf", **options)
        print("Category/comparison figures exported. Centre maps require saved coordinates and are not regenerated.")
    if args.exposure:
        plot_exposure_summary(pd.read_csv(args.exposure), args.exposure.parent, **options)
        print("Exposure summary exported. Local maps require footprint geometries and are not regenerated.")


if __name__ == "__main__":
    main()
