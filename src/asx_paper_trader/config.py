from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_config(path: str | Path) -> dict[str, Any]:
    with Path(path).open(encoding="utf-8") as handle:
        config = json.load(handle)
    risk = float(config["account"]["max_risk_per_trade_pct"])
    if not 0 < risk <= 0.02:
        raise ValueError("max_risk_per_trade_pct must be greater than 0 and no more than 0.02")
    if float(config["account"]["starting_balance"]) <= 0:
        raise ValueError("starting_balance must be positive")
    return config
