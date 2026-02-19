# LEAN CLI Setup - alpha-lab

## Installation

```bash
cd /home/dhawal/alpha-lab
source .venv/bin/activate
lean --version  # 1.0.223
```

## Configuration

Local-only setup (no QuantConnect cloud login required for backtesting):
- `lean.json` - LEAN engine configuration
- Data folder: `./data`
- Results: `./backtests`

## Running Backtests

```bash
cd /home/dhawal/alpha-lab
source .venv/bin/activate

# Run a backtest
lean backtest strategies/basic_sma.py

# With custom dates
lean backtest strategies/basic_sma.py --start 2023-01-01 --end 2023-12-31
```

## Data

For SPX options backtesting, you'll need:
1. **AlgoSeek SPX Options data** - requires QuantConnect subscription
2. Or **local data** in LEAN format under `./data/`

## Sample Strategies

- `strategies/basic_sma.py` - Simple SMA crossover (test strategy)

## Next Steps

1. [ ] Subscribe to AlgoSeek SPX Options data (QuantConnect)
2. [ ] Download historical data for backtesting
3. [ ] Create SPX 0DTE strategy templates
4. [ ] Integrate with D2DT signal pipeline

---

Created: 2026-02-18
