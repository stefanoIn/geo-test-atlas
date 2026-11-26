# Scientific figures

`geography/plotting.py` contains ecological and exposure-summary plotting. Existing enrichment and exposure entry points call it at the same points in their workflows. Geographical calculations, statistical definitions, saved tables, cache keys and provenance are unchanged.

The shared stylesheet resolves from `THESIS_MPLSTYLE`, otherwise `../figures/style/thesis.mplstyle` relative to the project location. Scoped SciencePlots science/no-latex styles are optional; a built-in serif Matplotlib fallback handles unavailable SciencePlots or stylesheets. No cross-project Python imports are used.

Generic series use the native colour/marker/line cycle in input order. Comparison bars add hatches after the colour palette repeats. RESOLVE colours and unclassified grey remain unchanged. Existing local/world exposure maps retain their source-colour semantics; no additional named colour mappings were introduced. Generic exposure-summary series use automatic colours and labels from the saved inventory identifiers.

Plot functions accept `show_titles` and `figsize`; functions with comparative legends accept `legend_loc` and `legend_ncol`. Category plots retain their top-20 selection. Exports are PDF and 300 DPI PNG; sampled centre points retain rasterisation inside the PDF. MathText requires no LaTeX installation.

## Regenerate figures from saved results only

From this project directory:

```powershell
$env:THESIS_MPLSTYLE = "../figures/style/thesis.mplstyle"
python scripts/plot_saved_results.py --enrichment outputs/enrichment --no-titles --legend-columns 2
python scripts/plot_saved_results.py --exposure outputs/exposure/all_chips/exposure_summary.csv --no-titles
```

Adjust paths to the existing outputs. The first command reads category CSV tables and compact provenance manifests, writing dataset figures under `figures/<dataset>/` and the comparison under `figures/`. The second reads the consolidated exposure CSV and writes its summary figures beside it. Neither command opens inventories, checkpoints or satellite imagery, or reruns enrichment/exposure. The existing summary plot's mean coverage and empirical distance distribution are retained.

Local maps cannot be regenerated from the exposure CSV alone because it does not contain the polygons. Sampled-centre maps likewise require coordinates not present in category tables; the plot-only command skips them rather than reopening inventories.

Existing missing-value conventions are preserved: absent entries in the cross-inventory biome pivot become zero, and centre maps use grey for unclassified/missing colours. Missing distance values retain the existing empirical-distribution treatment; they are not newly filtered or imputed. Interpret these conventions carefully.

No Python scripts, tests, analytical pipelines or figure generation were run during these changes. Check runtime compatibility and layout locally. The shared stylesheet is external and must be distributed separately or selected via the environment variable.
