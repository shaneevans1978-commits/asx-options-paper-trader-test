from __future__ import annotations

import math

from .models import Candidate, OptionQuote, Signal


def size_candidate(quote: OptionQuote, signal: Signal, equity: float, cfg: dict) -> Candidate | None:
    fee = float(cfg.get("fee_per_contract", 0.0))
    risk_budget = equity * float(cfg["max_risk_per_trade_pct"])
    risk_per_contract = quote.ask * quote.multiplier + fee
    if risk_per_contract <= 0:
        return None
    quantity = math.floor(risk_budget / risk_per_contract)
    if quantity < 1:
        return None
    risk_amount = round(quantity * risk_per_contract, 2)
    if risk_amount > risk_budget + 0.001:
        raise AssertionError("position sizing exceeded risk budget")
    return Candidate(quote, signal, quantity, quote.ask, risk_amount)
