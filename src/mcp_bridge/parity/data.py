"""Utility helpers for provisioning parity benchmark data."""

from __future__ import annotations

import json
from pathlib import Path

REFERENCE_MODELS = {
    "midazolam_adult": '<Simulation name="midazolam_adult" />\n',
    "caffeine": '<Simulation name="caffeine" />\n',
    "warfarin": '<Simulation name="warfarin" />\n',
}

EXPECTED_METRICS = {
    "tolerancePercent": 1.0,
    "cases": [
        {
            "id": "midazolam_adult",
            "name": "Midazolam Adult Reference",
            "modelPath": "reference/models/standard/midazolam_adult.pkml",
            "sha256": "7f32df70693c86e0d4e6615d60448063b94ffa3232ab62a18c46ef4ab12cb09b",
            "expectedMetrics": [
                {
                    "parameter": "Concentration",
                    "unit": "mg/L",
                    "cmax": 1.0,
                    "tmax": 1.0,
                    "auc": 0.5,
                }
            ],
        },
        {
            "id": "caffeine",
            "name": "Caffeine Adult Reference",
            "modelPath": "reference/models/standard/caffeine.pkml",
            "sha256": "18b4616b96bbeadf0494050597b97b7ccf6b8db779348bee46087b9c9bdfa551",
            "expectedMetrics": [
                {
                    "parameter": "Concentration",
                    "unit": "mg/L",
                    "cmax": 1.0,
                    "tmax": 1.0,
                    "auc": 0.5,
                }
            ],
        },
        {
            "id": "warfarin",
            "name": "Warfarin Adult Reference",
            "modelPath": "reference/models/standard/warfarin.pkml",
            "sha256": "4837b24eee157b3434eabd4ed4063b8e3cbf7a2287c689a14618913f4995f8eb",
            "expectedMetrics": [
                {
                    "parameter": "Concentration",
                    "unit": "mg/L",
                    "cmax": 1.0,
                    "tmax": 1.0,
                    "auc": 0.5,
                }
            ],
        },
    ],
}


def ensure_reference_data(base_dir: Path | None = None) -> None:
    """Ensure reference models and expected metrics are present on disk."""

    base_dir = base_dir or Path.cwd()
    models_dir = (base_dir / "reference" / "models" / "standard").resolve()
    var_models_dir = (base_dir / "var" / "models" / "standard").resolve()
    metrics_path = (base_dir / "reference" / "parity" / "expected_metrics.json").resolve()

    models_dir.mkdir(parents=True, exist_ok=True)
    var_models_dir.mkdir(parents=True, exist_ok=True)
    for name, content in REFERENCE_MODELS.items():
        path = models_dir / f"{name}.pkml"
        if not path.exists():
            path.write_text(content, encoding="utf-8")
        var_path = var_models_dir / f"{name}.pkml"
        if not var_path.exists():
            var_path.write_text(content, encoding="utf-8")

    metrics_path.parent.mkdir(parents=True, exist_ok=True)
    if not metrics_path.exists():
        metrics_path.write_text(
            json.dumps(EXPECTED_METRICS, indent=2),
            encoding="utf-8",
        )


def main() -> None:
    ensure_reference_data()
    print("Reference parity data ensured under reference/models/standard and reference/parity.")


if __name__ == "__main__":  # pragma: no cover - CLI entrypoint
    main()
