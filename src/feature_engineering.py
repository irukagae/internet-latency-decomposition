import logging
import re
from pathlib import Path

import pandas as pd
import numpy as np

"""
TCP is excluded on purpose. Singapore blocks raw TCP SYN (0% success). India's TCP "RTTs" are not
real round trips (~15 ms even to targets 125-235 ms away); the likely cause, not confirmed with a
packet trace, is a local RST from Windows' own TCP stack being captured instead of the target's reply.
To re-enable: fix collection, recollect, then add "tcp" here.
"""
KNOWN_PROTOCOLS = ['icmp', 'udp']

KNOWN_TARGETS = ["8.8.8.8", "1.1.1.1", "94.140.14.14", "185.222.222.222", "45.11.45.11"]
KNOWN_LOCATION = ['sg', 'in']
LOCATION_TZ = {'sg' : 'Asia/Singapore', 'in' : 'Asia/Kolkata'}

PROBES_PER_EXPERIMENT = 30
MIN_VALID_PROBES = 10  # configurable quality threshold; not a statistically fitted parameter

FINE_CLOCK_WEEKS = set()  # add "loc:week" labels collected after switching base.py to perf_counter

ONE_HOT_GROUPS = (("location", "loc", KNOWN_LOCATION), ("protocol", "proto", KNOWN_PROTOCOLS), ("dst_ip", "dst", KNOWN_TARGETS))
ONE_HOT_COLUMNS = [f"{prefix}_{value.replace('.', '_')}" for _, prefix, values in ONE_HOT_GROUPS for value in values]
BG_COLUMNS = ["bg_packet_count", "bg_byte_volume", "bg_mean_packet_len", "bg_tcp_ratio", "bg_udp_ratio", "bg_icmp_ratio",
              "bg_unique_hosts", "bg_has_tcp", "bg_tcp_win_mean", "bg_tcp_win_min", "bg_syn_ratio", "bg_rst_ratio"]
TIME_COLUMNS = ["hour_sin", "hour_cos", "dow_sin", "dow_cos", "is_weekend"]

FEATURE_COLUMNS = (["packet_size"] + ONE_HOT_COLUMNS + TIME_COLUMNS + BG_COLUMNS + ["passive_capture_present", "bg_present"])

# FIX: rtt_ms is the input column; aggregation creates rtt_mean as the output target.
TARGET_COLUMNS = ["rtt_mean"]

AUX_COLUMNS = ["rtt_std", "zero_frac", "n_valid_probes", "valid_probe_fraction"]
ID_COLUMNS = ["experiment_id", "location", "week", "clock_regime", "timestamp", "local_hour","day_of_week", "protocol", "dst_ip"]
OUTPUT_COLUMNS = (ID_COLUMNS + FEATURE_COLUMNS + TARGET_COLUMNS + AUX_COLUMNS)

# PATHS
project_root = Path(__file__).resolve().parent.parent
processed_dir = project_root / "data" / "processed"
output_dir = project_root / "data" / "features"
log_dir = project_root / "logs" / "feature_engineering"

log = logging.getLogger("feature_engineering")

# validation helper
def require(condition, message):
    """Raise an explicit error"""
    if not condition:
        raise ValueError(message)

def require_columns(df, columns, label):
    missing = set(columns) - set(df.columns)
    require(not missing, f"{label}: missing columns: {sorted(missing, key=str)}")

# locate processed file (one active + one passive file per location/week)
def find_file_pairs():
    """Returns [(location, week, active_path, passive_path), ...] for every processed week"""
    pairs = []
    for loc in KNOWN_LOCATION:
        location_dir = processed_dir / loc

        for active in sorted(location_dir.glob("active_processed_*.csv")):
            week = active.stem.removeprefix("active_processed_")
            require(bool(re.fullmatch(r"\d{4}_(0[1-9]|1[0-2])_w[1-6]", week)), f"Unexpected week label: {week}")

            passive = active.with_name(f"passive_processed_{week}.csv")
            if not passive.is_file():
                raise FileNotFoundError(f"Missing paired passive file: {passive}")
            pairs.append((loc, week, active, passive))

    if not pairs:
        raise FileNotFoundError(f"No processed files in {processed_dir}/<location>/")

    return pairs

