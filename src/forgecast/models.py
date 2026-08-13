"""Ensemble: base rate, time-series logistic, discrete hazard, sequence, analogs."""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from forgecast.features import FEATURE_NAMES, HAZARD_FEATURES, SEQUENCE_FEATURES

HAZARD_IDX = [FEATURE_NAMES.index(n) for n in HAZARD_FEATURES]
SEQUENCE_IDX = [FEATURE_NAMES.index(n) for n in SEQUENCE_FEATURES]
ANALOG_RATE_IDX = FEATURE_NAMES.index("analog_rate")
ANALOG_SIM_IDX = FEATURE_NAMES.index("analog_sim")
N90_IDX = FEATURE_NAMES.index("n_90")
ANALOG_BLEND = 0.35


@dataclass
class Ensemble:
    weights: dict[str, float] = field(
        default_factory=lambda: {
            "baseline": 0.25,
            "timeseries": 0.25,
            "hazard": 0.20,
            "sequence": 0.10,
            "analog": 0.20,
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
                        LogisticRegression(
                            max_iter=800,
                            solver="lbfgs",
                            class_weight="balanced",
                        ),
                    ),
                ]
            )

        self.ts_model = _logit().fit(X, y)
        self.hazard_model = _logit().fit(X[:, HAZARD_IDX], y)
        self.seq_model = _logit().fit(X[:, SEQUENCE_IDX], y)

        raw = self._raw_matrix(X)
        blend = self._blend(raw)
        cut = max(int(len(y) * 0.75), 1)
        y_val, p_val = y[cut:], blend[cut:]
        if y_val.sum() >= 8 and (len(y_val) - y_val.sum()) >= 8:
            try:
                iso = IsotonicRegression(out_of_bounds="clip", y_min=0.005, y_max=0.90)
                iso.fit(p_val, y_val)
                check = iso.predict(p_val)
                if float(np.max(check)) >= 0.25 or float(np.max(p_val)) < 0.15:
                    self.calibrator = iso
                else:
                    self.calibrator = None
            except Exception:
                self.calibrator = None
        else:
            self.calibrator = None
        self.fitted = True
        return self

    def _raw_matrix(self, X: np.ndarray) -> dict[str, np.ndarray]:
        n = len(X)
        baseline = np.full(n, self.base_rate)
        analog_rate = np.clip(X[:, ANALOG_RATE_IDX], 0, 1)
        analog_sim = np.clip(X[:, ANALOG_SIM_IDX], 0, 1)
        analog = np.where(
            analog_sim >= ANALOG_BLEND,
            0.75 * analog_rate + 0.25 * self.base_rate,
            baseline,
        )
        ts = self.ts_model.predict_proba(X)[:, 1] if self.ts_model is not None else baseline
        hz = (
            self.hazard_model.predict_proba(X[:, HAZARD_IDX])[:, 1]
            if self.hazard_model is not None
            else baseline
        )
        seq = (
            self.seq_model.predict_proba(X[:, SEQUENCE_IDX])[:, 1]
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

    def _analog_pull(self, X: np.ndarray, blend: np.ndarray) -> np.ndarray:
        analog_rate = np.clip(X[:, ANALOG_RATE_IDX], 0, 1)
        analog_sim = np.clip(X[:, ANALOG_SIM_IDX], 0, 1)
        n_90 = np.clip(X[:, N90_IDX], 0, None)
        w = np.clip((analog_sim - ANALOG_BLEND) / 0.40, 0, 1) * np.clip((n_90 - 8.0) / 50.0, 0, 1)
        pulled = np.maximum(analog_rate, blend)
        return (1.0 - 0.85 * w) * blend + (0.85 * w) * pulled

    def predict_proba(self, X: np.ndarray) -> np.ndarray:
        if not self.fitted or X.size == 0:
            return np.full(max(len(X), 1), self.base_rate)[: len(X)]
        blend = self._analog_pull(X, self._blend(self._raw_matrix(X)))
        if self.calibrator is not None:
            try:
                calibrated = self.calibrator.predict(blend)
                if float(np.max(calibrated)) >= 0.25 or float(np.max(blend)) < 0.15:
                    blend = calibrated
            except Exception:
                pass
        return np.clip(blend, 0.005, 0.90)

    def components(self, x: np.ndarray) -> dict[str, float]:
        raw = self._raw_matrix(x.reshape(1, -1))
        return {k: float(v[0]) for k, v in raw.items()}
