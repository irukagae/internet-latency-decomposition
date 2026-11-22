# shared validation/training/test splits

import pandas as pd
from ..feature_engineering import require

def split_weeks(development, test, validation_fraction):
    require(0 < validation_fraction < 1, "Validation fraction must be between 0 and 1")
    require(not development["experiment_id"].isin(test["experiment_id"]).any(), "Experiment IDs overlap across development and test")
    require(development["timestamp"].max() < test["timestamp"].min(), "Development and test overlap in time")

    # keep experiments recorded at the same timestamp in the same partition
    times = development["timestamp"].drop_duplicates().sort_values().reset_index(drop=True)
    cut = int(len(times) * (1 - validation_fraction))
    require(0 < cut < len(times), "Too few distinct timestamps for the requested split")

    boundary = times.iloc[cut]
    train = development.loc[development["timestamp"].lt(boundary)]
    valid = development.loc[development["timestamp"].ge(boundary)]

    assignment = []
    for label, frame in (("train",train), ("validation", valid), ("test", test)):
        rows = frame[["experiment_id", "timestamp", "location", "week"]].copy()
        rows["split"] = label
        assignment.append(rows)

    return train, valid, pd.concat(assignment, ignore_index=True)
