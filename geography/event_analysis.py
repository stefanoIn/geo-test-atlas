"""Descriptive event summaries from saved exposure and ecological results only."""
from pathlib import Path
import hashlib
import json
import re
import warnings
from datetime import datetime, timezone

import numpy as np
import pandas as pd

RADII = (5, 10, 25, 50, 100)
TABLES = ("chip_level_characterisation", "event_exposure_summary",
          "event_proximity_summary", "event_biome_composition",
          "event_ecoregion_composition", "ecological_inventory_representation")


def _json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def _hash(path):
    with Path(path).open("rb") as stream:
        digest = hashlib.sha256()
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _ids(values):
    _require(values.notna().all(), "Missing sample identifiers")
    return values.astype(str).str.replace(r"_label$", "", regex=True)


def sen1floods11_events(chip_ids):
    """Dataset adapter: event prefix followed by an underscore and numeric chip ID."""
    ids = _ids(pd.Series(chip_ids))
    events = ids.str.extract(r"^(.+)_([0-9]+)$")[0]
    _require(events.notna().all(), "Unexpected Sen1Floods11 identifier; provide explicit event metadata")
    return pd.DataFrame({"chip_id": ids, "event": events})


def load_characterisation(exposure_csv, downstream_parquet, enrichment_root, *,
                          event_metadata=None, expected_chips=446, expected_events=11,
                          expected_inventories=("croma_ssl4eo", "terramind_majortom",
                                                "terramind_ssl4eo", "terramind"),
                          radii=RADII):
    """Load small saved outputs; check correspondence without opening raw inventories."""
    exposure_csv, downstream_parquet = Path(exposure_csv), Path(downstream_parquet)
    root = Path(enrichment_root)
    _require(list(radii) == sorted(set(radii)) and all(r > 0 for r in radii),
             "Radii must be positive, unique and increasing")
    paths = [exposure_csv, exposure_csv.parent / "provenance.json", downstream_parquet,
             downstream_parquet.with_suffix(".provenance.json")]
    exp = pd.read_csv(exposure_csv)
    ep = _json(paths[1])
    dp = _json(paths[3])
    _require(dp["signature"]["inputs"]["scope"] == "full", "Downstream enrichment is not complete")
    _require(set(radii).issubset(ep["arguments"]["radii"]), "Requested radii absent from exposure provenance")
    exp["chip_id"] = _ids(exp.chip_id)
    _require(not exp.duplicated(["chip_id", "pretraining_inventory"]).any(),
             "Duplicate chip/inventory exposure rows")
    _require(exp.split.notna().all() and exp.groupby("chip_id").split.nunique().eq(1).all(),
             "Missing or conflicting split membership")
    chips = exp[["chip_id", "split"]].drop_duplicates()
    if expected_chips is not None:
        _require(len(chips) == expected_chips, f"Expected {expected_chips} chips; found {len(chips)}")
    _require(set(exp.pretraining_inventory) == set(expected_inventories), "Unexpected exposure inventories")
    _require(exp.groupby("chip_id").size().eq(len(expected_inventories)).all(),
             "Incomplete chip/inventory exposure grid")
    _require(chips.split.value_counts().to_dict() == ep["split_counts"], "Exposure split counts disagree with provenance")
    required = ["coverage_fraction", "nearest_footprint_km", "overlapping_records",
                "overlapping_unique_centres"] + [
        f"{kind}_within_{r:g}km" for r in radii for kind in ("records", "unique_centres")]
    _require(np.isfinite(exp[required].to_numpy(dtype=float)).all(), "Missing/nonfinite exposure measurements")
    _require(exp[required].ge(0).all().all() and exp.coverage_fraction.le(1).all(),
             "Exposure values outside their valid ranges")
    for col in required[2:]:
        _require(exp[col].mod(1).eq(0).all(), f"Noninteger count: {col}")
    overlap = exp.physical_overlap.astype(str).str.lower().map({"true": True, "false": False})
    _require(overlap.notna().all() and overlap.eq(exp.coverage_fraction.gt(0)).all(),
             "Positive-area overlap disagrees with coverage")
    exp["physical_overlap"] = overlap.astype(bool)
    _require(exp.overlapping_unique_centres.le(exp.overlapping_records).all(), "Centre counts exceed records")
    for kind in ("records", "unique_centres"):
        cols = [f"{kind}_within_{r:g}km" for r in radii]
        _require((np.diff(exp[cols], axis=1) >= 0).all(), "Proximity counts decrease with radius")
    for r in radii:
        _require(exp[f"unique_centres_within_{r:g}km"].le(exp[f"records_within_{r:g}km"]).all(),
                 "Nearby centre counts exceed records")

    if event_metadata is None:
        events = sen1floods11_events(chips.chip_id)
    else:
        event_metadata = Path(event_metadata)
        paths.append(event_metadata)
        events = pd.read_csv(event_metadata, dtype={"chip_id": str, "event": str})
        events["chip_id"] = _ids(events.chip_id)
    _require(not events.chip_id.duplicated().any() and events.event.notna().all(),
             "Duplicate or missing event assignments")
    _require(set(events.chip_id) == set(chips.chip_id), "Event membership is incomplete or has extra chips")
    if expected_events is not None:
        _require(events.event.nunique() == expected_events, f"Expected {expected_events} events")

    columns = ["sample_id", "center_lon", "center_lat", "assignment_status",
               "matched_ecoregion_ids", "realm"] + [
        f"{cat}_{field}" for cat in ("biome", "ecoregion") for field in ("id", "name", "color")]
    eco = pd.read_parquet(downstream_parquet, columns=columns)
    eco["chip_id"] = _ids(eco.sample_id)
    _require(not eco.chip_id.duplicated().any(), "Ecological IDs collide after _label normalisation")
    _require(len(eco) == dp["output_records"], "Downstream record count disagrees with provenance")
    fingerprints = list(dp.get("output_fingerprint", {}).values())
    _require(len(fingerprints) == 1 and _hash(downstream_parquet) == fingerprints[0],
             "Downstream Parquet does not match its provenance")
    notes = [
        "Exposure provenance has sizes/timestamps, not content hashes: historical source equivalence is not cryptographically verifiable.",
        "Category CSVs have no source hash linkage; totals, status counts and frequencies are checked against enrichment manifests.",
        "Pretraining Parquet files are not reopened or hashed; saved full-inventory statistics are used."
    ]
    missing = sorted(set(chips.chip_id) - set(eco.chip_id))
    extra = sorted(set(eco.chip_id) - set(chips.chip_id))
    if missing or extra:
        notes.append(f"Ecological join: {len(missing)} missing and {len(extra)} extra IDs; see provenance.")
    chip_eco = chips.merge(events[["chip_id", "event"]], validate="one_to_one").merge(
        eco, on="chip_id", how="left", validate="one_to_one")
    chip_eco["assignment_status"] = chip_eco.assignment_status.astype("string").fillna("missing_metadata")
    combined = exp.merge(chip_eco.drop(columns="split"), on="chip_id", validate="many_to_one")
    manifests = {"downstream": dp}
    inventories = {}
    for dataset, exposure_keys in (
        ("ssl4eo", ["croma_ssl4eo"]),
        ("terramesh", ["terramind_ssl4eo", "terramind_majortom"]),
    ):
        folder = root / "statistics" / dataset
        mp = root / "enriched" / f"{dataset}_enriched.provenance.json"
        sp = folder / "summary.json"
        paths.extend([mp, sp])
        manifest, summary = _json(mp), _json(sp)
        manifests[dataset] = manifest
        _require(manifest["signature"]["inputs"]["scope"] == "full", f"{dataset} is not a full inventory")
        _require(summary["records"] == manifest["output_records"] ==
                 sum(ep["inventory_records"][k] for k in exposure_keys), f"{dataset} record totals disagree")
        _require({k: v for k, v in summary["assignment_status_counts"].items() if v} ==
                 {k: v for k, v in manifest["assignment_status_counts"].items() if v},
                 f"{dataset} status totals disagree")
        _require(sum(summary["assignment_status_counts"].values()) == summary["records"], "Status counts incomplete")
        inventories[dataset] = {"summary": summary}
        for cat in ("biome", "ecoregion"):
            p = folder / f"{cat}_counts.csv"
            paths.append(p)
            table = pd.read_csv(p)
            _require(not table[f"{cat}_id"].duplicated().any(), f"Duplicate {dataset} {cat} IDs")
            _require(table.records.ge(0).all() and table.unique_centres.between(0, table.records).all(),
                     "Invalid ecological category counts")
            _require(len(table) == summary["represented_" + cat + "s"], "Incomplete category table")
            statuses = summary["assignment_status_counts"]
            unique = sum(statuses.get(s, 0) for s in ("classified", "boundary"))
            ambiguous = sum(statuses.get(s, 0) for s in ("shared_boundary", "multiple_matches"))
            _require(unique <= table.records.sum() <= unique + ambiguous,
                     "Category totals disagree with assignment statuses")
            _require(table.records.mod(1).eq(0).all() and table.unique_centres.mod(1).eq(0).all(),
                     "Noninteger ecological counts")
            _require(np.allclose(table.fraction_all_records, table.records / summary["records"],
                                 rtol=1e-10, atol=1e-12), "Category frequency denominator mismatch")
            inventories[dataset][cat] = table
    resolve_hashes = [sorted(m["signature"]["resolve"].values()) for m in manifests.values()]
    _require(all(h == resolve_hashes[0] for h in resolve_hashes), "Incompatible validated RESOLVE versions")
    _require(len({m["signature"]["predicate"] for m in manifests.values()}) == 1, "Incompatible ecological predicates")
    # Check recorded source names without traversing any catalogues or inventories.
    for name, argument in (("downstream", "catalog"), ("ssl4eo", "ssl4eo"), ("terramesh", "terramesh")):
        basename = re.split(r"[\\/]", ep["arguments"][argument])[-1].lower()
        source_names = [re.split(r"[\\/]", p)[-1].lower()
                        for p in manifests[name]["signature"]["inputs"]["source"]]
        _require(basename in source_names, f"{name}: exposure/enrichment source names differ")
    for note in notes:
        warnings.warn(note, stacklevel=2)
    audit = dict(created_utc=datetime.now(timezone.utc).isoformat(),
                 inputs={str(p): _hash(p) for p in paths},
                 exposure_provenance=ep, enrichment_manifests=manifests,
                 ecological_missing_ids=missing, ecological_extra_ids=extra,
                 limitations=notes, radii_km=list(radii),
                 downstream_assignment_status_counts=chip_eco.assignment_status.value_counts().to_dict(),
                 event_method="explicit metadata" if event_metadata else "Sen1Floods11 identifier prefix",
                 event_counts=chip_eco.event.value_counts().sort_index().to_dict())
    return combined, inventories, audit


