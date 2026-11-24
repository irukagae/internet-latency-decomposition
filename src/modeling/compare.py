import argparse
from pathlib import Path
import pandas as pd

from ..feature_engineering import require
from .persistence import comparison_dir, new_id, read_json

def compare_runs(runs):
    references = {}
    rows = []

    for path in runs:
        path = Path(path)
        config = read_json(path / "config.json")
        manifest = read_json(path / "manifest.json")
        metrics = read_json(path / "metrics.json")
        location = config["location"]

        splits = pd.read_csv(path / "split_assignments.csv", dtype={"experiment_id": "string"})
        splits = splits.sort_values("experiment_id").reset_index(drop=True)
        inputs = (manifest["input_sha256"], config["target"], config["features"])

        if location in references:
            previous_inputs, previous_splits = references[location]
            require(inputs == previous_inputs and splits.equals(previous_splits),
                    f"Incompatible data, predictors or split assignments for {location}")
        else:
            references[location] = inputs, splits

        rows.append({"run_id": path.name, "location": location, "model": config["model"],
                     "test_week": config["weeks"]["test"], **metrics["test"]})

    table = pd.DataFrame(rows).sort_values(["location", "model"])
    destination = comparison_dir / new_id()
    destination.mkdir(parents=True)
    path = destination / "model_comparison.csv"
    table.to_csv(path, index=False)
    return path

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compare saved training runs")
    parser.add_argument("runs", nargs="+", type=Path)
    args = parser.parse_args()
    print(compare_runs(args.runs))
