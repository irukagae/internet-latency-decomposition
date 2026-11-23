import numpy as np
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from ..feature_engineering import FEATURE_COLUMNS, require

def evaluate(df, model, target, split):
    prediction = model.predict(df[FEATURE_COLUMNS])
    require(np.isfinite(prediction).all(), f"Non-finite {split} prediction")

    actual = df[target]
    metric = {"n": len(df), "mae_ms": float(mean_absolute_error(actual, prediction)),
              "rmse_ms": float(np.sqrt(mean_squared_error(actual, prediction))),
              "r2": float(r2_score(actual, prediction)) if actual.nunique() > 1 else None,
              "negative_prediction": int(np.sum(prediction < 0))}

    columns = ["experiment_id", "timestamp", "location", "week", "clock_regime", "protocol", "dst_ip", "packet_size", target]
    rows = df[columns].copy()
    rows["split"] = split
    rows["prediction_ms"] = prediction
    rows["error_ms"] = prediction - actual
    rows["absolute_error_ms"] = rows["error_ms"].abs()

    return metric, rows
