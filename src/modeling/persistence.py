import hashlib
import json
import platform
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4
import joblib

project_root = Path(__file__).resolve().parents[2]
training_dir = project_root / "artifacts" / "training"
comparison_dir = project_root / "results" / "comparisons"

def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))

def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")

def new_id():
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{timestamp}_{uuid4().hex[:10]}"

def save_run(config, model, metrics, predictions, assignments, paths):
    training_dir.mkdir(parents=True, exist_ok=True)
    run_id = f"{config['location']}_{config['model']}_{new_id()}"
    destination = training_dir / run_id

    packages = ["numpy", "pandas", "scikit-learn", "joblib"]
    if config["model"] == "xgboost":
        packages.append("xgboost")

    hashes = {str(path.relative_to(project_root)): hashlib.sha256(path.read_bytes()).hexdigest() for path in paths}
    manifest = {"input_sha256": hashes, "python": platform.python_version(),
                "packages": {name: version(name) for name in packages}}

    # publish the run directory only after all its files have been written
    with TemporaryDirectory(dir=training_dir) as temporary:
        stage = Path(temporary) / run_id
        stage.mkdir()

        write_json(stage / "config.json", config)
        write_json(stage / "manifest.json", manifest)
        write_json(stage / "metrics.json", metrics)
        predictions.to_csv(stage / "prediction.csv", index=False)
        assignments.to_csv(stage / "split_assignments.csv", index=False)
        joblib.dump(model, stage / "model.joblib")

        stage.rename(destination)

    return destination
