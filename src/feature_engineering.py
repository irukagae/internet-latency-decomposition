import argparse
import logging
from datetime import datetime
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

MIN_VALID_PROBES = 0  # experiments with fewer successful probes give a too-noisy mean
BASELINE_QUANTILE = 0.05  # low quantile of experiment-mean RTT = approximate physical floor
FINE_CLOCK_WEEKS = set()  # add "loc:week" labels collected after switching base.py to perf_counter

BG_COLUMNS = ["bg_packet_count", "bg_byte_volume", "bg_mean_packet_len", "bg_tcp_ratio", "bg_udp_ratio", "bg_icmp_ratio",
              "bg_unique_hosts", "bg_has_tcp", "bg_tcp_win_mean", "bg_tcp_win_min", "bg_syn_ratio", "bg_rst_ratio"]
ONE_HOT_COLUMNS = ([f"loc_{l}" for l in KNOWN_LOCATION] + [f"proto_{p}" for p in KNOWN_PROTOCOLS]
                   + [f"dst_{ip.replace('.', '_')}" for ip in KNOWN_TARGETS])
TIME_COLUMNS = ["hour_sin", "hour_cos", "day_of_week", "is_weekend"]

FEATURE_COLUMNS = ["packet_size"] + ONE_HOT_COLUMNS + TIME_COLUMNS + BG_COLUMNS
TARGET_COLUMNS = ["rtt_mean", "excess_rtt_mean"]
AUX_COLUMNS = ["rtt_std", "zero_frac", "n_valid_probes", "baseline_rtt"]
ID_COLUMNS = ["experiment_id", "location", "week", "clock_regime", "timestamp", "local_hour", "protocol", "dts_ip"]

# PATHS
project_root = Path(__file__).resolve().parent.parent
processed_dir = project_root / "data" / "processed"
baseline_dir = processed_dir / "baseline_rtt.csv"
output_path = processed_dir / "feature_matrix.csv"
log_dir = processed_dir / "logs" / "feature_engineering"

log = logging.getLogger("feature_engineering")

def setup_logging():
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / f"feature_engineering_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

    log.setLevel(logging.INFO)
    log.handlers.clear()
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    for handler in (logging.FileHandler(log_file), logging.StreamHandler()):
        handler.setFormatter(formatter)
        log.addHandler(handler)
    log.info(f"Log file: {log_file}")

# locate processed file (one active + one passive file per location/week)
def find_file_pairs():
    """Returns [(location, week, active_path, passive_path), ...] for every processed week"""
    pairs = []
    for active_path in sorted(processed_dir.glob("*active_processed_*.csv")):
        location = active_path.parent.name
        week = active_path.stem.replace("active_processed_", "")
        passive_path = active_path.parent / f"passive_processed_{week}.csv"
        if not passive_path.exists():
            raise FileNotFoundError(f"Missing passive file for {location}/{week}: {passive_path}")

        pairs.append((location, week, active_path, passive_path))

    if not pairs:
        raise FileNotFoundError(f"No processed files found under {processed_dir}")

    return pairs

# experiment-level rows from active data
def build_experiment_table(active_df):
    """Collapses the 30 probes of experiment into one row.

    The clock ticks every 15.6 ms, so a single probe is coarse, but the mean over many probes is a good estimate of the RTT.
    Zero-RTT probes are kept for exactly that reason."""

    df = active_df[active_df['protocol'].isin(KNOWN_PROTOCOLS)].copy()  # drops India's TCP rows

    grouped = df.groupby("experiment_id")
    exp = grouped.agg(location=("location", "first"), week=("week", "first"), timestamp=("timestamp", "first"),
                      protocol=("protocol", "first"), dst_ip=("dst_ip", "first"), packet_size=("packet_size", "first"),
                      rtt_mean=("rtt_ms", "mean"), rtt_std=("rtt_ms", "std"), zero_frac=("rtt_ms", lambda s: (s==0).mean()),
                      n_valid_probes=("rtt_ms", "size")).resent_index()

    before = len(exp)
    exp = exp[exp["n_valid_probes"] >= MIN_VALID_PROBES].copy()
    log.info(f"  experiments: {before} -> {len(exp)} after requiring >= {MIN_VALID_PROBES} valid probes")
    return exp

