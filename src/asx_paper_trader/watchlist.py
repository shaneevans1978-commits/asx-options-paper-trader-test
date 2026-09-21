from __future__ import annotations

import csv
import json
import os
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from .strategy import rsi, trend_signal


API_URL = "https://www.alphavantage.co/query"


def _daily_series(symbol: str, api_key: str) -> list[tuple[str, float]]:
    query = urlencode({
        "function": "TIME_SERIES_DAILY",
        "symbol": f"{symbol}.AX",
        "outputsize": "compact",
        "apikey": api_key,
    })
    request = Request(f"{API_URL}?{query}", headers={"User-Agent": "asx-paper-trader/0.1"})
    with urlopen(request, timeout=30) as response:
        payload = json.load(response)
    if "Error Message" in payload:
        raise RuntimeError(f"{symbol}: provider rejected symbol")
    if "Note" in payload or "Information" in payload:
        message = payload.get("Note") or payload.get("Information")
        raise RuntimeError(f"{symbol}: provider limit: {message}")
    series = payload.get("Time Series (Daily)")
    if not isinstance(series, dict) or not series:
        raise RuntimeError(f"{symbol}: no daily history returned")
    return sorted((day, float(values["4. close"])) for day, values in series.items())


def build_watchlist(config: dict, api_key: str, output_dir: str | Path) -> dict:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    today = datetime.now(ZoneInfo(config["market"]["timezone"])).date().isoformat()
    rows: list[dict] = []
    errors: list[str] = []
    latest_dates: set[str] = set()

    for index, symbol in enumerate(config["market"]["universe"]):
        try:
            history = _daily_series(symbol, api_key)
            latest_date = history[-1][0]
            latest_dates.add(latest_date)
            closes = [close for _, close in history]
            signal = trend_signal(symbol, closes, config["strategy"])
            rows.append({
                "symbol": symbol,
                "date": latest_date,
                "close": round(closes[-1], 4),
                "direction": signal.direction if signal else "NO ACTION",
                "reason": signal.reason if signal else "Trend/RSI rules not met",
                "strength": round(signal.strength, 6) if signal else 0.0,
                "rsi": round(rsi(closes, int(config["strategy"]["rsi_days"])) or 0.0, 2),
            })
        except Exception as exc:
            errors.append(str(exc))
        if index + 1 < len(config["market"]["universe"]):
            time.sleep(0.8)

    status = "complete"
    if not rows:
        status = "failed"
    elif errors:
        status = "partial"
    elif latest_dates != {today}:
        status = "market_closed_or_data_not_updated"

    report = {
        "generated_at": datetime.now(ZoneInfo(config["market"]["timezone"])).isoformat(),
        "status": status,
        "data_dates": sorted(latest_dates),
        "signals": [row for row in rows if row["direction"] != "NO ACTION"],
        "all_results": rows,
        "errors": errors,
        "notice": "Share-price signals only. No option contract was selected and no trade was opened.",
    }
    (output_path / "daily_watchlist.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    with (output_path / "daily_watchlist.csv").open("w", newline="", encoding="utf-8") as handle:
        fields = ["symbol", "date", "close", "direction", "reason", "strength", "rsi"]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return report


def api_key_from_environment() -> str:
    key = os.environ.get("ALPHA_VANTAGE_API_KEY", "").strip()
    if not key:
        raise RuntimeError("ALPHA_VANTAGE_API_KEY is not configured")
    return key
