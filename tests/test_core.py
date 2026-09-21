from __future__ import annotations

import tempfile
import unittest
from unittest.mock import patch
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

from asx_paper_trader.ledger import Ledger
from asx_paper_trader.models import Candidate, OptionQuote, Signal
from asx_paper_trader.risk import size_candidate
from asx_paper_trader.strategy import trend_signal
from asx_paper_trader.watchlist import build_watchlist


class CoreTests(unittest.TestCase):
    def setUp(self):
        self.account = {"max_risk_per_trade_pct": 0.02, "fee_per_contract": 0}
        self.strategy = {"short_sma_days": 20, "long_sma_days": 50, "rsi_days": 14}

    def quote(self, ask: float) -> OptionQuote:
        return OptionQuote(
            datetime.now(timezone.utc), "BHP", "BHPX", date.today() + timedelta(days=35),
            "CALL", 45, ask - 0.1, ask, ask - 0.05, 10, 100, 46, 0.5, 100,
        )

    def test_two_percent_position_cap(self):
        candidate = size_candidate(self.quote(1.10), Signal("BHP", "CALL", "test", 1), 10_000, self.account)
        self.assertIsNotNone(candidate)
        self.assertEqual(candidate.quantity, 1)
        self.assertEqual(candidate.risk_amount, 110)

    def test_rejects_one_contract_over_budget(self):
        self.assertIsNone(size_candidate(self.quote(2.01), Signal("BHP", "CALL", "test", 1), 10_000, self.account))

    def test_bullish_trend(self):
        closes = []
        value = 90.0
        for i in range(50):
            value += -0.15 if i % 3 == 2 else 0.10
            closes.append(value)
        signal = trend_signal("BHP", closes, self.strategy)
        self.assertIsNotNone(signal)
        self.assertEqual(signal.direction, "CALL")

    def test_ledger_initial_balance(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = Ledger(Path(directory) / "ledger.db", 10_000)
            self.assertEqual(ledger.cash(), 10_000)
            ledger.close()

    def test_close_trade_cash_and_pnl(self):
        with tempfile.TemporaryDirectory() as directory:
            ledger = Ledger(Path(directory) / "ledger.db", 10_000)
            quote = self.quote(1.10)
            candidate = Candidate(quote, Signal("BHP", "CALL", "test", 1), 1, 1.10, 110)
            trade_id = ledger.open_trade(candidate)
            self.assertEqual(ledger.cash(), 9_890)
            pnl = ledger.close_trade(trade_id, 1.30, "test exit", quote.timestamp)
            self.assertEqual(pnl, 20)
            self.assertEqual(ledger.cash(), 10_020)
            self.assertEqual(ledger.realised_pnl(), 20)
            ledger.close()

    @patch("asx_paper_trader.watchlist._daily_series")
    def test_watchlist_does_not_open_option_trade(self, daily_series):
        daily_series.return_value = [
            ((date.today() - timedelta(days=59 - index)).isoformat(), 90 + index * 0.2)
            for index in range(60)
        ]
        config = {
            "market": {"timezone": "Australia/Sydney", "universe": ["BHP"]},
            "strategy": self.strategy,
        }
        with tempfile.TemporaryDirectory() as directory:
            report = build_watchlist(config, "test-key", directory)
            self.assertEqual(len(report["all_results"]), 1)
            self.assertIn("No option contract", report["notice"])
            self.assertTrue((Path(directory) / "daily_watchlist.json").exists())
            self.assertTrue((Path(directory) / "daily_watchlist.csv").exists())


if __name__ == "__main__":
    unittest.main()
