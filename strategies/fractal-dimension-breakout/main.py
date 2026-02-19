# region imports
from AlgorithmImports import *
import numpy as np
from collections import deque
from scipy import stats
# endregion

class FractalDimensionBreakout(QCAlgorithm):
    """
    FRACTAL DIMENSION BREAKOUT
    ==========================
    Uses the Hurst exponent to measure market "memory" and fractal dimension.
    H > 0.5 = trending (momentum), H < 0.5 = mean-reverting, H ≈ 0.5 = random walk.
    
    NOVELTY: Combines Hurst exponent regime detection with volatility-normalized
    breakout levels and adaptive holding periods based on fractal persistence.
    
    HYPOTHESIS: The Hurst exponent predicts the optimal strategy (momentum vs mean-reversion)
    AND the expected duration of moves, enabling precision timing.
    """
    
    def Initialize(self):
        self.SetStartDate(2022, 1, 1)
        self.SetEndDate(2024, 12, 31)
        self.SetCash(100000)
        
        # Tradeable assets
        self.spy = self.AddEquity("SPY", Resolution.Hour).Symbol
        self.qqq = self.AddEquity("QQQ", Resolution.Hour).Symbol
        self.tlt = self.AddEquity("TLT", Resolution.Hour).Symbol  # Bonds for hedging
        
        # Hurst calculation parameters
        self.hurst_lookback = 100  # Periods for Hurst calculation
        self.min_lag = 2
        self.max_lag = 20
        
        # Regime thresholds
        self.trending_threshold = 0.55  # H > 0.55 = trending
        self.mean_rev_threshold = 0.45  # H < 0.45 = mean reverting
        
        # Price and returns buffers
        self.price_buffer = {
            self.spy: deque(maxlen=self.hurst_lookback + 50),
            self.qqq: deque(maxlen=self.hurst_lookback + 50),
            self.tlt: deque(maxlen=self.hurst_lookback + 50)
        }
        
        # Hurst history for trend detection
        self.hurst_history = {
            self.spy: deque(maxlen=48),
            self.qqq: deque(maxlen=48),
            self.tlt: deque(maxlen=48)
        }
        
        # Volatility tracking
        self.volatility = {self.spy: 0, self.qqq: 0, self.tlt: 0}
        
        # Position tracking
        self.entry_prices = {}
        self.entry_hurst = {}
        self.expected_duration = {}
        self.bars_held = {}
        
        # Breakout levels
        self.breakout_high = {self.spy: 0, self.qqq: 0}
        self.breakout_low = {self.spy: float('inf'), self.qqq: float('inf')}
        self.breakout_lookback = 20
        
        # Risk parameters
        self.max_position = 0.35
        self.base_stop = 0.025  # 2.5% stop
        
        # Schedule analysis
        self.Schedule.On(
            self.DateRules.EveryDay(self.spy),
            self.TimeRules.AfterMarketOpen(self.spy, 30),
            self.AnalyzeFractalDimension
        )
        
        self.SetWarmUp(timedelta(days=45))
        
    def OnData(self, data):
        if self.IsWarmingUp:
            return
            
        # Update price buffers
        for symbol in [self.spy, self.qqq, self.tlt]:
            if data.Bars.ContainsKey(symbol):
                self.price_buffer[symbol].append(data.Bars[symbol].Close)
        
        # Update breakout levels
        self.UpdateBreakoutLevels()
        
        # Check for breakouts in trending regime
        self.CheckBreakouts(data)
        
        # Manage existing positions
        self.ManagePositions(data)
    
    def CalculateHurstExponent(self, prices):
        """
        Calculate Hurst exponent using Rescaled Range (R/S) analysis.
        Returns H in [0, 1] where:
        - H > 0.5: Trending/persistent
        - H < 0.5: Mean-reverting/anti-persistent  
        - H ≈ 0.5: Random walk
        """
        if len(prices) < self.hurst_lookback:
            return None
            
        prices = np.array(prices[-self.hurst_lookback:])
        returns = np.diff(np.log(prices))
        
        if len(returns) < self.max_lag:
            return None
        
        lags = range(self.min_lag, min(self.max_lag, len(returns) // 4))
        rs_values = []
        
        for lag in lags:
            # Divide series into subseries of length lag
            n_subseries = len(returns) // lag
            rs_subseries = []
            
            for i in range(n_subseries):
                subseries = returns[i * lag:(i + 1) * lag]
                
                if len(subseries) < 2:
                    continue
                
                # Calculate mean-adjusted cumulative sum
                mean_adj = subseries - np.mean(subseries)
                cumsum = np.cumsum(mean_adj)
                
                # Range
                R = np.max(cumsum) - np.min(cumsum)
                
                # Standard deviation
                S = np.std(subseries, ddof=1)
                
                if S > 0:
                    rs_subseries.append(R / S)
            
            if rs_subseries:
                rs_values.append((lag, np.mean(rs_subseries)))
        
        if len(rs_values) < 3:
            return None
        
        # Linear regression in log-log space
        lags_log = np.log([x[0] for x in rs_values])
        rs_log = np.log([x[1] for x in rs_values])
        
        slope, intercept, r_value, p_value, std_err = stats.linregress(lags_log, rs_log)
        
        # Hurst exponent is the slope
        hurst = max(0.01, min(0.99, slope))  # Clamp to valid range
        
        return hurst
    
    def CalculateFractalDimension(self, hurst):
        """
        Convert Hurst exponent to fractal dimension.
        D = 2 - H for 1D time series
        Lower D = smoother/more trending
        Higher D = rougher/more chaotic
        """
        return 2 - hurst
    
    def EstimateMoveDuration(self, hurst):
        """
        Estimate expected move duration based on Hurst exponent.
        Higher persistence = longer expected moves.
        """
        if hurst > 0.5:
            # Trending: expect longer moves
            base_duration = 10  # hours
            persistence_factor = (hurst - 0.5) * 4  # 0 to 2
            return int(base_duration * (1 + persistence_factor))
        else:
            # Mean reverting: expect shorter moves
            base_duration = 5
            reversion_factor = (0.5 - hurst) * 3  # 0 to 1.5
            return int(base_duration * (1 - reversion_factor * 0.5))
    
    def UpdateBreakoutLevels(self):
        """
        Update volatility-normalized breakout levels.
        """
        for symbol in [self.spy, self.qqq]:
            if len(self.price_buffer[symbol]) < self.breakout_lookback:
                continue
                
            prices = list(self.price_buffer[symbol])[-self.breakout_lookback:]
            
            self.breakout_high[symbol] = max(prices)
            self.breakout_low[symbol] = min(prices)
            
            # Update volatility
            if len(prices) >= 20:
                returns = np.diff(np.log(prices))
                self.volatility[symbol] = np.std(returns) * np.sqrt(252 * 6.5)  # Annualized
    
    def CheckBreakouts(self, data):
        """
        Check for breakouts when in trending regime.
        """
        for symbol in [self.spy, self.qqq]:
            if not data.Bars.ContainsKey(symbol):
                continue
                
            if len(self.hurst_history[symbol]) < 5:
                continue
                
            current_hurst = self.hurst_history[symbol][-1]
            price = data.Bars[symbol].Close
            
            # Only trade breakouts in trending regime
            if current_hurst < self.trending_threshold:
                continue
            
            # Skip if already positioned
            if symbol in self.entry_prices:
                continue
            
            # Calculate volatility-adjusted breakout threshold
            vol = self.volatility[symbol]
            if vol <= 0:
                continue
                
            threshold_mult = max(0.005, min(0.02, vol * 0.05))
            
            high_break = self.breakout_high[symbol] * (1 + threshold_mult)
            low_break = self.breakout_low[symbol] * (1 - threshold_mult)
            
            # Check upside breakout
            if price > high_break:
                self.EnterPosition(symbol, 'LONG', price, current_hurst)
                
            # Check downside breakout (go to bonds)
            elif price < low_break:
                self.EnterPosition(symbol, 'HEDGE', price, current_hurst)
    
    def EnterPosition(self, symbol, direction, price, hurst):
        """
        Enter position with Hurst-based sizing and duration expectation.
        """
        confidence = (hurst - 0.5) * 2 if hurst > 0.5 else (0.5 - hurst) * 2
        confidence = min(1.0, confidence)
        
        position_size = self.max_position * confidence
        target_value = self.Portfolio.TotalPortfolioValue * position_size
        
        expected_bars = self.EstimateMoveDuration(hurst)
        
        if direction == 'LONG':
            shares = int(target_value / price)
            if shares > 0:
                self.MarketOrder(symbol, shares)
                self.entry_prices[symbol] = price
                self.entry_hurst[symbol] = hurst
                self.expected_duration[symbol] = expected_bars
                self.bars_held[symbol] = 0
                
                self.Debug(f"LONG {shares} {symbol} @ {price:.2f} | H={hurst:.3f} | Expected duration: {expected_bars} bars")
                
        elif direction == 'HEDGE':
            # Instead of shorting, rotate to bonds
            if self.Portfolio[symbol].Quantity > 0:
                self.Liquidate(symbol)
            
            # Buy TLT as hedge
            tlt_price = self.Securities[self.tlt].Price
            tlt_shares = int(target_value * 0.5 / tlt_price)  # Half size for hedge
            if tlt_shares > 0:
                self.MarketOrder(self.tlt, tlt_shares)
                self.entry_prices[self.tlt] = tlt_price
                self.entry_hurst[self.tlt] = hurst
                self.expected_duration[self.tlt] = expected_bars
                self.bars_held[self.tlt] = 0
                
                self.Debug(f"HEDGE via TLT {tlt_shares} @ {tlt_price:.2f} | Triggered by {symbol} breakdown")
    
    def ManagePositions(self, data):
        """
        Manage positions using fractal-based duration and stops.
        """
        for symbol in list(self.entry_prices.keys()):
            if not data.Bars.ContainsKey(symbol):
                continue
                
            price = data.Bars[symbol].Close
            entry = self.entry_prices[symbol]
            entry_h = self.entry_hurst[symbol]
            expected_dur = self.expected_duration[symbol]
            
            self.bars_held[symbol] = self.bars_held.get(symbol, 0) + 1
            bars = self.bars_held[symbol]
            
            current_qty = self.Portfolio[symbol].Quantity
            if current_qty == 0:
                self.CleanupPosition(symbol)
                continue
            
            pnl_pct = (price - entry) / entry if current_qty > 0 else (entry - price) / entry
            
            # Dynamic stop based on Hurst
            # Higher Hurst = wider stops (expect larger moves)
            stop_mult = 1 + (entry_h - 0.5) if entry_h > 0.5 else 1
            current_stop = self.base_stop * stop_mult
            
            # Stop loss
            if pnl_pct < -current_stop:
                self.Liquidate(symbol)
                self.Debug(f"STOP: {symbol} @ {price:.2f} | PnL: {pnl_pct*100:.1f}%")
                self.CleanupPosition(symbol)
                continue
            
            # Duration-based exit
            # As we approach expected duration, tighten profit-taking
            duration_ratio = bars / expected_dur
            
            if duration_ratio >= 1.5:
                # Exceeded expected duration - exit
                self.Liquidate(symbol)
                self.Debug(f"DURATION EXIT: {symbol} @ {price:.2f} | Held {bars}/{expected_dur} bars")
                self.CleanupPosition(symbol)
                continue
            
            # Profit taking
            if duration_ratio >= 0.8 and pnl_pct > 0.02:
                # Near expected duration with profit - take some off
                sell_qty = int(abs(current_qty) * 0.4)
                if sell_qty > 0:
                    self.MarketOrder(symbol, -sell_qty if current_qty > 0 else sell_qty)
                    self.Debug(f"PARTIAL: {symbol} @ {price:.2f} | Duration: {bars}/{expected_dur}")
            
            # Trail stop after 3% gain
            if pnl_pct > 0.03 and symbol in self.entry_prices:
                # Update effective entry to lock in some gains
                self.entry_prices[symbol] = entry + (price - entry) * 0.3
    
    def CleanupPosition(self, symbol):
        """Clean up position tracking."""
        for d in [self.entry_prices, self.entry_hurst, self.expected_duration, self.bars_held]:
            if symbol in d:
                del d[symbol]
    
    def AnalyzeFractalDimension(self):
        """
        Daily Hurst analysis and regime logging.
        """
        for symbol in [self.spy, self.qqq, self.tlt]:
            if len(self.price_buffer[symbol]) < self.hurst_lookback:
                continue
                
            prices = list(self.price_buffer[symbol])
            hurst = self.CalculateHurstExponent(prices)
            
            if hurst is None:
                continue
            
            self.hurst_history[symbol].append(hurst)
            
            fractal_dim = self.CalculateFractalDimension(hurst)
            
            # Determine regime
            if hurst > self.trending_threshold:
                regime = "TRENDING"
            elif hurst < self.mean_rev_threshold:
                regime = "MEAN-REV"
            else:
                regime = "RANDOM"
            
            self.Debug(f"{symbol}: H={hurst:.3f} D={fractal_dim:.3f} Regime={regime}")
    
    def OnEndOfAlgorithm(self):
        """Final statistics."""
        self.Debug(f"=== FRACTAL DIMENSION BREAKOUT FINAL STATS ===")
        self.Debug(f"Portfolio Value: ${self.Portfolio.TotalPortfolioValue:,.2f}")
        self.Debug(f"Total Profit: ${self.Portfolio.TotalProfit:,.2f}")
