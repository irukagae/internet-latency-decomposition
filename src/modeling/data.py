#load and validate weekly features

from pathlib import Path
import numpy as np
import pandas as pd

from ..feature_engineering import (AUX_COLUMNS, FEATURE_COLUMNS, TARGET_COLUMNS, require, require_columns)

project_root = Path(__file__).resolve().parents[2]
features_dir = project_root / "data" / "features"

METADATA = ["experiment_id", "timestamp", "location", "week", "clock_regime", "protocol", "dst_ip"]

def load_week(location, week,  target):
    path = features_dir / location / f"features_{week}.csv"
    df = pd.read_csv(path, dtype={"experiment_id" : "string"})

    require(TARGET_COLUMNS == [target], "Configured data differs from feature engineering")
    forbidden = set(AUX_COLUMNS + TARGET_COLUMNS + ["rtt_ms", "expected_rtt_mean"])
    require(not forbidden.intersection(FEATURE_COLUMNS), "RTT-derived column in predictors")

    columns = METADATA + FEATURE_COLUMNS + [target]
    require_columns(df, columns, str(path))
    df = df[columns].copy()

    require(not df.empty, f"Empty feature file: {path}")
    require(not df.isna().any().any(), f"Null values: {path}")
    require(df["experiment_id"].is_unique, f"Duplicate experiment IDs: {path}")
    require(df["location"].eq(location).all() and df["week"].eq(week).all(), f"Location/week mismatch: {path}")

    df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True, errors="raise")
    require(df["timestamp"].notna().all(), f"Missing timestamp: {path}")

    numeric = FEATURE_COLUMNS + [target]
    df[numeric] = df[numeric].apply(pd.to_numeric, errors="raise")
    require(np.isfinite(df[numeric].to_numpy(dtype=float)).all(), f"Non-finite values: {path}")
    require(df[target].between(0, 500).all(), f"RTT outside preprocessing bounds: {path}")

    df = df.sort_values(["timestamp", "experiment_id"], kind="stable").reset_index(drop=True)
    return df, path
