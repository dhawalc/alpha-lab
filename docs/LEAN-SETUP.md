# QuantConnect LEAN CLI Setup (Local Backtesting)

**Date:** 2026-02-18

## Summary
Configured LEAN CLI for **local backtesting only** in `/home/dhawal/alpha-lab`.
We avoid cloud login; all backtests run locally via Docker.

## Python Environment
LEAN CLI currently does **not** support Python 3.14+ due to pydantic v1 compatibility.
A Python 3.12 virtual environment was created for LEAN:

```bash
cd /home/dhawal/alpha-lab
python3.12 -m venv .venv
source .venv/bin/activate
pip install lean
```

Verify:
```bash
source .venv/bin/activate
lean --version
```

## LEAN Configuration (Local)
The CLI `lean init` prompts for QuantConnect cloud credentials. For local-only usage, we created a minimal `lean.json` manually:

`/home/dhawal/alpha-lab/lean.json`
```json
{
    "data-folder": "data",
    "results-destination-folder": "backtests",
    "debugging": false,
    "debugging-method": "LocalCmdLine",
    "log-handler": "QuantConnect.Logging.CompositeLogHandler",
    "messaging-handler": "QuantConnect.Messaging.Messaging",
    "job-queue-handler": "QuantConnect.Queues.JobQueue",
    "api-handler": "QuantConnect.Api.Api",
    "map-file-provider": "QuantConnect.Data.Auxiliary.LocalDiskMapFileProvider",
    "factor-file-provider": "QuantConnect.Data.Auxiliary.LocalDiskFactorFileProvider",
    "data-provider": "QuantConnect.Lean.Engine.DataFeeds.DefaultDataProvider",
    "object-store": "QuantConnect.Lean.Engine.Storage.LocalObjectStore",
    "data-aggregator": "QuantConnect.Lean.Engine.DataFeeds.AggregationManager",
    "algorithm-language": "Python",
    "environment": "backtesting",
    "live-data-url": "",
    "live-results-url": "",
    "log-rolling-max-files": 10,
    "log-rolling-max-size": 52428800,
    "data-feed-workers-count": 8,
    "data-feed-max-work-weight": 200,
    "data-feed-queue-fill-timeout-ms": 2000,
    "algorithm-manager-time-loop-maximum": 60,
    "send-via-api": false,
    "python-additional-paths": [],
    "environments": {
        "backtesting": {
            "live-mode": false,
            "setup-handler": "QuantConnect.Lean.Engine.Setup.ConsoleSetupHandler",
            "result-handler": "QuantConnect.Lean.Engine.Results.BacktestingResultHandler",
            "data-feed-handler": "QuantConnect.Lean.Engine.DataFeeds.FileSystemDataFeed",
            "real-time-handler": "QuantConnect.Lean.Engine.RealTime.BacktestingRealTimeHandler",
            "history-provider": "QuantConnect.Lean.Engine.HistoricalData.SubscriptionDataReaderHistoryProvider",
            "transaction-handler": "QuantConnect.Lean.Engine.TransactionHandlers.BacktestingTransactionHandler"
        }
    }
}
```

## Test Strategy
Created a simple SMA crossover strategy:

```
/home/dhawal/alpha-lab/strategies/test-sma/main.py
/home/dhawal/alpha-lab/strategies/test-sma/config.json
```

To run:
```bash
cd /home/dhawal/alpha-lab
source .venv/bin/activate
lean backtest strategies/test-sma
```

**Note:** The first run pulls the Docker image `quantconnect/lean:latest` (~4GB).

## Data
No paid data subscriptions were configured. Local data folder is:

```
/home/dhawal/alpha-lab/data
```

You can add free sample data using the CLI later if needed:
```bash
lean data download --help
```

## Troubleshooting
- If `lean init` requires cloud login, skip it and use the manual `lean.json` above.
- Ensure Docker is running:
  ```bash
  docker ps
  ```
- Python 3.14+ is not supported by LEAN CLI currently (pydantic v1 issues). Use Python 3.12.
