from __future__ import annotations

import argparse
import json
from pathlib import Path

from .config import load_config
from .engine import run_scan
from .ledger import Ledger
from .provider import read_option_quotes, read_price_history


def _ledger(config_path: str, config: dict) -> Ledger:
    ledger_path = Path(config["storage"]["ledger_path"])
    if not ledger_path.is_absolute():
        ledger_path = Path(config_path).resolve().parent / ledger_path
    return Ledger(ledger_path, float(config["account"]["starting_balance"]))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="ASX options paper trader")
    parser.add_argument("command", choices=["init", "scan", "report"])
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--quotes")
    parser.add_argument("--history")
    args = parser.parse_args(argv)
    config = load_config(args.config)
    ledger = _ledger(args.config, config)
    try:
        if args.command == "init":
            print(json.dumps({"status": "initialised", "cash": ledger.cash()}, indent=2))
        elif args.command == "report":
            print(json.dumps({
                "cash": ledger.cash(),
                "equity_at_cost": ledger.equity_for_sizing(),
                "realised_pnl": ledger.realised_pnl(),
                "open_positions": ledger.open_count(),
                "open_risk": ledger.open_risk(),
            }, indent=2))
        else:
            if not args.quotes or not args.history:
                parser.error("scan requires --quotes and --history")
            messages = run_scan(ledger, read_option_quotes(args.quotes), read_price_history(args.history), config)
            print("\n".join(messages) if messages else "NO ACTION")
    finally:
        ledger.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
