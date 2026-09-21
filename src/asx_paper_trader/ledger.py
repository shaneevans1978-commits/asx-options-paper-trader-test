from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from .models import Candidate


SCHEMA = """
CREATE TABLE IF NOT EXISTS account_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  occurred_at TEXT NOT NULL,
  event_type TEXT NOT NULL,
  amount REAL NOT NULL,
  note TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS trades (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  opened_at TEXT NOT NULL,
  closed_at TEXT,
  underlying TEXT NOT NULL,
  option_symbol TEXT NOT NULL,
  option_type TEXT NOT NULL,
  expiry TEXT NOT NULL,
  strike REAL NOT NULL,
  multiplier INTEGER NOT NULL,
  quantity INTEGER NOT NULL,
  entry_price REAL NOT NULL,
  exit_price REAL,
  max_loss_at_entry REAL NOT NULL,
  entry_reason TEXT NOT NULL,
  exit_reason TEXT,
  status TEXT NOT NULL CHECK(status IN ('OPEN','CLOSED')),
  realised_pnl REAL
);
CREATE TABLE IF NOT EXISTS scan_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  occurred_at TEXT NOT NULL,
  event_type TEXT NOT NULL,
  underlying TEXT,
  detail TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS one_open_symbol
ON trades(option_symbol) WHERE status = 'OPEN';
"""


class Ledger:
    def __init__(self, path: str | Path, starting_balance: float):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        count = self.conn.execute("SELECT COUNT(*) FROM account_events").fetchone()[0]
        if count == 0:
            self.conn.execute(
                "INSERT INTO account_events(occurred_at,event_type,amount,note) VALUES(?,?,?,?)",
                (datetime.now(timezone.utc).isoformat(), "DEPOSIT", starting_balance, "Initial paper balance"),
            )
            self.conn.commit()

    def close(self) -> None:
        self.conn.close()

    def cash(self) -> float:
        events = self.conn.execute("SELECT COALESCE(SUM(amount),0) FROM account_events").fetchone()[0]
        purchases = self.conn.execute(
            "SELECT COALESCE(SUM(entry_price*multiplier*quantity),0) FROM trades WHERE status='OPEN'"
        ).fetchone()[0]
        return round(float(events) - float(purchases), 2)

    def realised_pnl(self) -> float:
        return round(float(self.conn.execute("SELECT COALESCE(SUM(realised_pnl),0) FROM trades").fetchone()[0]), 2)

    def equity_for_sizing(self) -> float:
        return round(self.cash() + self.open_cost_basis(), 2)

    def open_cost_basis(self) -> float:
        return round(float(self.conn.execute(
            "SELECT COALESCE(SUM(entry_price*multiplier*quantity),0) FROM trades WHERE status='OPEN'"
        ).fetchone()[0]), 2)

    def open_risk(self) -> float:
        return round(float(self.conn.execute(
            "SELECT COALESCE(SUM(max_loss_at_entry),0) FROM trades WHERE status='OPEN'"
        ).fetchone()[0]), 2)

    def open_count(self) -> int:
        return int(self.conn.execute("SELECT COUNT(*) FROM trades WHERE status='OPEN'").fetchone()[0])

    def has_open_underlying(self, underlying: str) -> bool:
        return bool(self.conn.execute(
            "SELECT 1 FROM trades WHERE status='OPEN' AND underlying=? LIMIT 1", (underlying,)
        ).fetchone())

    def record_scan(self, event_type: str, detail: str, underlying: str | None = None) -> None:
        self.conn.execute(
            "INSERT INTO scan_events(occurred_at,event_type,underlying,detail) VALUES(?,?,?,?)",
            (datetime.now(timezone.utc).isoformat(), event_type, underlying, detail),
        )
        self.conn.commit()

    def open_trade(self, candidate: Candidate) -> int:
        q = candidate.quote
        cursor = self.conn.execute(
            """INSERT INTO trades(
              opened_at,underlying,option_symbol,option_type,expiry,strike,multiplier,
              quantity,entry_price,max_loss_at_entry,entry_reason,status
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,'OPEN')""",
            (
                q.timestamp.isoformat(), q.underlying, q.symbol, q.option_type, q.expiry.isoformat(),
                q.strike, q.multiplier, candidate.quantity, candidate.entry_price,
                candidate.risk_amount, candidate.signal.reason,
            ),
        )
        self.conn.commit()
        return int(cursor.lastrowid)

    def open_trades(self) -> list[sqlite3.Row]:
        return list(self.conn.execute("SELECT * FROM trades WHERE status='OPEN' ORDER BY opened_at"))

    def close_trade(self, trade_id: int, exit_price: float, reason: str, closed_at: datetime) -> float:
        trade = self.conn.execute("SELECT * FROM trades WHERE id=? AND status='OPEN'", (trade_id,)).fetchone()
        if trade is None:
            raise ValueError(f"open trade {trade_id} not found")
        pnl = round((exit_price - trade["entry_price"]) * trade["multiplier"] * trade["quantity"], 2)
        self.conn.execute(
            """UPDATE trades SET closed_at=?,exit_price=?,exit_reason=?,status='CLOSED',realised_pnl=?
               WHERE id=?""",
            (closed_at.isoformat(), exit_price, reason, pnl, trade_id),
        )
        self.conn.execute(
            "INSERT INTO account_events(occurred_at,event_type,amount,note) VALUES(?,?,?,?)",
            (closed_at.isoformat(), "TRADE_CLOSE", pnl,
             f"Close trade {trade_id}: {reason}"),
        )
        self.conn.commit()
        return pnl
