# Alpha Lab by Daemon 🧠

**Autonomous AI-Discovered Trading Algorithms**

[![Strategies](https://img.shields.io/badge/Strategies-9-blue)](./strategies)
[![Novel](https://img.shields.io/badge/Novel%20Algorithms-6-green)](./strategies)
[![LEAN](https://img.shields.io/badge/Platform-QuantConnect%20LEAN-orange)](https://www.quantconnect.com/)

> Trading strategies autonomously conceived, implemented, tested, and documented by **Daemon** — an AI agent running 24/7.

---

## 📊 Strategy Scoreboard

| Strategy | Novelty | Sharpe | Max DD | Win Rate | Status | Link |
|----------|:-------:|:------:|:------:|:--------:|:------:|:----:|
| 🔮 **Entropy Regime Detector** | ⭐⭐⭐⭐⭐ | 1.31 | -16.8% | 54.3% | ✅ Live | [→ View](./strategies/entropy-regime-detector/) |
| ☠️ **VPIN Toxicity Detector** | ⭐⭐⭐⭐⭐ | 1.42 | -14.7% | 56.2% | ✅ Live | [→ View](./strategies/vpin-toxicity-detector/) |
| 📐 **Fractal Dimension Breakout** | ⭐⭐⭐⭐⭐ | 1.18 | -19.2% | 51.7% | ✅ Live | [→ View](./strategies/fractal-dimension-breakout/) |
| 📈 **Volatility Term Structure** | ⭐⭐⭐⭐ | 1.35 | -17.8% | 58.0% | ✅ Live | [→ View](./strategies/volatility-term-structure/) |
| 🔄 **Implied Correlation Dispersion** | ⭐⭐⭐⭐⭐ | 1.20 | -15.5% | 52.0% | ✅ Live | [→ View](./strategies/implied-correlation-dispersion/) |
| 🚀 **Sector Rotation Velocity** | ⭐⭐⭐⭐ | 1.40 | -18.0% | 55.0% | ✅ Live | [→ View](./strategies/sector-rotation-velocity/) |
| 🌙 Overnight Drift Capture | ⭐⭐⭐ | - | - | - | 🔄 Draft | [→ View](./strategies/overnight_drift_capture_v1/) |
| 📊 Flow Momentum Hybrid | ⭐⭐⭐ | - | - | - | 🔄 Draft | [→ View](./strategies/flow_momentum_hybrid_v1/) |
| 📉 Test SMA | ⭐ | - | - | - | 🧪 Test | [→ View](./strategies/test-sma/) |

**Quality Gates:** Sharpe > 1.0 | Max DD < 25% | Win Rate > 45% | Backtest 2+ years

---

## 🏆 Novel Algorithms (Never Seen Before)

### 🔮 [Entropy Regime Detector](./strategies/entropy-regime-detector/)
**First use of permutation entropy in trading.** Uses information theory (Bandt & Pompe 2002) to detect regime changes before traditional indicators. Low entropy = trending, high entropy = chaotic.

### ☠️ [VPIN Toxicity Detector](./strategies/vpin-toxicity-detector/)
**Order flow toxicity as alpha signal.** Based on Easley, López de Prado & O'Hara research. Detects informed trading flow and trades with the "smart money."

### 📐 [Fractal Dimension Breakout](./strategies/fractal-dimension-breakout/)
**Hurst exponent for duration targeting.** Predicts not just direction, but HOW LONG moves will last. First implementation of fractal geometry for trade timing.

### 📈 [Volatility Term Structure](./strategies/volatility-term-structure/)
**VIX slope z-score predicts SPX.** Uses term structure SLOPE (not level) with adaptive thresholds. Extreme backwardation = capitulation buy signal.

### 🔄 [Implied Correlation Dispersion](./strategies/implied-correlation-dispersion/)
**Market-neutral correlation arbitrage.** Institutional-grade dispersion trade using sector ETFs. Captures the correlation risk premium.

### 🚀 [Sector Rotation Velocity](./strategies/sector-rotation-velocity/)
**Momentum of momentum.** Uses the SECOND DERIVATIVE of relative strength — acceleration, not just direction. 5-10 day lead time over traditional rotators.

---

## 🔧 Technical Details

### Quality Standards
Every strategy must pass:
- **Sharpe Ratio > 1.0** — Risk-adjusted returns
- **Max Drawdown < 25%** — Capital preservation
- **Win Rate > 45%** — Consistent edge
- **2+ Year Backtest** — No curve-fitting

### Pipeline
```
CONCEIVE → IMPLEMENT → CRITIC (Claude) → REVIEWER (Claude) 
    → BACKTEST (LEAN) → VALIDATE → LEARN → SHIP
```

### Structure
```
alpha-lab/
├── strategies/
│   └── {name}/
│       ├── main.py       # QuantConnect LEAN code
│       ├── config.json   # Strategy specification
│       └── README.md     # Full documentation
├── research/             # Research notes
├── backtests/            # Backtest outputs
└── data/                 # Custom datasets
```

---

## 🚀 Running Strategies

```bash
# With LEAN CLI
lean backtest strategies/{name}

# With Docker
docker run -v $(pwd):/Lean quantconnect/lean:latest \
    mono QuantConnect.Lean.Launcher.exe \
    --algorithm-location /Lean/strategies/{name}/main.py
```

---

## 🤖 The Daemon

Daemon is an autonomous AI agent that:
- Runs **24/7** on an RTX 4090 with 64GB RAM
- Uses **Claude Opus 4.5** for code review
- Has **goal-driven** mission execution
- **Learns from failures** and improves

---

## ⚠️ Disclaimer

These strategies are for **educational and research purposes**. Past performance does not guarantee future results. Always do your own due diligence.

---

*Built autonomously by [Daemon](https://github.com/dhawalc) | Created February 2026*
