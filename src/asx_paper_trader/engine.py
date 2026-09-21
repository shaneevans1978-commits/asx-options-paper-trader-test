from __future__ import annotations

from datetime import datetime

from .ledger import Ledger
from .models import OptionQuote
from .risk import size_candidate
from .strategy import select_contract, trend_signal


def _latest_quotes(quotes: list[OptionQuote]) -> dict[str, OptionQuote]:
    result: dict[str, OptionQuote] = {}
    for quote in quotes:
        current = result.get(quote.symbol)
        if current is None or quote.timestamp > current.timestamp:
            result[quote.symbol] = quote
    return result


def process_exits(ledger: Ledger, quotes: list[OptionQuote], cfg: dict) -> list[str]:
    latest = _latest_quotes(quotes)
    messages: list[str] = []
    for trade in ledger.open_trades():
        quote = latest.get(trade["option_symbol"])
        if quote is None:
            continue
        entry = float(trade["entry_price"])
        return_pct = quote.bid / entry - 1.0
        held_days = (quote.timestamp.date() - datetime.fromisoformat(trade["opened_at"]).date()).days
        dte = quote.dte(quote.timestamp.date())
        reason = None
        if return_pct <= -float(cfg["stop_loss_pct"]):
            reason = "stop loss"
        elif return_pct >= float(cfg["take_profit_pct"]):
            reason = "take profit"
        elif dte <= int(cfg["exit_dte"]):
            reason = "expiry risk"
        elif held_days >= int(cfg["maximum_holding_days"]):
            reason = "maximum holding period"
        if reason:
            pnl = ledger.close_trade(int(trade["id"]), quote.bid, reason, quote.timestamp)
            messages.append(f"CLOSE {quote.symbol} @ {quote.bid:.2f}; P/L {pnl:+.2f}; {reason}")
    return messages


def run_scan(ledger: Ledger, quotes: list[OptionQuote], history: dict, config: dict) -> list[str]:
    strategy_cfg = config["strategy"]
    account_cfg = config["account"]
    universe = set(config["market"]["universe"])
    messages = process_exits(ledger, quotes, strategy_cfg)
    signals = []
    for underlying, dated_prices in history.items():
        if underlying not in universe:
            continue
        signal = trend_signal(underlying, [price for _, price in dated_prices], strategy_cfg)
        if signal:
            signals.append(signal)
    for signal in sorted(signals, key=lambda item: item.score, reverse=True):
        if ledger.open_count() >= int(account_cfg["max_open_positions"]):
            ledger.record_scan("SKIP", "maximum open positions reached", signal.underlying)
            break
        if ledger.has_open_underlying(signal.underlying):
            ledger.record_scan("SKIP", "underlying already has an open trade", signal.underlying)
            continue
        contract = select_contract(quotes, signal, strategy_cfg)
        if contract is None:
            ledger.record_scan("NO_CONTRACT", signal.reason, signal.underlying)
            continue
        candidate = size_candidate(contract, signal, ledger.equity_for_sizing(), account_cfg)
        if candidate is None:
            ledger.record_scan("RISK_REJECT", "one contract exceeds 2% risk budget", signal.underlying)
            continue
        total_cap = ledger.equity_for_sizing() * float(account_cfg["max_total_open_risk_pct"])
        if ledger.open_risk() + candidate.risk_amount > total_cap + 0.001:
            ledger.record_scan("RISK_REJECT", "total open risk cap exceeded", signal.underlying)
            continue
        if candidate.risk_amount > ledger.cash():
            ledger.record_scan("RISK_REJECT", "insufficient paper cash", signal.underlying)
            continue
        trade_id = ledger.open_trade(candidate)
        messages.append(
            f"OPEN #{trade_id} {contract.symbol}: {candidate.quantity} @ {candidate.entry_price:.2f}; "
            f"max loss ${candidate.risk_amount:.2f}; {signal.reason}"
        )
    ledger.record_scan("SCAN_COMPLETE", f"{len(signals)} signals; {len(messages)} actions")
    return messages
