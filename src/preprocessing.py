import argparse
from pathlib import Path
import logging
from datetime import datetime
import pandas as pd

# Paths
project_root = Path(__file__).resolve().parent.parent
processed_dir = project_root / "data" / "processed"
registry_path = project_root / "data" / "registry" / "processed_registry.csv"
log_dir = project_root / "logs" / "preprocessing"

processed_dir.mkdir(parents=True, exist_ok=True)
registry_path.parent.mkdir(parents=True, exist_ok=True)
log_dir.mkdir(parents=True, exist_ok=True)

# Logging Setup
def setup_logging(location, week_label):
    """Configures logging to write to both console and a file named after the location and week being processed"""
    log_file = log_dir / f"{location}_{week_label}.log"

    logger = logging.getLogger(__name__)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger

log = None  # Set inside processed_week() once location/week are known

# Registry helper - prevents double-processing the same week
def get_processed_keys():
    """Return set of 'location_weeks' keys that have already been processed"""
    if not registry_path.exists():
        return set()
    registry = pd.read_csv(registry_path)
    return set(registry['location'] + "_" + registry['week'])

def update_registry(location, week_label, active_rows, passive_rows):
    """Appends a new entry to the processed registry after successful processing"""
    entry = pd.DataFrame([{"location": location, "week": week_label,
        "processed_on": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), "active_rows_added": active_rows,
        "passive_rows_added": passive_rows
    }])
    file_exists = registry_path.exists()
    entry.to_csv(registry_path, mode="a", header=not file_exists, index=False)

# Active Probe Cleaning
def clean_active_data(active_df, location):
    """Cleans raw active probe data. Shared rules apply to both locations; the only location-specific rule is TCP handling:

        - Singapore: TCP is dropped entirely (0% success: network-level block on raw SYN packets, confirmed via EDA)
        - India: TCP is retained through this stage since it has non-zero success, but is known to carry a measurement
          artifact (local RST responses being captured instead of genuine SYN-ACKs). This script does NOT exclude it;
          that decision belongs to feature_engineering.py, which should drop or flag it before modeling. A warning is
          logged here as a reminder.)"""

    raw_row_count = len(active_df)
    log.info(f"Raw active rows: {raw_row_count}")

    df = active_df.copy()

    # location specific TCP handling
    if location == 'sg':
        dropped_tcp = (df['protocol'] == 'tcp').sum()
        df = df[df['protocol'] != 'tcp']
        log.info(f"Dropped {dropped_tcp} tcp rows (Singapore network blocks raw SYN packest, 0% success)")

    elif location == "in":
        tcp_count = (df['protocol'] == 'tcp').sum()
        if tcp_count > 0:
            log.warning(
                f"{tcp_count} TCP rows retained for India — known local-RST measurement "
                f"artifact present. Exclude/flag in feature_engineering.py "
                f"before using for D_proc analysis or modeling."
            )

    # dropped failed probes (success=False, null rtt_ms)
    dropped_failed = (df['success'] == False).sum()
    df = df[df['success'] == True]
    log.info(f"Dropped {dropped_failed} failed probes (timeout, null RTT")

    # dropped zero RTT rows (measurement artifacts, nor real 0ms RTT)
    dropped_zero = (df['rtt_ms'] == 0).sum()
    df = df[df['rtt_ms'] > 0]
    log.info(f"Dropped {dropped_zero} zero RTT measurement artifacts")

    # dropped extreme outliers (RTT > 500ms)
    dropped_outliers = (df['rtt_ms'] > 500).sum()
    df = df[df['rtt_ms'] <= 500]
    log.info(f"Dropped {dropped_outliers} outliers (RTT > 500ms)")

    retained_pct = (len(df) / raw_row_count) * 100 if raw_row_count else 0
    log.info(f"Active data retention: {len(df) / raw_row_count} ({retained_pct:.1f}%)")

    # per-protocol breakdown for visibility
    log.info(f"Protocol breakdown after cleaning: {df['protocol'].value_counts().to_dict()}")

    return df, raw_row_count

# Passive probe cleaning
def clean_passive_data(passive_df, valid_experiment_ids):
    """Cleans raw passive capture data. Identical logic for both locations:
        - Fills expected nulls for non-TCP packets (tcp_flag, window_size)
        - Drop non_IP 'OTHER' protocol noice
        - Drops orphaned rows whose experiment_id has no surviving active probe"""

    raw_row_count = len(passive_df)
    log.info(f"Raw passive rows: {raw_row_count}")

    df = passive_df.copy()

    # Fill expected nulls for non-TCP packets
    df['tcp_flag'] = df['tcp_flag'].fillna('NONE')
    df['window_size'] = df['window_size'].fillna(0)

    # drop non-IP noice
    dropped_other = (df['protocol'] == 'OTHER').sum()
    df = df[df['protocol'] != 'OTHER']
    log.info(f"Dropped {dropped_other} non-IP 'OTHER' protocol rows")

    # drop orphaned passive rows
    dropped_orphaned = (~df['experiment_id'].isin(valid_experiment_ids)).sum()
    df = df[df['experiment_id'].isin(valid_experiment_ids)]
    log.info(f"Dropped {dropped_orphaned} orphaned passive rows")

    retained_pct = (len(df) / raw_row_count) * 100 if raw_row_count else 0
    log.info(f"Passive data retention: {len(df) / raw_row_count} ({retained_pct:.1f}%)")

    return df, raw_row_count

