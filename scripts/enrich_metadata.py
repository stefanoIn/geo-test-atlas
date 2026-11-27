"""Enrich inventories and report centre-based ecological composition.

The default uses bounded validation subsets. --full explicitly enriches complete
inventories; repair comparisons always use the bounded subsets.
"""
from contextlib import closing, nullcontext
import argparse
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import geopandas as gpd
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import shapely
from tqdm.auto import tqdm
from geography.metadata import iter_centres
from geography.plotting import plot_category, plot_centres, plot_biome_comparison
from geography.enrichment import (prepare_resolve, enrich_inventory, compare_repairs,
                                  fingerprint, classified_regions, pending_output)


DEFAULT_INVENTORIES = {
    'ssl4eo': Path('data/inventories/SSL4EO-S12/ssl4eo-s12_center_coords.csv'),
    'terramesh': Path('data/inventories/TerraMesh/train_metadata.parquet'),
    'stac': Path('../GeoTest/data/sen1floods11/catalog/sen1floods11_hand_labeled_label/collection.json'),
}


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resolve-source', type=Path, default=Path('data/environmental/resolve_2017/Ecoregions2017.shp'))
    parser.add_argument('--validated', type=Path, default=Path('outputs/enrichment/validation/resolve_2017_validated.parquet'))
    parser.add_argument('--dataset', choices=list(DEFAULT_INVENTORIES) + ['sen1floods11'], nargs='+',
                        metavar='{ssl4eo,terramesh,sen1floods11}',
                        help='Inventories to process (default: all). The legacy stac alias is accepted.')
    parser.add_argument('--inventory', action='append', metavar='KIND=PATH',
                        help='Override inventory paths. Without --dataset, process only these overrides.')
    parser.add_argument('--output-dir', type=Path, help='Ecological output root: enriched/, validation/, statistics/ and figures/.')
    parser.add_argument('--sample-records', type=int, default=4096)
    parser.add_argument('--batch-size', type=int, default=65536)
    parser.add_argument('--full', action='store_true')
    parser.add_argument('--aggregation-backend', choices=['pandas', 'sqlite'], default='pandas',
                        help='Pandas for in-memory aggregation; SQLite for lower RAM use.')
    parser.add_argument('--report-only', action='store_true',
                        help='Regenerate reports from enriched files in --output-dir, without enrichment.')
    args = parser.parse_args(argv)
    if args.sample_records <= 0 or args.batch_size <= 0:
        parser.error('Sample and batch sizes must be positive')
    if args.dataset:
        args.dataset = ['stac' if kind == 'sen1floods11' else kind for kind in args.dataset]
    overrides = {}
    for spec in args.inventory or []:
        kind, separator, path = spec.partition('=')
        kind = 'stac' if kind == 'sen1floods11' else kind
        if not separator or not path or kind not in DEFAULT_INVENTORIES:
            parser.error('--inventory must be ssl4eo=PATH, terramesh=PATH or sen1floods11=PATH')
        if kind in overrides:
            parser.error(f'Duplicate inventory override: {kind}')
        overrides[kind] = Path(path)
    selected = args.dataset or list(overrides) or list(DEFAULT_INVENTORIES)
    if len(selected) != len(set(selected)):
        parser.error('Each dataset can be selected only once')
    if set(overrides) - set(selected):
        parser.error('Inventory overrides must belong to the selected datasets')
    paths = DEFAULT_INVENTORIES | overrides
    args.inventory = [f'{kind}={paths[kind]}' for kind in selected]
    if args.output_dir is None:
        args.output_dir = Path('outputs/enrichment' if args.full or args.report_only else 'outputs/enrichment_subsets')
    return args


def parquet_rows(path):
    with pq.ParquetFile(path) as parquet:
        return parquet.metadata.num_rows


