from __future__ import annotations

import csv
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

from .models import OptionQuote


def _parse_timestamp(value: str) -> datetime:
    value = value.strip().replace("Z", "+00:00")
    return datetime.fromisoformat(value)


def read_option_quotes(path: str | Path) -> list[OptionQuote]:
    quotes: list[OptionQuote] = []
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            raw_delta = row.get("delta", "").strip()
            quotes.append(
                OptionQuote(
                    timestamp=_parse_timestamp(row["timestamp"]),
                    underlying=row["underlying"].strip().upper(),
                    symbol=row["symbol"].strip().upper(),
                    expiry=date.fromisoformat(row["expiry"].strip()),
                    option_type=row["option_type"].strip().upper(),
                    strike=float(row["strike"]),
                    bid=float(row["bid"]),
                    ask=float(row["ask"]),
                    last=float(row["last"]),
                    volume=int(row["volume"]),
                    open_interest=int(row["open_interest"]),
                    underlying_price=float(row["underlying_price"]),
                    delta=float(raw_delta) if raw_delta else None,
                    multiplier=int(row.get("multiplier") or 100),
                )
            )
    return quotes


def read_price_history(path: str | Path) -> dict[str, list[tuple[date, float]]]:
    history: dict[str, list[tuple[date, float]]] = defaultdict(list)
    with Path(path).open(newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            history[row["underlying"].strip().upper()].append(
                (date.fromisoformat(row["date"].strip()), float(row["close"]))
            )
    for values in history.values():
        values.sort(key=lambda item: item[0])
    return dict(history)