# Schema Validation - catches silent drifts before it corrupts the master file
def validate_active_schema(df):
    expected_columns = {"timestamp", "experiment_id", "source_location", "protocol", "dst_ip", "packet_size", "probe_index",
                        "success", "rtt_ms", "send_timestamp", "recv_timestamp", "location", "week"}
    missing = expected_columns - set(df.columns)
    assert not missing, f"Schema mismatch — missing columns: {missing}"

    assert df["rtt_ms"].min() > 0, "Zero/negative RTT leaked through cleaning"
    assert df["rtt_ms"].max() <= 500, "Outlier leaked through cleaning"
    assert df["success"].all(), "Failed probes leaked through cleaning"
    log.info("Active schema validation passed")

def validate_passive_schema(df):
    expected_columns = {"timestamp", "src_ip", "dst_ip", "protocol", "packet_length", "ttl", "tcp_flag", "window_size",
                        "source_location", "experiment_id", "experiment_timestamp"}
    missing = expected_columns - set(df.columns)
    assert not missing, f"Schema mismatch — missing columns: {missing}"

    assert not (df["protocol"] == "OTHER").any(), "OTHER protocol rows leaked through cleaning"
    assert df["tcp_flag"].isnull().sum() == 0, "Unfilled tcp_flag nulls remain"
    assert df["window_size"].isnull().sum() == 0, "Unfilled window_size nulls remain"
    log.info("Passive schema validation passed")

# Main Preprocessing pipeline
def process_week(active_path, passive_path, location, week_label):
    """Runs the full preprocessing pipeline foe single week of raw data and appends the clean active and passive data
    to their processed master files"""

    global log
    log = setup_logging(location, week_label)

    registry_key = f"{location}_{week_label}"
    if registry_key in get_processed_keys():
        raise ValueError(
            f"{registry_key} has already been processed"
            f"Check {registry_path} if you intend to reprocess"
        )
    log.info(f"PREPROCESSING -  Location: {location.upper()} | Week: {week_label}")

    # load raw data
    active_df = pd.read_csv(active_path)
    passive_df = pd.read_csv(passive_path)

    # clean active data
    active_clean, active_raw_count = clean_active_data(active_df, location)

    # clean passive data - only keep rows whose experiment survived active cleaning
    valid_experiment_ids = set(active_clean['experiment_id'])
    passive_clean, passive_raw_count = clean_passive_data(passive_df, valid_experiment_ids)

    # attach location and week metadata
    active_clean['location'] = location
    active_clean['week'] = week_label

    # validate schema before writing
    validate_active_schema(active_clean)
    validate_passive_schema(passive_clean)

    # write processed master file
    active_master_path = processed_dir / "active_processed_master.csv"
    passive_master_path = processed_dir / "passive_processed_master.csv"

    active_file_exists = active_master_path.exists()
    passive_file_exists = passive_master_path.exists()

    active_clean.to_csv(active_master_path, mode='a', header=not active_file_exists, index=False)
    passive_clean.to_csv(passive_master_path, mode='a', header=not passive_file_exists, index=False)

    # update registry
    update_registry(location, week_label, len(active_clean), len(passive_clean))

    # final summary
    log.info(f"PREPROCESSING SUMMARY — {location.upper()} / {week_label}")
    log.info(f"Active:  {active_raw_count} raw -> {len(active_clean)} clean "
             f"({len(active_clean) / active_raw_count * 100:.1f}% retained)")
    log.info(f"Passive: {passive_raw_count} raw -> {len(passive_clean)} clean "
             f"({len(passive_clean) / passive_raw_count * 100:.1f}% retained)")
    log.info(f"Appended to: {active_master_path}")
    log.info(f"Appended to: {passive_master_path}")
    log.info(f"Log saved to: {log_dir / f'{location}_{week_label}.log'}")

# CLI entry points
def main():
    parser = argparse.ArgumentParser(description="Preprocess a single week of raw latency data")
    parser.add_argument("--active", required=True, help="Path to raw active probe CSV")
    parser.add_argument("--passive", required=True, help="Path to raw passive probe CSV")
    parser.add_argument("--location", required=True, choices=['in', 'sg'], help="Collection Location")
    parser.add_argument("--week", required=True, help="Week label (eg.- 2026_07_w2")

    args = parser.parse_args()

    process_week(active_path=args.active, passive_path=args.passive,
                 location=args.location, week_label=args.week)

if __name__ == '__main__':
    main()