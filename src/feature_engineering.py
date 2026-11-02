import argparse
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd
import numpy as np

KNOWN_PROTOCOLS = ['icmp', 'udp']  # tcp excluded: Singapore blocks it, India's TCP RTT is a local-RST artifact
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