def representative_centres(kind, path, size):
    """Bounded TerraMesh sampling across row groups; no full Parquet scan."""
    if kind == 'terramesh':
        with pq.ParquetFile(path) as parquet:
            group_count = parquet.num_row_groups
        # Row groups span the file's source ordering; sampling is not uniform globally.
        groups = np.unique(np.linspace(0, group_count-1, min(16,group_count), dtype=int))
        quota = max(1, int(np.ceil(size / len(groups))))
        pieces = []
        for group in groups:
            piece = next(iter_centres(kind, path, batch_size=quota, row_groups={int(group)}))
            pieces.append(piece)
        result = pd.concat(pieces, ignore_index=True)
        if len(result) > size:
            result = result.sample(size, random_state=42).sort_values('source_row').reset_index(drop=True)
        return result
    frames = list(iter_centres(kind, path))
    result = pd.concat(frames, ignore_index=True)
    if kind != 'stac' and len(result) > size:
        result = result.sample(size, random_state=42).sort_values('source_row').reset_index(drop=True)
    return result


def _aggregate(path, backend):
    columns = ['center_lon', 'center_lat', 'biome_id', 'biome_name', 'biome_color',
               'ecoregion_id', 'ecoregion_name', 'ecoregion_color', 'assignment_status']
    centres, frames, tables = [], [], {}
    print(f'Aggregating {path.name} with {backend}...', flush=True)
    with tempfile.TemporaryDirectory() as temp, (
            closing(sqlite3.connect(str(Path(temp)/'counts.sqlite'))) if backend == 'sqlite'
            else nullcontext()) as db:
        with pq.ParquetFile(path) as parquet, tqdm(total=parquet.metadata.num_rows,
                desc=f'Read {path.stem}', unit='records') as progress:
            for batch in parquet.iter_batches(batch_size=65536, columns=columns):
                frame = batch.to_pandas()
                if backend == 'pandas':
                    frames.append(frame)
                else:
                    frame.to_sql('records', db, if_exists='append', index=False)
                # Preserve the existing per-batch plotting sample and random seed.
                centres.append(frame.sample(min(128, len(frame)), random_state=42))
                progress.update(len(frame))
        if backend == 'pandas':
            data = pd.concat(frames, ignore_index=True)
            del frames
            count = len(data)
            statuses = data.assignment_status.value_counts(sort=False, dropna=True)
            statuses = {str(key): int(value) for key, value in statuses.items() if value}
        else:
            count = db.execute('select count(*) from records').fetchone()[0]
            statuses = dict(db.execute('select assignment_status,count(*) from records group by assignment_status'))
        summary = dict(records=count, assignment_status_counts=statuses,
                       uniquely_classified_records=sum(statuses.get(k, 0) for k in ['classified', 'boundary']))
        for category in ['biome', 'ecoregion']:
            print(f'Counting {category} records and exact unique centres...', flush=True)
            key = category + '_id'
            groups = [key, category + '_name', category + '_color']
            if backend == 'pandas':
                # Match SQL NULL filtering and retain null names/colours in groups.
                valid = data.assignment_status.notna() & data.assignment_status.ne('unclassified') & data[key].notna()
                selected = data.loc[valid, groups + ['center_lon', 'center_lat']]
                table = selected.groupby(groups, dropna=False, observed=True, sort=True).size().reset_index(name='records')
                table = table.sort_values('records', ascending=False, kind='stable')
                unique = selected[[key, 'center_lon', 'center_lat']].drop_duplicates()
                unique = unique.groupby(key, observed=True, sort=True).size().reset_index(name='unique_centres')
                del selected
            else:
                valid = "assignment_status != 'unclassified' and " + key + ' is not null'
                table = pd.read_sql_query(f'''select {key}, {category}_name, {category}_color,
                    count(*) as records from records where {valid}
                    group by {key}, {category}_name, {category}_color order by records desc''', db)
                unique = pd.read_sql_query(f'''select {key},count(*) as unique_centres from
                    (select distinct {key},center_lon,center_lat from records where {valid})
                    group by {key}''', db)
            table = table.merge(unique, on=key)
            table['fraction_all_records'] = table.records/count
            tables[category] = table
            summary['represented_'+category+'s'] = len(table)
    return tables, summary, centres