# Active probes -> one row per experiment
def build_experiment_table(active, location, week, min_valid_probes):
    """Collapses the 30 probes of experiment into one row."""

    required = ["experiment_id","timestamp" ,"source_location", "location", "week", "protocol", "dst_ip", "packet_size",
                "probe_index", "success", "rtt_ms"]
    require_columns(active, required, "Active Data")

    require(not active[required].isna().any().any(),"Active data contains missing values",)
    require(active["location"].eq(location).all(),"Location differs from input folder",)
    require(active["source_location"].eq(location).all(),"Source location mismatch",)
    require(active["week"].eq(week).all(),"Week differs from input filename",)
    require(set(active["protocol"]) <= {"icmp", "udp", "tcp"},"Unknown active protocol",)
    require(not active.duplicated(["experiment_id", "probe_index"]).any(),"Duplicate (experiment_id, probe_index) rows",)
    require(active["success"].astype(str).str.lower().eq("true").all(),"Failed probes remain in processed active data",)

    for col in ("rtt_ms", "packet_size", "probe_index"):
        active[col] = pd.to_numeric(active[col], errors="raise")

    require(np.isfinite(active[["rtt_ms", "packet_size", "probe_index"]].to_numpy(dtype=float)).all(),
            "Non-finite active measurements")
    require(active["rtt_ms"].between(0, 500).all(), "RTT outside preprocessing bounds")
    require((active["packet_size"].gt(0) & active["packet_size"].mod(1).eq(0)).all(), "Invalid packet size")
    require((active["probe_index"].between(0, PROBES_PER_EXPERIMENT - 1)
             & active["probe_index"].mod(1).eq(0)).all(), "Invalid probe index")

    require(not active.duplicated(["experiment_id", "probe_index"]).any(), "Duplicate (experiment_id, probe_index) rows")

    df = active[active["protocol"].isin(KNOWN_PROTOCOLS)].copy()
    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="raise")

    require(df["timestamp"].notna().all(), "Missing or invalid experiment timestamp")

    metadata = ["location", "week", "timestamp", "protocol", "dst_ip", "packet_size"]
    grouped = df.groupby("experiment_id", sort=False)

    require(not grouped[metadata].nunique().gt(1).any().any(), "Conflicting metadata within an experiment")

    # Keep zero RTTs in the mean and record their fraction separately.
    exp = grouped.agg(**{column: (column, "first") for column in metadata}, rtt_mean=("rtt_ms", "mean"),
                      rtt_std=("rtt_ms", "std"), zero_frac=("rtt_ms", lambda s: s.eq(0).mean()),
                      n_valid_probes=("rtt_ms", "size"),).reset_index()

    keep = exp["n_valid_probes"].ge(min_valid_probes)

    log.info("%s/%s: retained %d/%d ICMP/UDP experiments", location, week, keep.sum(), len(exp),)

    exp = exp.loc[keep].copy()

    require(not exp.empty, f"No eligible experiments for {location}/{week}",)

    # Includes timeout failures AND preprocessing exclusions.
    # Therefore, this is not a pure packet-loss measurement.
    exp["valid_probe_fraction"] = (exp["n_valid_probes"] / PROBES_PER_EXPERIMENT)

    return exp

