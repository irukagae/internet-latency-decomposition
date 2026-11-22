from xgboost import XGBRegressor

def fit_baseline(x_train, y_train, x_valid, y_valid, settings):
    model = XGBRegressor(**settings)

    # select the number of trees using only the validation portion
    model.fit(x_train, y_train, eval_set=[(x_valid, y_valid)], verbose=False)

    final_settings = dict(settings)
    final_settings.pop("early_stopping_round")
    final_settings["n_estimators"] = int(model.best_iteration) + 1

    return model, XGBRegressor(**final_settings), final_settings
