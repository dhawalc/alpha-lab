# QUANTCONNECT.COM - Democratizing Finance, Empowering Individuals.
# Lean Algorithmic Trading Engine v2.0. Copyright 2014 QuantConnect Corporation.
#
# Simple SMA Crossover Strategy - Test Algorithm

from AlgorithmImports import *

class SMACrossoverAlgorithm(QCAlgorithm):
    """
    Simple Moving Average Crossover Strategy
    - Buy when fast SMA crosses above slow SMA
    - Sell when fast SMA crosses below slow SMA
    """

    def initialize(self) -> None:
        self.set_start_date(2020, 1, 1)
        self.set_end_date(2020, 12, 31)
        self.set_cash(100000)

        # Add SPY as our test asset
        self.symbol = self.add_equity("SPY", Resolution.DAILY).symbol

        # Create indicators
        self.fast_sma = self.sma(self.symbol, 10, Resolution.DAILY)
        self.slow_sma = self.sma(self.symbol, 30, Resolution.DAILY)

        # Track previous state for crossover detection
        self._previous_fast = None
        self._previous_slow = None

        # Warm up indicators
        self.set_warm_up(30, Resolution.DAILY)

    def on_data(self, data: Slice) -> None:
        # Skip if warming up or indicators not ready
        if self.is_warming_up:
            return
        
        if not self.fast_sma.is_ready or not self.slow_sma.is_ready:
            return

        fast_value = self.fast_sma.current.value
        slow_value = self.slow_sma.current.value

        # Detect crossovers
        if self._previous_fast is not None and self._previous_slow is not None:
            # Bullish crossover: fast crosses above slow
            if self._previous_fast <= self._previous_slow and fast_value > slow_value:
                if not self.portfolio.invested:
                    self.set_holdings(self.symbol, 1.0)
                    self.debug(f"BUY: Fast SMA ({fast_value:.2f}) crossed above Slow SMA ({slow_value:.2f})")

            # Bearish crossover: fast crosses below slow
            elif self._previous_fast >= self._previous_slow and fast_value < slow_value:
                if self.portfolio.invested:
                    self.liquidate(self.symbol)
                    self.debug(f"SELL: Fast SMA ({fast_value:.2f}) crossed below Slow SMA ({slow_value:.2f})")

        # Update previous values
        self._previous_fast = fast_value
        self._previous_slow = slow_value

    def on_end_of_algorithm(self) -> None:
        self.log(f"Final Portfolio Value: ${self.portfolio.total_portfolio_value:,.2f}")