def aggregate_events(chips, inventories, *, radii=RADII):
    """Chip-weighted summaries; no spatial operations or invented missing measurements."""
    groups = chips.groupby(["event", "pretraining_inventory"], sort=True)
    rows, proximity = [], []
    for (event, inventory), group in groups:
        row = dict(event=event, pretraining_inventory=inventory, chips=len(group),
                   positive_overlap_chips=int(group.physical_overlap.sum()),
                   positive_overlap_fraction=float(group.physical_overlap.mean()),
                   zero_distance_without_overlap_chips=int(
                       (group.nearest_footprint_km.eq(0) & ~group.physical_overlap).sum()))
        for metric in ("coverage_fraction", "nearest_footprint_km",
                       "overlapping_records", "overlapping_unique_centres"):
            values = group[metric]
            for stat, value in (("mean", values.mean()), ("median", values.median()),
                                ("std", values.std(ddof=1)), ("q25", values.quantile(.25)),
                                ("q75", values.quantile(.75))):
                row[f"{metric}_{stat}"] = value
        rows.append(row)
        for radius in radii:
            item = dict(event=event, pretraining_inventory=inventory, radius_km=radius, chips=len(group))
            for kind in ("records", "unique_centres"):
                values = group[f"{kind}_within_{radius:g}km"]
                item[f"{kind}_mean"] = values.mean()
                item[f"{kind}_median"] = values.median()
            proximity.append(item)
    downstream = chips.drop_duplicates("chip_id")
    compositions, representations = {}, []
    for cat in ("biome", "ecoregion"):
        key, name, color = [f"{cat}_{suffix}" for suffix in ("id", "name", "color")]
        frame = downstream.copy()
        frame["category_id"] = frame[key]
        # Match the existing descriptive filtering; ambiguous common-biome assignments remain valid.
        valid = frame.assignment_status.ne("unclassified") & frame[key].notna()
        frame.loc[~valid, "category_id"] = np.nan
        frame["category_name"] = frame[name].where(valid, "Unresolved: " + frame.assignment_status)
        frame["category_color"] = frame[color].where(valid)
        groupcols = ["event", "category_id", "category_name", "category_color", "assignment_status"]
        table = frame.groupby(groupcols, dropna=False, observed=True).size().reset_index(name="chips")
        table["event_chips"] = table.event.map(downstream.groupby("event").size())
        table["fraction_all_event_chips"] = table.chips / table.event_chips
        compositions[cat] = table
        for category_id, selected in frame[valid].groupby("category_id"):
            row = dict(category=cat, category_id=category_id,
                       category_name=selected[name].iloc[0], category_color=selected[color].iloc[0],
                       events="; ".join(sorted(selected.event.unique())))
            representations.append(dict(row, inventory="downstream", records=len(selected),
                unique_centres=len(selected[["center_lon", "center_lat"]].drop_duplicates()),
                total_records=len(downstream), fraction_all_records=len(selected)/len(downstream), present=True))
            for inventory, saved in inventories.items():
                match = saved[cat].loc[saved[cat][key].eq(category_id)]
                _require(len(match) <= 1, "Duplicate ecological category")
                if len(match):
                    _require(match[name].iloc[0] == row["category_name"] and
                             match[color].iloc[0] == row["category_color"], "RESOLVE category attributes disagree")
                count = int(match.records.iloc[0]) if len(match) else 0
                representations.append(dict(row, inventory=inventory, records=count,
                    unique_centres=int(match.unique_centres.iloc[0]) if len(match) else 0,
                    total_records=saved["summary"]["records"],
                    fraction_all_records=count/saved["summary"]["records"], present=count > 0))
        # Separate classified categories outside the downstream set from unresolved assignments.
        for inventory in ("downstream", *inventories):
            current = [r for r in representations if r["category"] == cat and r["inventory"] == inventory]
            relevant = sum(r["records"] for r in current)
            total = len(downstream) if inventory == "downstream" else inventories[inventory]["summary"]["records"]
            assigned = int(valid.sum()) if inventory == "downstream" else int(inventories[inventory][cat].records.sum())
            for label, count in (("Other assigned categories", assigned-relevant), ("Unresolved assignments", total-assigned)):
                representations.append(dict(category=cat, category_id=np.nan, category_name=label,
                    category_color=None, events="", inventory=inventory, records=count, unique_centres=np.nan,
                    total_records=total, fraction_all_records=count/total, present=count > 0))
    return dict(chip_level_characterisation=chips, event_exposure_summary=pd.DataFrame(rows),
                event_proximity_summary=pd.DataFrame(proximity),
                event_biome_composition=compositions["biome"], event_ecoregion_composition=compositions["ecoregion"],
                ecological_inventory_representation=pd.DataFrame(representations))


