from __future__ import annotations

from statistics import fmean

from .models import OptionQuote, Signal


def rsi(closes: list[float], days: int = 14) -> float | None:
    if len(closes) < days + 1:
        return None
    changes = [b - a for a, b in zip(closes[-days - 1 : -1], closes[-days:])]
    avg_gain = fmean(max(change, 0.0) for change in changes)
    avg_loss = fmean(max(-change, 0.0) for change in changes)
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def trend_signal(underlying: str, closes: list[float], cfg: dict) -> Signal | None:
    short_days = int(cfg["short_sma_days"])
    long_days = int(cfg["long_sma_days"])
    if len(closes) < long_days:
        return None
    short = fmean(closes[-short_days:])
    long = fmean(closes[-long_days:])
    momentum = rsi(closes, int(cfg["rsi_days"]))
    if momentum is None:
        return None
    price = closes[-1]
    distance = abs(short / long - 1.0)
    if price > short > long and 45 <= momentum <= 70:
        return Signal(underlying, "CALL", f"price>SMA{short_days}>SMA{long_days}; RSI={momentum:.1f}", distance)
    if price < short < long and 30 <= momentum <= 55:
        return Signal(underlying, "PUT", f"price<SMA{short_days}<SMA{long_days}; RSI={momentum:.1f}", distance)
    return None


def eligible_quote(quote: OptionQuote, signal: Signal, cfg: dict) -> bool:
    dte = quote.dte(quote.timestamp.date())
    if quote.option_type != signal.direction:
        return False
    if not int(cfg["minimum_dte"]) <= dte <= int(cfg["maximum_dte"]):
        return False
    if quote.ask <= 0 or quote.bid < 0 or quote.spread_pct > float(cfg["maximum_spread_pct"]):
        return False
    if quote.volume < int(cfg["minimum_volume"]) or quote.open_interest < int(cfg["minimum_open_interest"]):
        return False
    if quote.delta is None:
        return False
    abs_delta = abs(quote.delta)
    return float(cfg["minimum_abs_delta"]) <= abs_delta <= float(cfg["maximum_abs_delta"])


def select_contract(quotes: list[OptionQuote], signal: Signal, cfg: dict) -> OptionQuote | None:
    eligible = [q for q in quotes if q.underlying == signal.underlying and eligible_quote(q, signal, cfg)]
    if not eligible:
        return None
    return min(
        eligible,
        key=lambda q: (abs(abs(q.delta or 0) - 0.50), q.spread_pct, abs(q.dte(q.timestamp.date()) - 35)),
    )
