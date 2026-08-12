"""Ensemble: base rate, time-series logistic, discrete hazard, sequence, analogs."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from forgecast.features import FEATURE_NAMES


@dataclass
class Ensemble:
    weights: dict[str, float] = field(
        default_factory=lambda: {
            "baseline": 0.40,
            "timeseries": 0.30,
            "hazard": 0.15,
            "sequence": 0.10,
            "analog": 0.05,
        }
    )
    ts_model: Pipeline | None = None
    hazard_model: Pipeline | None = None
    seq_model: Pipeline | None = None
    calibrator: IsotonicRegression | None = None
    base_rate: float = 0.08
    fitted: bool = False

    def fit(self, X: np.ndarray, y: np.ndarray) -> Ensemble:
        y = y.astype(int)
        self.base_rate = float(np.mean(y)) if len(y) else 0.08
        if len(np.unique(y)) < 2 or len(y) < 20:
            self.fitted = True
            return self

        def _logit() -> Pipeline:
            return Pipeline(
                [
                    ("scale", StandardScaler()),
                    (
                        "clf",
                        LogisticRegression(max_iter=800, solver="lbfgs"),
                    ),
                ]
            )

        self.ts_model = _logit().fit(X, y)
        # Hazard uses the same snapshot labels but emphasizes recency features.
        self.hazard_model = _logit().fit(X[:, [0, 3, 4, 6, 7, 12, 13]], y)
        # Sequence-like: event-mix buckets only.
        self.seq_model = _logit().fit(X[:, [3, 4, 5, 6, 7, 8]], y)

        raw = self._raw_matrix(X)
        blend = self._blend(raw)
        # Hold out the last 20% in time order for isotonic calibration.
        cut = max(int(len(y) * 0.75), 1)
        y_val, p_val = y[cut:], blend[cut:]
        if y_val.sum() >= 2 and (len(y_val) - y_val.sum()) >= 2:
            try:
                iso = IsotonicRegression(out_of_bounds="clip", y_min=0.005, y_max=0.90)
                iso.fit(p_val, y_val)
                self.calibrator = iso
            except Exception:
                self.calibrator = None
        else:
            self.calibrator = None
        self.fitted = True
        return self

    def _raw_matrix(self, X: np.ndarray) -> dict[str, np.ndarray]:
        n = len(X)
        baseline = np.full(n, self.base_rate)
        analog_rate = np.clip(X[:, FEATURE_NAMES.index("analog_rate")], 0, 1)
        analog_sim = np.clip(X[:, FEATURE_NAMES.index("analog_sim")], 0, 1)
        analog = np.where(
            analog_sim >= 0.5,
            0.6 * analog_rate + 0.4 * self.base_rate,
            baseline,
        )
        ts = (
            self.ts_model.predict_proba(X)[:, 1]
            if self.ts_model is not None
            else baseline
        )
        hz = (
            self.hazard_model.predict_proba(X[:, [0, 3, 4, 6, 7, 12, 13]])[:, 1]
            if self.hazard_model is not None
            else baseline
        )
        seq = (
            self.seq_model.predict_proba(X[:, [3, 4, 5, 6, 7, 8]])[:, 1]
            if self.seq_model is not None
            else baseline
        )
        return {
            "baseline": baseline,
            "timeseries": ts,
            "hazard": hz,
            "sequence": seq,
            "analog": analog,
        }

    def _blend(self, raw: dict[str, np.ndarray]) -> np.ndarray:
        acc = np.zeros(len(next(iter(raw.values()))))
        wsum = 0.0
        for name, w in self.weights.items():
            acc = acc + w * raw[name]
            wsum += w
        return acc / wsum

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if not self.fitted or X.size == 0:
            return np.full(max(len(X), 1), self.base_rate)[: len(X)]
        blend = self._blend(self._raw_matrix(X))
        if self.calibrator is not None:
            try:
                blend = self.calibrator.predict(blend)
            except Exception:
                pass
        return np.clip(blend, 0.005, 0.90)

    def components(self, x: np.ndarray) -> dict[str, float]:
        raw = self._raw_matrix(x.reshape(1, -1))
        return {k: float(v[0]) for k, v in raw.items()}