def save_analysis(tables, provenance, output):
    """Publish to a fresh directory so earlier analysis and source results remain intact."""
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    for name in TABLES:
        tables[name].to_csv(output / f"{name}.csv", index=False)
    provenance = dict(provenance, tables={name: _hash(output / f"{name}.csv") for name in TABLES},
        definitions={
            "coverage": "Arithmetic chip mean of saved union area fractions; not event territorial coverage.",
            "overlap": "Positive area, not distance == 0.",
            "distance": "Saved nearest footprint km; original exposure method retained.",
            "proximity": "Saved Haversine centre-to-centre counts; exact-coordinate centres; per-chip mean/median.",
            "dispersion": "Sample standard deviation ddof=1; linear-interpolated quartiles; singleton std missing.",
            "ecology": "Centre assignment; existing non-unclassified nonnull category filtering, including common ambiguous biomes.",
            "denominators": "All chips in event or downstream dataset; full pretraining record totals.",
            "missing": "Blank CSV fields are unavailable, never zero-filled measurements; residual unique centres unavailable."
        })
    (output / "provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")


def load_analysis(output):
    """Load completed analytical tables for plotting without original inputs."""
    output = Path(output)
    provenance = _json(output / "provenance.json")
    for name in TABLES:
        _require(_hash(output / f"{name}.csv") == provenance["tables"][name], f"Changed analysis table: {name}")
    return {name: pd.read_csv(output / f"{name}.csv") for name in TABLES}
