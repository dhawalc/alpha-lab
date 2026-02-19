# Alpha Lab 🧪

Quantitative trading research and strategy development.

## Focus

- **SPX 0DTE Options** — Primary focus
- **Signal Generation** — Pattern recognition, ML models, technical indicators
- **Backtesting Infrastructure** — Validation pipeline with multiple data sources
- **Live Integration** — D2DT bridge for real-time signal deployment

## Architecture

```
alpha-lab/
├── strategies/          # Trading strategies (Pine Script, Python)
├── backtests/           # Backtest results and analysis
├── data/                # Historical data, cached datasets
├── signals/             # Signal generation modules
├── d2dt-bridge/         # Integration with D2DT trading system
└── research/            # Exploratory analysis, notebooks
```

## Data Sources

- **TradingView** — Screener, alerts, charting (Premium Plus)
- **QuantConnect** — Backtesting validation, historical options data
- **IBKR** — Live data, execution

## Related

- [Immortal Architecture](../daemon/docs/research/2026-02-14-immortal-architecture-opus.md) — D2DT system design
- [Daemon Evolution Journal](https://github.com/dhawalc/daemon-evolution-journal)

---

*Part of the autonomous trading infrastructure*
