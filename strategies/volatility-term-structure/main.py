# region imports
from AlgorithmImports import *
import numpy as np
from collections import deque
from datetime import timedelta
# endregion

class VolatilityTermStructureArbitrage(QCAlgorithm):
    """
    EXOTIC ALPHA: Volatility Term Structure Arbitrage
    
    Hypothesis:
    -----------
    VIX futures term structure (contango/backwardation) contains predictive 
    information about future SPX returns. Extreme backwardation signals panic
    capitulation and subsequent mean reversion upward. Contango steepness
    signals complacency and vulnerability to downside.
    
    Key Insight:
    ------------
    The VIX term structure slope is essentially the market's "fear schedule."
    When near-term fear dramatically exceeds long-term fear (backwardation),
    it indicates acute panic that typically resolves quickly. When long-term
    fear exceeds near-term (steep contango), it signals complacency.
    
    Signal Generation:
    -----------------
    1. Calculate VIX term structure slope (VIX9D vs VIX3M proxy)
    2. Compute z-score of slope relative to rolling history
    3. Extreme backwardation (z < -2) = Strong buy signal
    4. Extreme contango (z > 2) = Reduce exposure / hedge
    5. Position sizing inversely proportional to VIX level
    
    Novelty:
    --------
    - Uses VIX term structure SLOPE, not just VIX level
    - Z-score normalization for regime-adaptive thresholds
    - Dynamic position sizing based on volatility regime
    - Combines mean reversion AND momentum components
    """
    
    def Initialize(self):
        self.SetStartDate(2022, 1, 1)
        self.SetEndDate(2024, 12, 31)
        self.SetCash(100000)
        
        # Primary trading instrument
        self.spy = self.AddEquity("SPY", Resolution.Hour).Symbol
        
        # Volatility proxies (VIX ETFs as term structure proxies)
        self.vxx = self.AddEquity("VXX", Resolution.Hour).Symbol  # Short-term VIX
        self.vixm = self.AddEquity("VIXM", Resolution.Hour).Symbol  # Mid-term VIX
        
        # Alternative: Use UVXY/SVXY for leverage
        self.uvxy = self.AddEquity("UVXY", Resolution.Hour).Symbol
        
        # Term structure tracking
        self.term_structure_history = deque(maxlen=252)  # 1 year of daily data
        self.vxx_prices = deque(maxlen=60)
        self.vixm_prices = deque(maxlen=60)
        
        # Signal parameters
        self.lookback_days = 60
        self.zscore_buy_threshold = -1.5  # Extreme backwardation
        self.zscore_sell_threshold = 1.5  # Extreme contango
        self.zscore_extreme_buy = -2.5    # Capitulation signal
        
        # Position management
        self.base_position_size = 0.6
        self.max_position_size = 0.95
        self.min_position_size = 0.1
        
        # Risk management
        self.max_drawdown = 0.15
        self.trailing_stop_pct = 0.08
        self.entry_price = None
        self.peak_value = self.Portfolio.TotalPortfolioValue
        
        # State tracking
        self.last_term_structure_slope = None
        self.current_regime = "NEUTRAL"
        self.days_in_position = 0
        
        # Schedule daily analysis
        self.Schedule.On(
            self.DateRules.EveryDay("SPY"),
            self.TimeRules.AfterMarketOpen("SPY", 30),
            self.AnalyzeTermStructure
        )
        
        # Rebalance check
        self.Schedule.On(
            self.DateRules.EveryDay("SPY"),
            self.TimeRules.AfterMarketOpen("SPY", 60),
            self.ExecuteSignals
        )
        
        # Performance tracking
        self.trades = []
        self.daily_returns = []
        
        self.SetWarmUp(60, Resolution.Daily)
        
    def OnData(self, data: Slice):
        """Collect price data for term structure calculation."""
        if self.IsWarmingUp:
            return
            
        # Update price histories
        if data.ContainsKey(self.vxx) and data[self.vxx] is not None:
            self.vxx_prices.append(data[self.vxx].Close)
            
        if data.ContainsKey(self.vixm) and data[self.vixm] is not None:
            self.vixm_prices.append(data[self.vixm].Close)
            
        # Track portfolio drawdown
        current_value = self.Portfolio.TotalPortfolioValue
        self.peak_value = max(self.peak_value, current_value)
        drawdown = (self.peak_value - current_value) / self.peak_value
        
        # Emergency risk management
        if drawdown > self.max_drawdown:
            self.Liquidate()
            self.current_regime = "RISK_OFF"
            self.Debug(f"MAX DRAWDOWN TRIGGERED: {drawdown:.2%}")
            
    def AnalyzeTermStructure(self):
        """Calculate VIX term structure slope and generate signals."""
        if len(self.vxx_prices) < 20 or len(self.vixm_prices) < 20:
            return
            
        # Calculate term structure slope
        # VXX/VIXM ratio: > 1 = backwardation (fear), < 1 = contango (complacent)
        vxx_current = list(self.vxx_prices)[-1]
        vixm_current = list(self.vixm_prices)[-1]
        
        if vixm_current <= 0:
            return
            
        # Term structure slope (normalized)
        slope = (vxx_current / vixm_current) - 1  # 0 = flat, + = backwardation, - = contango
        
        # Store for z-score calculation
        self.term_structure_history.append(slope)
        self.last_term_structure_slope = slope
        
        if len(self.term_structure_history) < 60:
            return
            
        # Calculate z-score of current slope
        slopes = np.array(list(self.term_structure_history))
        mean_slope = np.mean(slopes)
        std_slope = np.std(slopes)
        
        if std_slope < 0.001:
            return
            
        zscore = (slope - mean_slope) / std_slope
        
        # Determine regime
        old_regime = self.current_regime
        
        if zscore < self.zscore_extreme_buy:
            self.current_regime = "EXTREME_BACKWARDATION"  # Capitulation buy
        elif zscore < self.zscore_buy_threshold:
            self.current_regime = "BACKWARDATION"  # Fear elevated
        elif zscore > self.zscore_sell_threshold:
            self.current_regime = "STEEP_CONTANGO"  # Complacency
        else:
            self.current_regime = "NEUTRAL"
            
        if old_regime != self.current_regime:
            self.Debug(f"REGIME CHANGE: {old_regime} -> {self.current_regime} | Z-Score: {zscore:.2f}")
            
    def ExecuteSignals(self):
        """Execute trades based on term structure regime."""
        if self.IsWarmingUp:
            return
            
        if not self.Securities[self.spy].Price:
            return
            
        current_holdings = self.Portfolio[self.spy].Quantity
        spy_price = self.Securities[self.spy].Price
        
        # Calculate target position based on regime
        target_weight = 0.0
        
        if self.current_regime == "EXTREME_BACKWARDATION":
            # Maximum conviction buy - capitulation detected
            target_weight = self.max_position_size
            self.Debug("CAPITULATION BUY SIGNAL - Max position")
            
        elif self.current_regime == "BACKWARDATION":
            # Elevated buy signal - fear premium
            target_weight = self.base_position_size + 0.2
            
        elif self.current_regime == "STEEP_CONTANGO":
            # Reduce exposure - complacency risk
            target_weight = self.min_position_size
            
        elif self.current_regime == "NEUTRAL":
            # Normal allocation
            target_weight = self.base_position_size
            
        elif self.current_regime == "RISK_OFF":
            target_weight = 0.0
            
        # Volatility-adjusted position sizing
        if len(self.vxx_prices) >= 5:
            recent_vxx = np.mean(list(self.vxx_prices)[-5:])
            vxx_baseline = 20  # Typical VXX level
            vol_scalar = min(vxx_baseline / max(recent_vxx, 10), 1.5)
            target_weight *= vol_scalar
            
        target_weight = max(0, min(target_weight, self.max_position_size))
        
        # Calculate current weight
        current_weight = (current_holdings * spy_price) / self.Portfolio.TotalPortfolioValue
        
        # Only trade if significant deviation
        if abs(target_weight - current_weight) > 0.05:
            self.SetHoldings(self.spy, target_weight)
            
            if target_weight > current_weight:
                self.trades.append({
                    "time": self.Time,
                    "action": "BUY",
                    "weight": target_weight,
                    "regime": self.current_regime
                })
            else:
                self.trades.append({
                    "time": self.Time,
                    "action": "REDUCE",
                    "weight": target_weight,
                    "regime": self.current_regime
                })
                
    def OnEndOfAlgorithm(self):
        """Report final statistics."""
        self.Debug(f"=== VOLATILITY TERM STRUCTURE ARBITRAGE RESULTS ===")
        self.Debug(f"Total Trades: {len(self.trades)}")
        self.Debug(f"Final Portfolio Value: ${self.Portfolio.TotalPortfolioValue:,.2f}")
        self.Debug(f"Total Return: {((self.Portfolio.TotalPortfolioValue - 100000) / 100000) * 100:.2f}%")