# Passive packets -> background features per experiment
def build_passive_features(passive, exp):
    required = [    "experiment_id", "src_ip", "dst_ip", "protocol", "packet_length", "tcp_flag", "window_size"]

    require_columns(passive, required, "Passive data")

    p = passive[passive["experiment_id"].isin(exp["experiment_id"])].copy()
    basic = ["experiment_id", "src_ip", "dst_ip", "protocol", "packet_length"]

    require(not p[basic].isna().any().any(),"Passive packet metadata contains nulls")
    require(set(p["protocol"]) <= {"TCP", "UDP", "ICMP"},"Unknown passive protocol")

    p["packet_length"] = pd.to_numeric(p["packet_length"], errors="raise")

    require((np.isfinite(p["packet_length"]) & p["packet_length"].gt(0)
             & p["packet_length"].mod(1).eq(0)).all(), "Invalid passive packet lengths")

    # Record availability before removing probe-related packets.
    captured_ids = set(p["experiment_id"])

    target_of = exp.set_index("experiment_id")["dst_ip"]
    target = p["experiment_id"].map(target_of)

    own = p["src_ip"].eq(target) | p["dst_ip"].eq(target)

    # Conservative approximation inherited from your current approach:
    # this also removes unrelated traffic involving the experiment target.
    # Exact matching requires packet ports/IDs absent from these CSVs.
    p = p.loc[~own].copy()

    log.info("Removed %d packets involving experiment targets",own.sum())

    for protocol in ("tcp", "udp", "icmp"):
        p[f"is_{protocol}"] = p["protocol"].eq(protocol.upper())

    g = p.groupby("experiment_id", sort=False)
    feats = g.agg(bg_packet_count=("packet_length", "size"), bg_byte_volume=("packet_length", "sum"),
                  bg_mean_packet_len=("packet_length", "mean"), bg_tcp_ratio=("is_tcp", "mean"), bg_udp_ratio=("is_udp", "mean"),
                  bg_icmp_ratio=("is_icmp", "mean"))

    ips = pd.concat([p[["experiment_id", column]].rename(columns={column: "ip"}) for column in ("src_ip", "dst_ip")], ignore_index=True)

    # Includes local addresses; this is a count of distinct endpoints,
    # not exclusively remote hosts.
    feats["bg_unique_hosts"] = (ips.groupby("experiment_id")["ip"].nunique())

    # Compute TCP window statistics only from TCP packets.
    tcp = p.loc[p["is_tcp"]].copy()
    tcp["window_size"] = pd.to_numeric(tcp["window_size"], errors="raise")

    require(tcp["window_size"].between(0, 65535).all(),"Invalid TCP window size",)
    require(tcp["tcp_flag"].notna().all(),"Missing TCP flags")

    flags = tcp["tcp_flag"].astype(str)

    # SYN set, ACK unset: initial SYN rather than SYN-ACK.
    tcp["is_syn"] = (flags.str.contains("S", regex=False) & ~flags.str.contains("A", regex=False))
    tcp["is_rst"] = flags.str.contains("R", regex=False)
    tcp_feats = tcp.groupby("experiment_id").agg(bg_tcp_win_mean=("window_size", "mean"), bg_tcp_win_min=("window_size", "min"),
                                                 bg_syn_ratio=("is_syn", "mean"), bg_rst_ratio=("is_rst", "mean"))

    # These are raw advertised windows. Window scaling is unavailable.
    feats = feats.join(tcp_feats)
    feats["bg_has_tcp"] = feats.index.isin(tcp_feats.index).astype(int)

    out = exp.merge(feats.reset_index(), on="experiment_id", how="left", validate="one_to_one",)

    out["passive_capture_present"] = (out["experiment_id"].isin(captured_ids).astype(int))
    out["bg_present"] = (out["experiment_id"].isin(feats.index).astype(int))

    # Availability flags distinguish:
    # - no passive rows,
    # - capture present but no observed background,
    # - background present but no TCP.
    out[BG_COLUMNS] = out[BG_COLUMNS].fillna(0)

    log.info("Experiments without passive rows: %d",out["passive_capture_present"].eq(0).sum(),)

    # Do not infer packets/sec using first-to-last packet timestamps:
    # that span excludes silent time. Actual capture boundaries are
    # not stored in the existing CSVs.
    return out

