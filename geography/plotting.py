"""Atlas-specific figures using the external thesis stylesheet."""
from contextlib import contextmanager
from pathlib import Path
import os
import warnings


@contextmanager
def scientific_style(path=None):
    """Scoped SciencePlots style with an optional external thesis stylesheet."""
    import matplotlib.style as style
    from cycler import cycler
    styles = ['default']
    try:
        import scienceplots  # Registers science and no-latex without activating them.
        styles.extend(['science', 'no-latex'])
    except ImportError:
        warnings.warn('SciencePlots unavailable; using the serif Matplotlib fallback.', stacklevel=2)
    styles.append({'font.family': 'serif', 'font.serif': ['STIXGeneral', 'DejaVu Serif'],
                   'mathtext.fontset': 'cm', 'text.usetex': False, 'font.size': 9,
                   'legend.fontsize': 7.5, 'legend.frameon': False,
                   'figure.facecolor': 'white', 'savefig.facecolor': 'white',
                   'savefig.dpi': 300, 'pdf.fonttype': 42,
                   'figure.figsize': [7.2, 3.2], 'axes.formatter.use_mathtext': True,
                   'axes.formatter.limits': [-3, 4],
                   'axes.prop_cycle': (cycler(linestyle=['-', '--', ':', '-.']) *
                       cycler(marker=['', 'o', 's']) * cycler(color=[
                       '#0072B2', '#D55E00', '#009E73', '#CC79A7', '#E69F00', '#56B4E9', '#000000']))})
    sheet = Path(path or os.environ.get('THESIS_MPLSTYLE') or
                 Path(__file__).resolve().parents[2] / 'figures/style/thesis.mplstyle')
    if sheet.is_file():
        import matplotlib as mpl
        try:
            styles.append(mpl.rc_params_from_file(sheet, fail_on_error=True, use_default_template=False))
        except (OSError, ValueError) as exc:
            warnings.warn(f'Cannot read thesis style {sheet}: {exc}; using fallback.', stacklevel=2)
    else:
        warnings.warn(f'Thesis stylesheet not found at {sheet}; using fallback.', stacklevel=2)
    with style.context(styles):
        yield


def save_figure(figure, path, **kwargs):
    """Export vector PDF and 300 DPI PNG from the same figure."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    for extension in ('.pdf', '.png'):
        figure.savefig(path.with_suffix(extension), dpi=300, **kwargs)

@scientific_style()
def plot_category(table, category, title, out, *, show_titles=True, figsize=None):
    import matplotlib.pyplot as plt
    shown = table.head(20).iloc[::-1]
    fig, ax = plt.subplots(figsize=figsize or (7.2, max(3, .25 * len(shown))))
    ax.barh(shown[category+'_name'], shown.fraction_all_records, color=shown[category+'_color'])
    ax.set(xlabel='Fraction of all inventory records', title=f'{title}: {category} composition'+(' (top 20)' if len(table)>20 else ''))
    if not show_titles:
        ax.set_title('')
    fig.tight_layout()
    save_figure(fig, Path(out)/f'{category}_distribution.pdf', bbox_inches='tight')
    plt.close(fig)


@scientific_style()
def plot_centres(points, title, out, *, show_titles=True, figsize=(7.2, 3.6)):
    import matplotlib.pyplot as plt
    import numpy as np
    finite = np.isfinite(points.center_lon) & np.isfinite(points.center_lat)
    colours = points.biome_color.fillna('#999999').copy()
    colours.loc[points.assignment_status == 'unclassified'] = '#999999'
    fig, ax = plt.subplots(figsize=figsize)
    ax.scatter(points.loc[finite, 'center_lon'], points.loc[finite, 'center_lat'],
               s=3, c=colours[finite], alpha=.6, rasterized=True)
    ax.set(xlim=(-180,180), ylim=(-90,90), xlabel='Longitude', ylabel='Latitude',
           title=f'{title}: sampled centres ({len(points):,}); colour denotes biome')
    if not show_titles:
        ax.set_title('')
    ax.grid(alpha=.2)
    fig.tight_layout()
    save_figure(fig, Path(out)/'centres.pdf')
    plt.close(fig)


@scientific_style()
def plot_biome_comparison(combined, output, *, show_titles=True, figsize=None,
                          legend_loc='best', legend_ncol=1):
    import matplotlib.pyplot as plt
    distribution = combined.pivot(index='biome_name', columns='inventory', values='fraction_all_records').fillna(0)
    fig, ax = plt.subplots(figsize=figsize or (7.2, max(4, .3*len(distribution))))
    distribution.plot.barh(ax=ax)
    # Colour cycles repeat; hatches distinguish subsequent palette-sized groups.
    capacity = len(set(plt.rcParams['axes.prop_cycle'].by_key()['color']))
    hatches = ['', '//', '\\\\', '..', 'xx']
    for index, container in enumerate(ax.containers):
        for rectangle in container:
            rectangle.set_hatch(hatches[(index // capacity) % len(hatches)])
    ax.set(xlabel='Fraction of all records', ylabel='', title='Centre-based biome composition (subset scope where indicated)')
    if not show_titles:
        ax.set_title('')
    ax.legend(loc=legend_loc, ncol=legend_ncol)
    fig.tight_layout()
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
def plot_exposure_summary(summary, out, *, show_titles=True, figsize=(7.2, 3.2),
                          legend_loc='best', legend_ncol=1):
    import matplotlib.pyplot as plt
    import numpy as np
    fig, axes = plt.subplots(1, 2, figsize=figsize)
    for source, group in summary.groupby("pretraining_inventory", sort=False):
        x = np.sort(group.nearest_footprint_km.to_numpy())
        axes[1].plot(x, np.arange(1,len(x)+1)/len(x), drawstyle="steps-post", label=source)
    grouped = summary.groupby("pretraining_inventory", sort=False).coverage_fraction.mean()
    axes[0].bar(range(len(grouped)), grouped.values*100, color=[line.get_color() for line in axes[1].lines])
    axes[0].set_xticks(range(len(grouped)), [s for s in grouped.index], rotation=25, ha="right", fontsize=8)
    axes[0].set_ylabel("Mean downstream coverage (%)")
    axes[0].set_ylim(0, 100)
    axes[1].set(xlabel="Nearest footprint distance (km)", ylabel="Fraction of analysed chips", ylim=(0,1.05))
    axes[1].legend(loc=legend_loc, ncol=legend_ncol)
    fig.suptitle(f"Metadata exposure · {summary.chip_id.nunique()} downstream chips\nGeographical exposure is not evidence of label leakage", fontsize=11)
    if not show_titles:
        fig.suptitle("")
    fig.tight_layout()
    save_figure(fig, out/"exposure_summary.png")
    plt.close(fig)


