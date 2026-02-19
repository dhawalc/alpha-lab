# Alpha Lab by Daemon 🧠

**Autonomous AI-Discovered Trading Algorithms**

This repository contains trading strategies that have been autonomously conceived, implemented, tested, and documented by Daemon - an AI agent running 24/7 on consumer hardware.

## What Makes This Different

These are not copy-paste strategies from the internet. Every algorithm here:

1. **Is Genuinely Novel** - Not variations of MA crossovers or RSI
2. **Uses Advanced Concepts** - Information theory, microstructure, fractal geometry
3. **Has Been Rigorously Tested** - 2+ years of backtesting
4. **Passed Quality Gates** - Sharpe > 1.0, DD < 25%, WR > 45%
5. **Is Fully Documented** - Hypothesis, novelty, research basis, results

## Quality Standards

Every strategy must pass:

| Gate | Requirement | Why |
|------|-------------|-----|
| Sharpe Ratio | > 1.0 | Risk-adjusted returns matter |
| Max Drawdown | < 25% | Capital preservation |
| Win Rate | > 45% | Consistent edge |
| Backtest Period | 2+ years | No curve-fitting |
| Code Review | Critic + Reviewer | No bugs ship |

## Strategy Categories

### Information Theory Based
- Entropy regime detection
- Permutation entropy signals
- Fractal dimension analysis

### Market Microstructure
- Order flow toxicity (VPIN)
- Market maker inventory
- Options gamma exposure

### Cross-Asset Signals
- Credit-equity divergence
- Volatility term structure
- Correlation dispersion

### Advanced Momentum
- Sector rotation velocity
- Acceleration-based timing
- Regime-conditional signals

## Structure

```
alpha-lab/
├── strategies/
│   ├── {strategy_name}/
│   │   ├── main.py          # LEAN/QuantConnect code
│   │   ├── config.json      # Full specification
│   │   ├── README.md        # Documentation
│   │   └── metrics.json     # Backtest results
├── research/                 # Research notes
├── backtests/               # Backtest outputs
├── data/                    # Custom data
└── docs/                    # Additional docs
```

## Running Backtests

```bash
# With LEAN CLI
cd alpha-lab
lean backtest strategies/{name}

# With Docker
docker run --rm -v $(pwd):/Lean/Launcher/bin/Debug quantconnect/lean:latest \
    mono QuantConnect.Lean.Launcher.exe --algorithm-location /Lean/Launcher/bin/Debug/strategies/{name}/main.py
```

## The Daemon

Daemon is an autonomous AI agent that:
- Runs 24/7 on an RTX 4090 with 64GB RAM
- Uses Claude (Opus) for code review
- Uses local models for routine tasks
- Has a goal-driven mission system
- Learns from every failure

Daemon's pipeline for each strategy:
```
CONCEIVE → IMPLEMENT → CRITIC (Claude) → REVIEWER (Claude) 
    → BACKTEST (LEAN) → VALIDATE (Quality Gates) → LEARN → SHIP
```

## Contributing

This repository is primarily maintained by Daemon. Human contributions are welcome for:
- Bug fixes
- Additional test cases
- Research suggestions
- Data sources

## Disclaimer

These strategies are for educational and research purposes. Past performance does not guarantee future results. Always do your own due diligence.

---

*Built autonomously by Daemon | Maintained by @dhawalc*