# passive (background traffic) features per experiment
def build_passive_features(passive_df, exp):
    """Aggregates background traffic per experiment.

    The sniffer sits at the same interface as the probes, so it records probes' own packets and their replies.
    Those are removed (anything to/from the experiment's target IP) so that the features describe the real background traffic only."""

    target_of = exp.set_index("experiment_id")["dst_ip"]
    p = passive_df[passive_df["experiment_id"].isin(target_of.index)].copy()
    captured_ids = set(p["experiment_id"])  # experiments the sniffer saw anything for

    target = p["experiment_id"].map(target_of)
    own = (p["src_ip"] == target) | (p["dst_ip"] == target)
    log.info(f"passive: {len(p)} packets, {own.mean() * 100:.1f}% were probes' own traffic (removed)")
    p = p[~own].copy()

    p["is_tcp"] = p["protocol"] == "TCP"
    p["is_udp"] = p["protocol"] == "UDP"
    p["is_icmp"] = p["protocol"] == "ICMP"
    g = p.groupby("experiment_id")

    feats = pd.DataFrame({"bg_packet_count" : g.size(), "bg_byte_volume" : g["packet_length"].sum(),
                          "bg_mean_packet_len" : g["packet_length"].mean(), "bg_tcp_ratio" : g["is_tcp"].mean(),
                          "bg_udp_ratio" : g["is_udp"].mean(), "bg_icmp_ratio" : g["is_icmp"].mean()})

    # distinct IPs seen on either side of a packet (includes this machine's own IP as a constant +1)
    ips = pd.concat([p[["experiment_id", "src_ip"]].rename(columns={"src_ip" : "ip"}),
                    p[["experiment_id", "dst_ip"]].rename(columns={"dst_ip" : "ip"})])
    feats["bg_unique_hosts"] = ips.groupby("experiment_id")["ip"].nunique()

    # TCp-only features: preprocessing filled window_size with 0 for non-TCP packets, so windows
    # statistics must be computed on TCP rows alone
    tcp = p[p["is_tcp"]].copy()
    tcp["is_syn"] = tcp["tcp_flag"].astype(str) == "S"
    tcp["is_rst"] = tcp["tcp_flag"].astype(str).str.contains("R")
    gt = tcp.groupby("experiment_id")
    feats["bg_tcp_win_mean"] = gt["window_size"].mean()
    feats["bg_tcp_win_min"] = gt["window_size"].min()
    feats["bg_syn_ratio"] = gt["is_syn"].mean()
    feats["bg_rst_ratio"] = gt["is_rst"].mean()
    feats["bg_has_tcp"] = feats.index.isin(tcp["experiment_id"].unique()).astype(int)

    feats = feats.reset_index()
    out = exp.merge(feats, on="experiment_id", how="left")

    # an experiment the sniffer captured but with only its own packets = a genuinely quite network (zeros);
    # an experiment with no captured packest at all = capture failure, so it is dropped
    no_capture = ~out["experiment_id"].isin(captured_ids)
    if no_capture.any():
        log.warning(f"dropped {no_capture.sum()} experiments with no passive capture at all")
    out = out[~no_capture].copy()
    out[BG_COLUMNS] = out[BG_COLUMNS].fillna(0)

    return out

# time, clock, regime, and one-hot features
def add_time_features(df):
    """Timestamps are UTC, so they are converted to each location's local time first"""
    utc = pd.to_datetime(df["timestamp"], utc=True)
    hour = pd.Series(np.nan, index=df.index)
    dow = pd.Series(np.nan, index=df.index)

    for loc in df["location"].unique():
        mask = df["location"] == loc
        local = utc[mask].dt.tz_convert(LOCATION_TZ[loc])
        hour[mask] = local.dt.hour + local.dt.minute / 60
        dow[mask] = local.dt.dayofweek

    df["local_hour"] = np.floor(hour).astype(int)
    df["hour_sin"] = np.sin(2 * np.pi * hour/24)
    df["hour_cos"] = np.cos(2 * np.pi * hour/24)
    df["day_of_week"] = dow.astype(int)
    df["id_weekend"] = (dow >= 5).astype(int)

    return df

def add_clock_regime(df):
    key = df["location"] + ":" + df["week"]
    df["clock_regime"] = np.where(key.isin(FINE_CLOCK_WEEKS), "fine", "coarse")

    return df

def add_one_hot(df):
    for name, value, column in (("loc", KNOWN_LOCATION, "location"),
                                ("proto", KNOWN_PROTOCOLS, "protocol"),
                                ("dst", KNOWN_TARGETS, "dst_ip")):
        unknown = set(df[column].unique()) - set(value)
        if unknown:
            raise ValueError(f"unknown {column} values {unknown} - add them to KNOWN_* lists at the top")
        for v in value:
            df[f"{name}_{str(v).replace('.', '_')}"] = (df[column] == v).astype(int)

    return df

# baseline (physical floor) and provisional queuing target
def parse_reference_week(specs, df):
    """'sg:2026_07_w1 in:2026_08_w1' -> set of (location, week). Default: earliest week of each location"""

    if specs:
        return {tuple(s.split(":", 1)) for s in specs}
    return {(loc, sorted(grp["week"].unique())[0]) for loc, grp in df.groupby("location")}

def build_baseline(df, reference_week):
    pass