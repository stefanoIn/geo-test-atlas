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


