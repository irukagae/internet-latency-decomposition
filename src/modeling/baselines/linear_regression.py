from sklearn.base import clone
from sklearn.feature_selection import VarianceThreshold
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

def fit_baseline(x_train, y_train, x_valid, y_valid, settings):
    # a location indicator is constant when training one model per location
    model = Pipeline([("remove_constants", VarianceThreshold()),
                      ("scale", StandardScaler()),
                      ("regression", LinearRegression(**settings))])

    model.fit(x_train, y_train)

    return model, clone(model), dict(settings)
