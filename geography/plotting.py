"""Atlas-specific figures using the external thesis stylesheet."""
from contextlib import contextmanager
from pathlib import Path
import os
import warnings

EXPOSURE_LABELS = {"croma_ssl4eo": "CROMA — SSL4EO original",
          "terramind_ssl4eo": "TerraMind — SSL4EO v1.1",
          "terramind_majortom": "TerraMind — MajorTOM", "terramind": "TerraMind union"}


@contextmanager
def scientific_style(path=None):
    """Scoped native SciencePlots styles with an optional thesis stylesheet."""
    import matplotlib as mpl
    import matplotlib.style as style
    from cycler import cycler
    styles = ['default']
    try:
        import scienceplots  # Registers styles without activating them.
        styles.extend(['science', 'no-latex', 'vibrant'])
    except ImportError:
        warnings.warn('SciencePlots unavailable; using the serif Matplotlib fallback.', stacklevel=2)
        styles.append({'font.family': 'serif', 'mathtext.fontset': 'cm',
                       'text.usetex': False,
                       'axes.prop_cycle': cycler(color=[
                           '#0072B2', '#D55E00', '#009E73', '#CC79A7',
                           '#E69F00', '#56B4E9', '#000000'])})
    styles.append({'legend.frameon': False, 'savefig.dpi': 300,
                   'pdf.fonttype': 42, 'figure.figsize': [7.2, 3.2]})
    sheet = Path(path or os.environ.get('THESIS_MPLSTYLE') or
                 Path(__file__).resolve().parents[2] / 'figures/style/thesis.mplstyle')
    if sheet.is_file():
        try:
            styles.append(mpl.rc_params_from_file(sheet, fail_on_error=True, use_default_template=False))
        except (OSError, ValueError) as exc:
            warnings.warn(f'Cannot read thesis style {sheet}: {exc}; using fallback.', stacklevel=2)
    else:
        warnings.warn(f'Thesis stylesheet not found at {sheet}; using fallback.', stacklevel=2)
    with style.context(styles):
        # Preserve the active native palette; distinguish repeated colours by line style.
        colours = mpl.rcParams['axes.prop_cycle'].by_key()['color']
        mpl.rcParams['axes.prop_cycle'] = cycler(linestyle=['-', '--', ':', '-.']) * cycler(color=colours)
        yield


def compact_legend_layout(figure, *, w_pad=3.0, top=1.0):
    """Place existing legends just below axis labels using their rendered bounds."""
    from matplotlib.transforms import Bbox

    legends = [(legend, figure.axes) for legend in figure.legends]
    legends += [(axis.get_legend(), [axis]) for axis in figure.axes
                if axis.get_legend() is not None]
    for legend, _ in legends:
        legend.set_in_layout(False)
    figure.tight_layout(w_pad=w_pad, rect=(0, 0, 1, top))
    figure.canvas.draw()
    renderer = figure.canvas.get_renderer()
    gap = 4 * figure.dpi / 72
    for legend, axes in legends:
        bounds = [axis.get_tightbbox(renderer) for axis in axes]
        bottom = min(bound.y0 for bound in bounds if bound is not None)
        centre = (min(axis.bbox.x0 for axis in axes) +
                  max(axis.bbox.x1 for axis in axes)) / 2
        box = legend.get_window_extent(renderer)
        anchor = legend.get_bbox_to_anchor()
        shifted = Bbox.from_bounds(
            anchor.x0 + centre - (box.x0 + box.x1) / 2,
            anchor.y0 + bottom - gap - box.y1, anchor.width, anchor.height)
        legend.set_bbox_to_anchor(shifted.transformed(figure.transFigure.inverted()),
                                  transform=figure.transFigure)
    for legend, _ in legends:
        legend.set_in_layout(True)


