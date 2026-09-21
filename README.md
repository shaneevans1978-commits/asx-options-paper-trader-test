# ASX Options Paper Trader

Paper-only prototype for scanning ASX 20 option opportunities, applying strict
risk controls, and recording every decision in a durable SQLite ledger.

## Locked settings

- Starting paper balance: AUD 10,000
- Maximum loss at entry: 2% of current equity per trade
- Universe: S&P/ASX 20 shares configured in `config.json`
- Long calls and long puts only (defined risk; no option writing)
- No broker connection and no live orders
- Scanner cadence: hourly during the configured Australian market window

The engine refuses a trade when one contract's premium exceeds the 2% risk
budget. It never rounds position size up.

## Automated daily watchlist

The free automated mode runs after the ASX close and uses Alpha Vantage daily
share prices to produce CALL/PUT **signals** for the configured ASX 20
universe. It does not select an option contract or open a paper trade because a
licensed ASX options-chain feed is not connected.

Set `ALPHA_VANTAGE_API_KEY` in the environment, then run:

```bash
python -m asx_paper_trader.cli watchlist --config config.json
```

The command writes `reports/daily_watchlist.json` and
`reports/daily_watchlist.csv`.

## Run locally

Python 3.11+ is sufficient; the runtime has no third-party dependencies.

```bash
python -m asx_paper_trader.cli init --config config.json
python -m asx_paper_trader.cli scan --config config.json \
  --quotes data/sample_option_chain.csv \
  --history data/sample_underlying_history.csv
python -m asx_paper_trader.cli report --config config.json
```

Set `PYTHONPATH=src` if the package has not been installed, or run
`python -m pip install -e .` once.

## Data-provider boundary

The prototype deliberately reads a normalized CSV instead of scraping a web
page. ASX publishes option contract details and price pages, but the public
pages do not constitute a stable, documented free automation API. Live or
delayed data can be wired in later without changing the strategy, risk, or
ledger code by producing these columns:

`timestamp,underlying,symbol,expiry,option_type,strike,bid,ask,last,volume,open_interest,underlying_price,delta,multiplier`

`delta` may be blank; the first production adapter can calculate it if implied
volatility is available. The sample is intentionally illustrative, not a claim
about current market prices.

## Automation

`.github/workflows/hourly-scan.yml` runs the signal watchlist once each weekday
after the ASX close. Add the repository Actions secret
`ALPHA_VANTAGE_API_KEY`; each run stores CSV and JSON reports as a private
workflow artifact for 90 days. The separate options paper-trading scan remains
available for a future licensed options feed.

## Important

This is research and paper-trading software, not financial advice. The current
CSV feed is a safe integration seam, not a live data service. Do not enable
live execution until market-data licensing, corporate actions, contract
multipliers, fees, slippage, exercise/assignment, and broker API behaviour have
all been validated.
