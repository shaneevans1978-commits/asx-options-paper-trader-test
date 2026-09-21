from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime


@dataclass(frozen=True)
class OptionQuote:
    timestamp: datetime
    underlying: str
    symbol: str
    expiry: date
    option_type: str
    strike: float
    bid: float
    ask: float
    last: float
    volume: int
    open_interest: int
    underlying_price: float
    delta: float | None
    multiplier: int = 100

    @property
    def mid(self) -> float:
        return round((self.bid + self.ask) / 2, 4)

    @property
    def spread_pct(self) -> float:
        return (self.ask - self.bid) / self.mid if self.mid > 0 else float("inf")

    def dte(self, as_of: date) -> int:
        return (self.expiry - as_of).days


@dataclass(frozen=True)
class Signal:
    underlying: str
    direction: str
    reason: str
    score: float


@dataclass(frozen=True)
class Candidate:
    quote: OptionQuote
    signal: Signal
    quantity: int
    entry_price: float
    risk_amount: float
