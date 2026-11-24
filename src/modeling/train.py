import argparse
import logging
import pandas as pd

from ..feature_engineering import FEATURE_COLUMNS
from .baselines import linear_regression
from .data import load_week, project_root
from .evaluation import evaluate
from .persistence import new_id, read_json, save_run
from .splits import split_weeks

config_dir = project_root / "configs" / "training"
log_dir = project_root / "logs" / "training"
log = logging.getLogger("training")

def train_location(location, names, experiment):
    weeks = experiment["weeks"][location]
    target = experiment["target"]

    development, dev_path = load_week(location, weeks["development"], target)
    test, test_path = load_week(location, weeks["test"], target)
    train, valid, assignments = split_weeks(development, test, experiment["validation_fraction"])

    log.info("%s: %d train, %d validation, %d test", location, len(train), len(valid), len(test))
    runs = []

    for name in names:
        settings = read_json(config_dir / f"{name}.json")

        if name == "linear_regression":
            fit = linear_regression.fit_baseline
        else:
            from .baselines.xg_boost import fit_baseline
            fit = fit_baseline
            settings["random_state"] = experiment["seed"]

        selection_model, final_model, final_settings = fit(train[FEATURE_COLUMNS], train[target],
            valid[FEATURE_COLUMNS], valid[target], settings)

        valid_metrics, valid_rows = evaluate(selection_model, valid, target, "validation")

        # Refit using the full development week before evaluating on week 3.
        final_model.fit(development[FEATURE_COLUMNS], development[target])
        test_metrics, test_rows = evaluate(final_model, test, target, "test")

        config = {"model": name, "location": location, "target": target, "features": list(FEATURE_COLUMNS), "weeks": weeks,
                  "validation_fraction": experiment["validation_fraction"], "seed": experiment["seed"], "selection_settings": settings,
                  "final_settings": final_settings}

        run = save_run(config, final_model, {"validation": valid_metrics, "test": test_metrics},
                       pd.concat([valid_rows, test_rows], ignore_index=True), assignments, [dev_path, test_path])

        log.info("%s/%s: test MAE %.3f ms, RMSE %.3f ms", location, name, test_metrics["mae_ms"], test_metrics["rmse_ms"])
        log.info("Saved %s", run)
        runs.append(run)

    return runs

def main():
    parser = argparse.ArgumentParser(description="Train standalone RTT baselines")
    parser.add_argument("--model", choices=["all", "linear_regression", "xgboost"], default="all")
    parser.add_argument("--location", choices=["all", "sg", "in"], default="all")
    args = parser.parse_args()

    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
                        handlers=[logging.StreamHandler(), logging.FileHandler(log_dir / f"{new_id()}.log", encoding="utf-8")])

    experiment = read_json(config_dir / "experiment.json")
    locations = list(experiment["weeks"]) if args.location == "all" else [args.location]
    names = ["linear_regression", "xgboost"] if args.model == "all" else [args.model]

    runs = []
    for location in locations:
        runs.extend(train_location(location, names, experiment))

    if len(names) > 1:
        from .compare import compare_runs
        log.info("Saved comparison to %s", compare_runs(runs))


if __name__ == "__main__":
    main()
    