# Basic SMA Crossover Strategy - Test
# QuantConnect LEAN Algorithm

from AlgorithmImports import *

class BasicSMACrossover(QCAlgorithm):
    """Simple SMA crossover to verify LEAN is working."""
    
    def initialize(self):
        self.set_start_date(2023, 1, 1)
        self.set_end_date(2023, 12, 31)
        self.set_cash(100000)
        
        # Add SPY
        self.spy = self.add_equity("SPY", Resolution.DAILY).symbol
        
        # Create indicators
        self.fast_sma = self.sma(self.spy, 10, Resolution.DAILY)
        self.slow_sma = self.sma(self.spy, 30, Resolution.DAILY)
        
        # Warm up
        self.set_warm_up(30)
        
    def on_data(self, data):
        if self.is_warming_up:
            return
            
        if not self.fast_sma.is_ready or not self.slow_sma.is_ready:
            return
        
        holdings = self.portfolio[self.spy].quantity
        
        # Buy signal: fast crosses above slow
        if self.fast_sma.current.value > self.slow_sma.current.value:
            if holdings <= 0:
                self.set_holdings(self.spy, 1.0)
        # Sell signal: fast crosses below slow
        elif self.fast_sma.current.value < self.slow_sma.current.value:
            if holdings > 0:
                self.liquidate(self.spy)