def _describe(path, out, aggregation_backend='pandas'):
    """Aggregate ecological assignments and plot the existing bounded centre sample."""
    if aggregation_backend not in {'pandas', 'sqlite'}:
        raise ValueError('aggregation_backend must be pandas or sqlite')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    out.mkdir(parents=True, exist_ok=True)
    scope=json.loads(path.with_suffix('.provenance.json').read_text())['signature']['inputs']['scope']
    title=f'{path.stem} ({scope.replace("_", " ")})'
    tables, summary, centres = _aggregate(path, aggregation_backend)
    print(f'Generating category figures for {path.stem}...', flush=True)
    for category, table in tables.items():
        table.to_csv(out/f'{category}_counts.csv', index=False)
        plot_category(table, category, title, out)
    print(f'Generating sampled-centre figure for {path.stem}...', flush=True)
    points=pd.concat(centres,ignore_index=True)
    if len(points)>10000:
        points=points.sample(10000,random_state=42)
    plot_centres(points, title, out)
    summary['plot_records']=len(points)
    (out/'summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    return tables['biome']


def describe(path, out, aggregation_backend='pandas', *, figures_dir=None):
    """Stage reports so interruption during aggregation preserves completed reports."""
    path, out = Path(path), Path(out)
    figures_dir = Path(figures_dir) if figures_dir is not None else out
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.describe-', dir=out.parent) as temporary:
        staging = Path(temporary)
        try:
            result = (_describe(path, staging) if aggregation_backend == 'pandas' else
                      _describe(path, staging, aggregation_backend))
            out.mkdir(parents=True, exist_ok=True)
            figures_dir.mkdir(parents=True, exist_ok=True)
            # The summary is the completion marker and is published last.
            (out / 'summary.json').unlink(missing_ok=True)
            for file in sorted(staging.iterdir(), key=lambda p: p.name == 'summary.json'):
                destination = figures_dir if file.suffix in {'.pdf', '.png'} else out
                file.replace(destination / file.name)
            return result
        finally:
            import matplotlib.pyplot as plt
            plt.close('all')


def main():
    args = parse_args()
    start=time.perf_counter()
    enriched_dir = args.output_dir/'enriched'
    validation_dir = args.output_dir/'validation'
    figures_dir = args.output_dir/'figures'
    for spec in args.inventory:
        kind = spec.split('=', 1)[0]
        if (args.output_dir/f'{kind}_enriched.parquet').exists() and not (enriched_dir/f'{kind}_enriched.parquet').exists():
            raise ValueError('Legacy outputs found. Expected inventories under enriched/; legacy flat outputs are not supported here.')
    if not args.report_only:
        regions=prepare_resolve(args.resolve_source,args.validated)
        original=gpd.read_file(args.resolve_source)
    enriched_dir.mkdir(parents=True,exist_ok=True)
    figures_dir.mkdir(parents=True,exist_ok=True)
    if not args.report_only:
        validation_dir.mkdir(parents=True,exist_ok=True)
    all_biomes=[];report={}
    for spec in args.inventory:
        kind,source=spec.split('=',1);source=Path(source)
        if args.report_only:
            output = enriched_dir/f'{kind}_enriched.parquet'
            manifest = output.with_suffix('.provenance.json')
            if not output.is_file() or not manifest.is_file():
                raise FileNotFoundError(f'Completed enrichment and provenance required: {output}')
            print(f'Checking completed output fingerprint: {output}', flush=True)
            if json.loads(manifest.read_text()).get('output_fingerprint') != fingerprint(output):
                raise ValueError(f'Enriched output does not match its provenance: {output}')
            table = describe(output, args.output_dir/'statistics'/kind, args.aggregation_backend, figures_dir=figures_dir/('sen1floods11' if kind == 'stac' else kind))
            table['inventory'] = kind
            all_biomes.append(table)
            continue
        print(f'Validating {kind}: {source}',flush=True)
        sample=representative_centres(kind,source,args.sample_records)
        comparison=compare_repairs(sample,original,regions)
        with pending_output(validation_dir/f'{kind}_repair_comparison.parquet') as pending:
            comparison.to_parquet(pending,compression='zstd',index=False)
        with pending_output(validation_dir/f'{kind}_assignment_discrepancies.csv') as pending:
            comparison[comparison.comparison_status!='unchanged'].to_csv(pending,index=False)
        invalid_tree=shapely.STRtree(original.loc[~original.is_valid].geometry)
        points=shapely.points(sample.center_lon,sample.center_lat)
        candidate_count=len(np.unique(invalid_tree.query(points)[0]))
        print(f'Checking source fingerprints for {kind}...', flush=True)
        provenance=dict(source=fingerprint(source),kind=kind,
            centre_method='existing inventory coordinates; STAC explicit centre or planar WGS84 footprint centroid',
            scope='full' if args.full or kind=='stac' else 'validation_subset',
            sample_records=args.sample_records if not args.full else None,
            sampling='all STAC items; SSL4EO fixed-seed random sample; TerraMesh evenly selected row-group prefixes',
            record_identity='source fingerprint plus source_row; original sample_id and tar/source_item retained')
        output=enriched_dir/f'{kind}_enriched.parquet'
        info=enrich_inventory(iter_centres(kind,source,args.batch_size) if args.full else
                              (sample.iloc[i:i+args.batch_size] for i in range(0,len(sample),args.batch_size)),
                              args.validated,output,provenance, total_records=(len(sample) if not args.full else
                                  parquet_rows(source) if kind == 'terramesh' else None))
        reloaded=pd.read_parquet(output) if not args.full else None
        if reloaded is not None:
            pd.testing.assert_frame_equal(reloaded[list(sample.columns)],sample.reset_index(drop=True),
                                          check_dtype=False, check_exact=True)
            assert reloaded.center_lon.dtype == np.dtype('float64')
            assert reloaded.center_lat.dtype == np.dtype('float64')
        info['comparison_counts']=comparison.comparison_status.value_counts().to_dict()
        info['comparison_records']=len(sample)
        info['sample_id_duplicates_in_subset']=int(sample.sample_id.duplicated().sum())
        info['repair_bbox_candidate_records']=candidate_count
        info['source_counts_in_subset']=sample.source.value_counts().to_dict()
        report[kind]=info
        table=describe(output,args.output_dir/'statistics'/kind,args.aggregation_backend, figures_dir=figures_dir/('sen1floods11' if kind == 'stac' else kind));table['inventory']=kind;all_biomes.append(table)
        print(kind,info['comparison_counts'],info['assignment_status_counts'],flush=True)
    import matplotlib.pyplot as plt
    print('Generating inventory comparison figure...', flush=True)
    combined=pd.concat(all_biomes,ignore_index=True)
    plot_biome_comparison(combined, figures_dir/'biome_comparison.pdf')
    if args.report_only:
        print(f'Reports completed in {time.perf_counter()-start:.1f}s', flush=True)
        return
    report['elapsed_seconds']=time.perf_counter()-start
    try:
        import psutil
        report['peak_working_set_bytes']=psutil.Process().memory_info().peak_wset
    except (ImportError,AttributeError):
        report['peak_working_set_bytes']=None
    with pending_output(validation_dir/'validation_summary.json') as pending:
        pending.write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(f'Completed in {report["elapsed_seconds"]:.1f}s',flush=True)


if __name__=='__main__':
    try:
        main()
    except KeyboardInterrupt:
        print('\nInterrupted. Completed outputs are retained; rerun the same command to reuse valid caches.', file=sys.stderr)
        sys.exit(130)