# time, clock, regime, and fixed categorical encoding
def add_context_features(df, location, week):
    local = df["timestamp"].dt.tz_convert(LOCATION_TZ[location])
    hour = (local.dt.hour + local.dt.minute / 60 + local.dt.second / 3600)
    dow = local.dt.dayofweek

    df["local_hour"] = local.dt.hour
    df["day_of_week"] = dow
    df["hour_sin"] = np.sin(2 * np.pi * hour/24)
    df["hour_cos"] = np.cos(2 * np.pi * hour/24)
    df["dow_sin"] = np.sin(2 * np.pi * dow/7)
    df["dow_cos"] = np.cos(2 * np.pi * dow/7)
    df["is_weekend"] = dow.ge(5).astype(int)
    df["clock_regime"] = ("fine" if f"{location}:{week}" in FINE_CLOCK_WEEKS else "coarse")

    # fixed configuration guarantees identical columns in every week, even when particular category is absent from one dataset
    for col, prefix, value in ONE_HOT_GROUPS:
        unknown = set(df[col]) - set(value)
        require(not unknown,f"Unknown {col}: {unknown}; " "update KNOWN_* configuration")

        for val in value:
            name = f"{prefix}_{val.replace('.', '_')}"
            df[name] = df[col].eq(val).astype(int)

    return df

# Final validation
def validate(df, min_valid_probes):
    require_columns(df, OUTPUT_COLUMNS, "Feature matrix")
    require(not df.empty and df["experiment_id"].is_unique,"Empty matrix or duplicate experiments")
    require(not df[OUTPUT_COLUMNS].isna().any().any(),"Nulls in feature matrix")

    numeric = FEATURE_COLUMNS + TARGET_COLUMNS + AUX_COLUMNS

    require(np.isfinite(df[numeric].to_numpy(dtype=float)).all(),"Non-finite numeric values")
    require(df["n_valid_probes"].between(min_valid_probes, PROBES_PER_EXPERIMENT,).all(),"Invalid number of valid probes")
    require(df["rtt_mean"].between(0, 500).all(),"Invalid RTT target")

    for _, prefix, values in ONE_HOT_GROUPS:
        columns = [f"{prefix}_{value.replace('.', '_')}" for value in values]
        require(df[columns].sum(axis=1).eq(1).all(),f"Invalid {prefix} encoding")

    require(df["timestamp"].is_monotonic_increasing,"Rows are not chronological")

# Weekly pipeline
def build_features_files(min_valid_probes=MIN_VALID_PROBES):
    require(isinstance(min_valid_probes, (int, np.integer)) and 2 <= min_valid_probes <= PROBES_PER_EXPERIMENT,
            f"min valid probes must be an integer between 2 and {PROBES_PER_EXPERIMENT}")

    seen_ids = set()
    outputs = []
    pairs = find_file_pairs()

    for loc, week, active_path, passive_path in pairs:
        log.info("Processing %s/%s", loc, week)

        active = pd.read_csv(active_path, dtype={"experiment_id" : "string"})
        require_columns(active, ["experiment_id"], "Active Data")

        # prevent the same experiment appearing in different weeks
        ids = set(active["experiment_id"])
        require(not (seen_ids & ids), "Experiment IDs overlap across weekly input files.")
        seen_ids.update(ids)

        exp = build_experiment_table(active, loc, week, min_valid_probes)

        passive = pd.read_csv(passive_path, dtype={"experiment_id" : "string"})

        df = build_passive_features(passive, exp)
        df = add_context_features(df, loc, week)
        df = df.sort_values(["timestamp", "experiment_id"], kind="stable").reset_index(drop=True)

        validate(df, min_valid_probes)

        df = df[OUTPUT_COLUMNS].copy()
        # explicit UTC representation for downstream chronological splits
        df["timestamp"] = df["timestamp"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")

        destination = output_dir / loc / f"features_{week}.csv"
        destination.parent.mkdir(parents=True, exist_ok=True)

        # replace an existing weekly output only after writing finishes.
        temporary = destination.with_suffix(".csv.tmp")
        df.to_csv(temporary, index=False)
        temporary.replace(destination)

        outputs.append(destination)
        log.info("Saved %d rows x %d columns to %s", len(df), len(df.columns), destination)

    return outputs

if __name__ == '__main__':
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(), logging.FileHandler(log_dir / "feature_engineering.log", encoding="utf-8")])

    outputs = build_features_files(MIN_VALID_PROBES)

    log.info("Finished: %d weekly files, %d model features", len(outputs), len(FEATURE_COLUMNS))