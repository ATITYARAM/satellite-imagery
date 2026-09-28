"""Prototype XGBoost model for paired 2016/2026 satellite imagery.

This is intentionally limited to the two available satellite observations.
Because no erosion ground-truth labels are present yet, the classifier target
is a paired-image change proxy: increased MNDWI together with decreased NDVI.
The model is a real XGBClassifier run; this is not the final validated
five-domain erosion model.
"""
from __future__ import annotations

import datetime as dt
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = ROOT / "data" / "satellite"
OUTPUT_DIR = ROOT / "outputs" / "xgboost"
RESULT_IMAGE = OUTPUT_DIR / "erosion_change_xgboost.png"
RESULT_JSON = OUTPUT_DIR / "result.json"

YEARS = (2016, 2026)
BAND_FILES = {
    "blue": "B2_blue.tif",
    "green": "B3_green.tif",
    "red": "B4_red.tif",
    "nir": "B5_nir.tif",
    "swir1": "B6_swir1.tif",
    "swir2": "B7_swir2.tif",
}
BAND_ORDER = list(BAND_FILES)


def _scaled(dn: np.ndarray) -> np.ndarray:
    out = dn.astype("float32")
    out[out <= 0] = np.nan
    return out * 0.0000275 - 0.2


def _safe_index(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    den = a + b
    with np.errstate(divide="ignore", invalid="ignore"):
        return np.where(np.abs(den) > 1e-6, (a - b) / den, np.nan)


def _read_year(year: int, max_pixels: int = 180_000) -> tuple[dict[str, np.ndarray], tuple[int, int]]:
    import rasterio
    from rasterio.enums import Resampling

    year_dir = DATA_ROOT / str(year)
    first_path = year_dir / BAND_FILES["blue"]
    if not first_path.exists():
        raise FileNotFoundError(f"Missing satellite band data for {year}: {first_path}")

    with rasterio.open(first_path) as src:
        height, width = src.height, src.width

    total = height * width
    scale = max(1.0, math.sqrt(total / max_pixels))
    out_height = max(1, int(round(height / scale)))
    out_width = max(1, int(round(width / scale)))

    values: dict[str, np.ndarray] = {}
    for name, filename in BAND_FILES.items():
        path = year_dir / filename
        if not path.exists():
            raise FileNotFoundError(f"Missing satellite band data for {year}: {path}")
        with rasterio.open(path) as src:
            dn = src.read(
                1,
                out_shape=(out_height, out_width),
                resampling=Resampling.bilinear,
            )
        values[name] = _scaled(dn)

    return values, (out_height, out_width)


def _build_features(
    old: dict[str, np.ndarray],
    new: dict[str, np.ndarray],
) -> tuple[np.ndarray, np.ndarray, list[str], np.ndarray]:
    old_ndvi = _safe_index(old["nir"], old["red"])
    old_ndwi = _safe_index(old["green"], old["nir"])
    old_mndwi = _safe_index(old["green"], old["swir1"])
    old_savi = 1.5 * (old["nir"] - old["red"]) / (old["nir"] + old["red"] + 0.5)

    new_ndvi = _safe_index(new["nir"], new["red"])
    new_ndwi = _safe_index(new["green"], new["nir"])
    new_mndwi = _safe_index(new["green"], new["swir1"])
    new_savi = 1.5 * (new["nir"] - new["red"]) / (new["nir"] + new["red"] + 0.5)

    old_savi[~np.isfinite(old_savi)] = np.nan
    new_savi[~np.isfinite(new_savi)] = np.nan

    arrays: list[np.ndarray] = []
    names: list[str] = []

    for year_name, source in (("2016", old), ("2026", new)):
        for name in BAND_ORDER:
            arrays.append(source[name])
            names.append(f"{name}_{year_name}")

    old_indices = [old_ndvi, old_ndwi, old_mndwi, old_savi]
    new_indices = [new_ndvi, new_ndwi, new_mndwi, new_savi]
    index_names = ["ndvi", "ndwi", "mndwi", "savi"]

    for name, value in zip(index_names, old_indices):
        arrays.append(value)
        names.append(f"{name}_2016")
    for name, value in zip(index_names, new_indices):
        arrays.append(value)
        names.append(f"{name}_2026")

    delta_arrays = [
        new_ndvi - old_ndvi,
        new_ndwi - old_ndwi,
        new_mndwi - old_mndwi,
        new_savi - old_savi,
    ]
    for name, value in zip(index_names, delta_arrays):
        arrays.append(value)
        names.append(f"delta_{name}")

    stacked = np.stack(arrays, axis=-1).astype("float32")
    finite = np.isfinite(stacked).all(axis=-1)
    flat = stacked.reshape(-1, stacked.shape[-1])
    valid = finite.reshape(-1)

    change_signal = (new_mndwi - old_mndwi) - 0.5 * (new_ndvi - old_ndvi)
    return flat, valid, names, change_signal


def _signature() -> str:
    parts = []
    for year in YEARS:
        for filename in BAND_FILES.values():
            path = DATA_ROOT / str(year) / filename
            if not path.exists():
                raise FileNotFoundError(f"Missing input band: {path}")
            stat = path.stat()
            parts.append(f"{path}:{stat.st_size}:{stat.st_mtime_ns}")
    return "|".join(parts)


def run_xgboost(force: bool = False) -> dict[str, Any]:
    signature = _signature()
    if not force and RESULT_JSON.exists() and RESULT_IMAGE.exists():
        try:
            cached = json.loads(RESULT_JSON.read_text(encoding="utf-8"))
            if cached.get("input_signature") == signature:
                return cached
        except (OSError, ValueError, TypeError):
            pass

    from sklearn.model_selection import train_test_split
    from xgboost import XGBClassifier

    old, old_shape = _read_year(2016)
    new, new_shape = _read_year(2026)
    if old_shape != new_shape:
        raise RuntimeError(f"2016 and 2026 grids differ after resampling: {old_shape} vs {new_shape}")

    features, valid, feature_names, change_signal = _build_features(old, new)

    valid_signal = change_signal.reshape(-1)[valid]
    if valid_signal.size < 100:
        raise RuntimeError("Too few valid paired pixels for XGBoost.")

    low_q, high_q = np.nanpercentile(valid_signal, [45, 55])
    target = np.full(valid_signal.shape, -1, dtype=np.int8)
    target[valid_signal <= low_q] = 0
    target[valid_signal >= high_q] = 1
    train_mask = target >= 0

    x = features[valid][train_mask]
    y = target[train_mask]
    if np.unique(y).size < 2:
        raise RuntimeError("Paired-image change proxy produced only one class.")

    sample_x = x
    sample_y = y
    max_train = 90_000
    if len(sample_y) > max_train:
        rng = np.random.default_rng(42)
        idx = rng.choice(len(sample_y), size=max_train, replace=False)
        sample_x = sample_x[idx]
        sample_y = sample_y[idx]

    x_train, _, y_train, _ = train_test_split(
        sample_x,
        sample_y,
        test_size=0.2,
        random_state=42,
        stratify=sample_y,
    )

    model = XGBClassifier(
        n_estimators=180,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.85,
        colsample_bytree=0.85,
        objective="binary:logistic",
        eval_metric="logloss",
        tree_method="hist",
        n_jobs=2,
        random_state=42,
    )
    model.fit(x_train, y_train)

    all_valid = features[valid]
    probabilities = np.full(features.shape[0], np.nan, dtype="float32")
    probabilities[valid] = model.predict_proba(all_valid)[:, 1]
    prob_map = probabilities.reshape(old_shape)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    _write_result_image(new, prob_map, RESULT_IMAGE)

    importance = np.asarray(model.feature_importances_, dtype=float)
    top_idx = np.argsort(importance)[::-1][:8]
    top_features = [
        {"name": feature_names[int(i)], "importance": float(importance[int(i)])}
        for i in top_idx
        if importance[int(i)] > 0
    ]

    high_score_threshold = 0.70
    high_score_pixels = int(np.isfinite(prob_map).sum() and np.sum(prob_map >= high_score_threshold))
    pixels_analyzed = int(np.isfinite(prob_map).sum())
    mean_probability = float(np.nanmean(prob_map)) if pixels_analyzed else 0.0

    result = {
        "status": "ok",
        "model": "XGBoost",
        "classifier": "XGBClassifier",
        "input_years": [2016, 2026],
        "feature_count": int(len(feature_names)),
        "n_estimators": 180,
        "pixels_analyzed": pixels_analyzed,
        "training_samples": int(len(sample_y)),
        "pseudo_positive_percent": float(np.mean(sample_y) * 100.0),
        "high_score_percent": float(high_score_pixels / max(1, pixels_analyzed) * 100.0),
        "mean_probability": mean_probability,
        "pseudo_label": "higher MNDWI with lower NDVI between 2016 and 2026",
        "image_url": "/xgboost/result.png",
        "run_id": dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ"),
        "input_signature": signature,
        "top_features": top_features,
    }
    RESULT_JSON.write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def _write_result_image(
    new: dict[str, np.ndarray],
    probability: np.ndarray,
    output_path: Path,
) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    red = new["red"]
    green = new["green"]
    blue = new["blue"]
    rgb_bands = []
    for band in (red, green, blue):
        finite = np.isfinite(band)
        if not np.any(finite):
            rgb_bands.append(np.zeros_like(band, dtype="float32"))
            continue
        low, high = np.nanpercentile(band, [2, 98])
        rgb_bands.append(np.clip((band - low) / max(high - low, 1e-6), 0.0, 1.0))

    base = np.stack(rgb_bands, axis=-1)
    finite = np.isfinite(probability)
    safe_probability = np.where(finite, probability, 0.0)
    cmap = plt.get_cmap("RdYlGn_r")
    overlay = cmap(safe_probability)[..., :3].astype("float32")

    alpha = np.where(finite, 0.18 + 0.72 * safe_probability, 0.0).astype("float32")
    composite = base * (1.0 - alpha[..., None]) + overlay * alpha[..., None]
    composite[~finite] = 0.0

    plt.imsave(output_path, composite, format="png")