def save_figure(figure, path, **kwargs):
    """Export vector PDF and 300 DPI PNG from the same figure."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    for extension in ('.pdf', '.png'):
        figure.savefig(path.with_suffix(extension), dpi=300, **kwargs)

@scientific_style()
def plot_category(table, category, title, out, *, show_titles=True, figsize=None):
    import matplotlib.pyplot as plt
    title = title.replace('stac_enriched', 'Sen1Floods11').replace('sen1floods11_enriched', 'Sen1Floods11')
    shown = table.head(20).iloc[::-1]
    fig, ax = plt.subplots(figsize=figsize or (7.2, max(3, .25 * len(shown))))
    ax.barh(shown[category+'_name'], shown.fraction_all_records,
            height=.7, color=shown[category+'_color'])
    ax.margins(y=.04)
    ax.tick_params(axis='y', which='both', left=False, right=False)
    ax.tick_params(axis='x', top=False)
    ax.minorticks_off()
    ax.grid(False, axis='y', which='both')
    ax.grid(True, axis='x', which='major')
    ax.set_xlabel('Fraction of all inventory records')
    if show_titles:
        ax.set_title(f'{category.capitalize()} composition' +
                     (' (top 20)' if len(table) > 20 else ''), pad=24)
        ax.annotate(title.replace('_', ' '), xy=(.5, 1), xycoords='axes fraction',
                    xytext=(0, 5), textcoords='offset points',
                    ha='center', va='bottom', fontsize=9)
    fig.tight_layout()
    save_figure(fig, Path(out)/f'{category}_distribution.pdf', bbox_inches='tight')
    plt.close(fig)


@scientific_style()
def plot_centres(points, title, out, *, show_titles=True, figsize=(7.2, 3.6)):
    import matplotlib.pyplot as plt
    import numpy as np
    title = title.replace('stac_enriched', 'Sen1Floods11').replace('sen1floods11_enriched', 'Sen1Floods11')
    finite = np.isfinite(points.center_lon) & np.isfinite(points.center_lat)
    colours = points.biome_color.fillna('#999999').copy()
    colours.loc[points.assignment_status == 'unclassified'] = '#999999'
    fig, ax = plt.subplots(figsize=figsize)
    ax.scatter(points.loc[finite, 'center_lon'], points.loc[finite, 'center_lat'],
               s=3, c=colours[finite], alpha=.6, rasterized=True)
    ax.set(xlim=(-180,180), ylim=(-90,90), xlabel='Longitude', ylabel='Latitude')
    if show_titles:
        ax.set_title('Sampled centres by biome', pad=24)
        ax.annotate(f"{title.replace('_', ' ')} · {len(points):,} centres",
                    xy=(.5, 1), xycoords='axes fraction', xytext=(0, 5),
                    textcoords='offset points', ha='center', va='bottom', fontsize=9)
    ax.minorticks_on()
    ax.grid(True, which='major')
    ax.grid(False, which='minor')
    fig.tight_layout()
    save_figure(fig, Path(out)/'centres.pdf')
    plt.close(fig)


@scientific_style()
def plot_biome_comparison(combined, output, *, show_titles=True, figsize=None,
                          legend_loc='upper center', legend_ncol=3):
    import matplotlib.pyplot as plt
    distribution = combined.pivot(index='biome_name', columns='inventory', values='fraction_all_records').fillna(0)
    fig, ax = plt.subplots(figsize=figsize or (7.2, max(4, .3*len(distribution))))
    distribution = distribution.rename(columns={'stac': 'Sen1Floods11', 'sen1floods11': 'Sen1Floods11'})
    distribution.plot.barh(ax=ax, width=.7)
    ax.margins(y=.04)
    ax.tick_params(axis='y', which='both', left=False, right=False)
    ax.tick_params(axis='x', top=False)
    # Colour cycles repeat; hatches distinguish subsequent palette-sized groups.
    capacity = len(set(plt.rcParams['axes.prop_cycle'].by_key()['color']))
    hatches = ['', '//', '\\\\', '..', 'xx']
    for index, container in enumerate(ax.containers):
        for rectangle in container:
            rectangle.set_hatch(hatches[(index // capacity) % len(hatches)])
    ax.set(xlabel='Fraction of all records', ylabel='', title='Centre-based biome composition (subset scope where indicated)')
    if not show_titles:
        ax.set_title('')
    ax.minorticks_off()
    ax.grid(False, axis='y', which='both')
    ax.grid(True, axis='x', which='major')
    ax.legend(loc='lower center' if legend_loc == 'best' else legend_loc,
              bbox_to_anchor=(.5, 0), frameon=False,
              ncol=max(1, min(legend_ncol, len(distribution.columns))))
    compact_legend_layout(fig)
    for extension in ('.pdf', '.png'):
        destination = Path(output).with_suffix(extension)
        destination.parent.mkdir(parents=True, exist_ok=True)
        pending = destination.with_name(destination.stem + '.pending' + destination.suffix)
        try:
            fig.savefig(pending, dpi=300, bbox_inches='tight')
            pending.replace(destination)
        finally:
            pending.unlink(missing_ok=True)
    plt.close(fig)

@scientific_style()
def plot_exposure_summary(summary, out, *, show_titles=True, figsize=(9, 3.2),
                          legend_loc='upper center', legend_ncol=4):
    import matplotlib.pyplot as plt
    import numpy as np
    fig, axes = plt.subplots(1, 2, figsize=figsize)
    for source, group in summary.groupby("pretraining_inventory", sort=False):
        x = np.sort(group.nearest_footprint_km.to_numpy())
        axes[1].plot(x, np.arange(1,len(x)+1)/len(x), drawstyle="steps-post",
                     marker="o" if len(x) == 1 else None, markersize=3,
                     label=EXPOSURE_LABELS.get(source, source.replace("_", " ")))
    grouped = summary.groupby("pretraining_inventory", sort=False).coverage_fraction.mean()
    axes[0].bar(range(len(grouped)), grouped.values*100,
                width=min(.72, .56 + .02 * len(grouped)),
                color=[line.get_color() for line in axes[1].lines])
    axes[0].set_xlim(-.65, max(0, len(grouped) - 1) + .65)
    axes[0].set_xticks(range(len(grouped)), [EXPOSURE_LABELS.get(s, s.replace("_", " ")).replace(" — ", "\n")
                                                   for s in grouped.index])
    axes[0].set_ylabel("Mean downstream coverage (%)")
    axes[0].set_ylim(0, 100)
    axes[1].set(xlabel="Nearest footprint distance (km)", ylabel="Fraction of analysed chips", ylim=(0,1.05))
    axes[0].minorticks_off()
    axes[0].grid(False, axis="x", which="both")
    axes[0].grid(True, axis="y", which="major")
    axes[0].tick_params(axis="x", top=False)
    axes[1].minorticks_on()
    axes[1].grid(True, axis="both", which="major")
    axes[1].grid(False, which="minor")
    handles, labels = axes[1].get_legend_handles_labels()
    labels = [label.replace(" — ", " (", 1) + ")" if " — " in label else label
              for label in labels]
    fig.legend(handles, labels, loc="lower center" if legend_loc == "best" else legend_loc,
               bbox_to_anchor=(.5, 0),
               ncol=max(1, min(legend_ncol, len(handles))), frameon=False)
    if show_titles:
        axes[0].set_title("(a) Footprint coverage")
        axes[1].set_title("(b) Nearest-footprint distance")
    compact_legend_layout(fig)
    save_figure(fig, out/"exposure_summary.png", bbox_inches="tight")
    plt.close(fig)




@scientific_style()
def plot_event_exposure(tables, output, *, inventories, event_order=None, figsize=(11, 5)):
    """Three coordinated event panels using saved union coverage and chip distances."""
    import numpy as np
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch
    summary = tables["event_exposure_summary"]
    chips = tables["chip_level_characterisation"]
    events = list(event_order or sorted(summary.event.unique()))
    palette = plt.rcParams["axes.prop_cycle"].by_key()["color"]
    fig, axes = plt.subplots(1, 3, figsize=figsize, sharey=True)
    y = np.arange(len(events))
    width = .72 / len(inventories)
    counts = chips.drop_duplicates("chip_id").groupby("event").size()
    for i, (inventory, label) in enumerate(inventories.items()):
        colour = palette[i % len(palette)]
        selected = summary[summary.pretraining_inventory.eq(inventory)].set_index("event").reindex(events)
        positions = y + (i - (len(inventories)-1)/2) * width
        axes[0].barh(positions, selected.coverage_fraction_mean * 100, height=width, color=colour)
        axes[1].barh(positions, selected.positive_overlap_fraction * 100, height=width, color=colour)
        distances = [chips.loc[chips.pretraining_inventory.eq(inventory) & chips.event.eq(e),
                               "nearest_footprint_km"].dropna().to_numpy() for e in events]
        boxes = axes[2].boxplot(distances, positions=positions, vert=False, widths=width*.8,
                               patch_artist=True, manage_ticks=False)
        for box in boxes["boxes"]:
            box.set_facecolor(colour)
        for element in ("whiskers", "caps", "medians"):
            for line in boxes[element]:
                line.set_color("black")
    for ax, title, xlabel in zip(axes, ("(a) Mean footprint coverage", "(b) Positive-area overlap",
                                      "(c) Nearest-footprint distance"),
                                 ("Coverage (%)", "Chips (%)", "Distance (km)")):
        ax.set_title(title)
        ax.set_xlabel(xlabel)
        ax.minorticks_off()
        ax.grid(False, axis="y")
        ax.grid(True, axis="x", which="major")
        ax.tick_params(axis="y", left=False, right=False)
        ax.tick_params(axis="x", top=False)
        ax.set_yticks(y, [f"{e} (n={counts[e]})" for e in events])
    axes[0].invert_yaxis()
    axes[0].set_xlim(0, 100)
    axes[1].set_xlim(0, 100)
    axes[2].set_xlim(left=0)
    fig.legend([Patch(facecolor=palette[i % len(palette)]) for i in range(len(inventories))],
               list(inventories.values()), loc="lower center", ncol=len(inventories), frameon=False)
    compact_legend_layout(fig)
    save_figure(fig, Path(output)/"geographical_exposure_by_event", bbox_inches="tight")
    plt.close(fig)


@scientific_style()
def plot_event_proximity(tables, output, *, inventories, event_order=None,
                         radii=(5, 10, 25, 50, 100), log1p=True, figsize=(9, 5)):
    """Shared heatmap scale; hatched cells indicate missing values, not zero."""
    import numpy as np
    import matplotlib.pyplot as plt
    from matplotlib.colors import Normalize
    from matplotlib.patches import Rectangle
    table = tables["event_proximity_summary"]
    events = list(event_order or sorted(table.event.unique()))
    matrices = [table[table.pretraining_inventory.eq(key)].pivot(
        index="event", columns="radius_km", values="unique_centres_mean").reindex(
            index=events, columns=radii).to_numpy() for key in inventories]
    values = [np.log1p(m) if log1p else m for m in matrices]
    finite = np.concatenate([m[np.isfinite(m)] for m in values])
    norm = Normalize(0, max(float(finite.max()), 1e-12) if len(finite) else 1)
    fig, axes = plt.subplots(1, len(inventories), figsize=figsize, sharey=True, squeeze=False)
    for i, (ax, label, matrix) in enumerate(zip(axes[0], inventories.values(), values)):
        mesh = ax.pcolormesh(np.ma.masked_invalid(matrix), cmap="viridis", norm=norm, shading="flat")
        for row, col in zip(*np.where(~np.isfinite(matrix))):
            ax.add_patch(Rectangle((col, row), 1, 1, fill=False, hatch="///"))
        ax.set(xticks=np.arange(len(radii))+.5, xticklabels=radii,
               yticks=np.arange(len(events))+.5, yticklabels=events,
               xlabel="Centre-to-centre radius (km)", title=f"({chr(97+i)}) {label}")
        ax.set_ylim(len(events), 0)
        ax.minorticks_off()
        ax.grid(False)
        ax.tick_params(which="both", top=False, right=False, length=0)
    compact_legend_layout(fig)
    fig.colorbar(mesh, ax=list(axes[0]), pad=.025, fraction=.035,
                 label=("log1p(mean distinct centres per chip)" if log1p else "Mean distinct centres per chip"))
    save_figure(fig, Path(output)/"multiscale_geographical_proximity", bbox_inches="tight")
    plt.close(fig)


@scientific_style()
def plot_event_ecology(tables, output, *, inventory_labels, event_order=None,
                       top_ecoregions=8, figsize=(12, 7), legend_ncol=3):
    """Event biome composition, full-denominator comparison and downstream-ranked ecoregions."""
    import textwrap
    import numpy as np
    import pandas as pd
    import matplotlib.pyplot as plt
    from matplotlib.patches import Patch, Rectangle
    from matplotlib.colors import Normalize
    if top_ecoregions < 1:
        raise ValueError("top_ecoregions must be positive")
    composition = tables["event_biome_composition"]
    rep = tables["ecological_inventory_representation"]
    biome = rep[rep.category.eq("biome")]
    events = list(event_order or sorted(composition.event.unique()))
    identities = biome[["category_name", "category_color"]].drop_duplicates("category_name")
    names = identities.category_name.tolist()
    colours = dict(zip(identities.category_name, identities.category_color))
    # Neutral hatching is reserved for residual/unresolved mass, not an ecological colour.
    residual = {"Other assigned categories": "//", "Unresolved assignments": ".."}
    fig, axes = plt.subplots(1, 3, figsize=figsize, gridspec_kw={"width_ratios": [1.15, 1, 1.6]})
    event_values = composition.assign(
        category_name=composition.category_name.where(composition.category_id.notna(), "Unresolved assignments")
    ).groupby(["event", "category_name"]).fraction_all_event_chips.sum().unstack(fill_value=0).reindex(events)
    for ax, labels, data in (
        (axes[0], events, event_values),
        (axes[1], list(inventory_labels.values()), biome.pivot(
            index="inventory", columns="category_name", values="fraction_all_records").reindex(inventory_labels)),
    ):
        left = np.zeros(len(labels))
        for name in names:
            values = data[name].to_numpy() if name in data else np.zeros(len(labels))
            ax.barh(np.arange(len(labels)), values*100, left=left*100, height=.65,
                    color=colours[name] if pd.notna(colours[name]) else "white",
                    edgecolor="black" if name in residual else "none", hatch=residual.get(name))
            left += values
        ax.set(yticks=np.arange(len(labels)), yticklabels=labels, xlim=(0,100), xlabel="All records (%)")
        ax.invert_yaxis()
        ax.minorticks_off()
        ax.grid(False, axis="y")
        ax.grid(True, axis="x", which="major")
        ax.tick_params(axis="y", left=False, right=False)
        ax.tick_params(axis="x", top=False)
    axes[0].set_xlabel("All event chips (%)")
    axes[0].set_title("(a) Event biome composition")
    axes[1].set_title("(b) Biome representation")
    eco = rep[rep.category.eq("ecoregion") & rep.category_id.notna()]
    ranked = eco[eco.inventory.eq("downstream")].sort_values(
        ["records", "category_id"], ascending=[False, True]).head(top_ecoregions)
    matrix = eco.pivot(index="category_id", columns="inventory", values="fraction_all_records").reindex(
        index=ranked.category_id, columns=inventory_labels).to_numpy()*100
    ax = axes[2]
    if not len(ranked):
        raise ValueError("No assigned downstream ecoregions available for the ecological figure")
    mesh = ax.pcolormesh(np.ma.masked_invalid(matrix), cmap="viridis",
                        norm=Normalize(0, max(np.nanmax(matrix), 1e-12)), shading="flat")
    for row, col in zip(*np.where(~np.isfinite(matrix))):
        ax.add_patch(Rectangle((col, row), 1, 1, fill=False, hatch="///"))
    labels = [textwrap.fill(str(row.category_name), 25) + "\n" +
              textwrap.fill(str(row.events), 25) for row in ranked.itertuples()]
    ax.set(xticks=np.arange(len(inventory_labels))+.5, xticklabels=list(inventory_labels.values()),
           yticks=np.arange(len(labels))+.5, yticklabels=labels, title="(c) Ecoregion representation")
    ax.invert_yaxis()
    ax.minorticks_off()
    ax.grid(False)
    ax.tick_params(which="both", top=False, right=False, length=0)
    handles = [Patch(facecolor=colours[n] if pd.notna(colours[n]) else "white",
                     edgecolor="black" if n in residual else "none", hatch=residual.get(n)) for n in names]
    fig.legend(handles, [textwrap.fill(n, 38) for n in names], loc="lower center",
               ncol=legend_ncol, frameon=False)
    compact_legend_layout(fig, w_pad=2)
    fig.colorbar(mesh, ax=ax, pad=.025, fraction=.04, label="All inventory records (%)")
    # The colour bar preserves vertical bounds; the shared legend remains below the labels.
    fig.canvas.draw()
    save_figure(fig, Path(output)/"ecological_composition_and_representation", bbox_inches="tight")
    plt.close(fig)
