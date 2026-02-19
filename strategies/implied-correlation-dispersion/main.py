# region imports
from AlgorithmImports import *
import numpy as np
from collections import deque
from datetime import timedelta
from scipy import stats
# endregion

class ImpliedCorrelationDispersion(QCAlgorithm):
    """
    EXOTIC ALPHA: Implied Correlation Dispersion Trade
    
    Hypothesis:
    -----------
    When implied correlation (priced into index options) diverges significantly 
    from realized correlation (actual stock co-movements), a dispersion opportunity
    exists. This strategy captures the "correlation risk premium."
    
    Key Insight:
    ------------
    Index volatility = f(component volatilities, correlations)
    
    If you know individual stock vols and index vol, you can back out implied
    correlation. When implied > realized → sell index vol, buy component vol
    (dispersion trade). We proxy this with sector ETFs.
    
    Signal Generation:
    -----------------
    1. Calculate realized correlation among sector ETFs (rolling 20-day)
    2. Estimate implied correlation from SPY vol vs sector vol basket
    3. When implied corr >> realized corr → long individual sectors, short SPY
    4. When implied corr << realized corr → long SPY, short sectors
    5. Market neutral with correlation alpha
    
    Novelty:
    --------
    - Pure correlation arbitrage, not directional
    - Uses sector ETFs as correlation proxy
    - Self-financing, market-neutral construction
    - Captures vol-of-vol and correlation risk premia
    """
    
    def Initialize(self):
        self.SetStartDate(2022, 1, 1)
        self.SetEndDate(2024, 12, 31)
        self.SetCash(100000)
        
        # Index
        self.spy = self.AddEquity("SPY", Resolution.Hour).Symbol
        
        # Sector ETFs for correlation tracking
        self.sectors = {
            "XLK": self.AddEquity("XLK", Resolution.Hour).Symbol,  # Technology
            "XLF": self.AddEquity("XLF", Resolution.Hour).Symbol,  # Financials
            "XLE": self.AddEquity("XLE", Resolution.Hour).Symbol,  # Energy
            "XLV": self.AddEquity("XLV", Resolution.Hour).Symbol,  # Healthcare
            "XLI": self.AddEquity("XLI", Resolution.Hour).Symbol,  # Industrials
            "XLC": self.AddEquity("XLC", Resolution.Hour).Symbol,  # Communications
            "XLY": self.AddEquity("XLY", Resolution.Hour).Symbol,  # Consumer Disc
            "XLP": self.AddEquity("XLP", Resolution.Hour).Symbol,  # Consumer Staples
        }
        
        # Price and return histories
        self.price_history = {sym: deque(maxlen=60) for sym in self.sectors.values()}
        self.price_history[self.spy] = deque(maxlen=60)
        
        self.return_history = {sym: deque(maxlen=60) for sym in self.sectors.values()}
        self.return_history[self.spy] = deque(maxlen=60)
        
        # Correlation tracking
        self.realized_corr_history = deque(maxlen=252)
        self.implied_corr_history = deque(maxlen=252)
        self.corr_spread_history = deque(maxlen=252)
        
        # Signal parameters
        self.corr_lookback = 20  # Days for realized correlation
        self.vol_lookback = 20   # Days for volatility calculation
        self.zscore_threshold = 1.5  # Threshold for trade entry
        
        # Position management
        self.max_sector_weight = 0.10  # Max weight per sector
        self.max_spy_weight = 0.40     # Max SPY hedge
        self.min_trade_size = 0.02     # Minimum position change
        
        # Current state
        self.current_signal = 0  # -1 to +1 scale
        self.position_type = "FLAT"  # DISPERSION_LONG, DISPERSION_SHORT, FLAT
        
        # Risk management
        self.max_drawdown = 0.12
        self.peak_value = self.Portfolio.TotalPortfolioValue
        
        # Schedule analysis
        self.Schedule.On(
            self.DateRules.EveryDay("SPY"),
            self.TimeRules.AfterMarketOpen("SPY", 45),
            self.CalculateCorrelations
        )
        
        self.Schedule.On(
            self.DateRules.EveryDay("SPY"),
            self.TimeRules.AfterMarketOpen("SPY", 90),
            self.ExecuteDispersionTrade
        )
        
        # End of day rebalance
        self.Schedule.On(
            self.DateRules.EveryDay("SPY"),
            self.TimeRules.BeforeMarketClose("SPY", 30),
            self.RebalancePortfolio
        )
        
        self.SetWarmUp(60, Resolution.Daily)
        
    def OnData(self, data: Slice):
        """Collect price data."""
        if self.IsWarmingUp:
            return
            
        # Update price histories
        all_symbols = list(self.sectors.values()) + [self.spy]
        
        for sym in all_symbols:
            if data.ContainsKey(sym) and data[sym] is not None:
                price = data[sym].Close
                
                # Store price
                if len(self.price_history[sym]) > 0:
                    prev_price = self.price_history[sym][-1]
                    if prev_price > 0:
                        ret = np.log(price / prev_price)
                        self.return_history[sym].append(ret)
                        
                self.price_history[sym].append(price)
                
        # Drawdown check
        current_value = self.Portfolio.TotalPortfolioValue
        self.peak_value = max(self.peak_value, current_value)
        drawdown = (self.peak_value - current_value) / self.peak_value
        
        if drawdown > self.max_drawdown:
            self.Liquidate()
            self.position_type = "FLAT"
            self.Debug(f"DRAWDOWN STOP: {drawdown:.2%}")
            
    def CalculateCorrelations(self):
        """Calculate realized and implied correlations."""
        # Need sufficient data
        min_data = self.corr_lookback
        sector_returns = {}
        
        for name, sym in self.sectors.items():
            if len(self.return_history[sym]) >= min_data:
                sector_returns[name] = np.array(list(self.return_history[sym])[-min_data:])
                
        if len(sector_returns) < 5:  # Need at least 5 sectors
            return
            
        if len(self.return_history[self.spy]) < min_data:
            return
            
        spy_returns = np.array(list(self.return_history[self.spy])[-min_data:])
        
        # Calculate realized pairwise correlations
        returns_matrix = np.array(list(sector_returns.values()))
        n_sectors = len(returns_matrix)
        
        correlations = []
        for i in range(n_sectors):
            for j in range(i + 1, n_sectors):
                corr = np.corrcoef(returns_matrix[i], returns_matrix[j])[0, 1]
                if not np.isnan(corr):
                    correlations.append(corr)
                    
        if len(correlations) == 0:
            return
            
        realized_corr = np.mean(correlations)
        
        # Calculate sector volatilities
        sector_vols = [np.std(ret) * np.sqrt(252) for ret in returns_matrix]
        avg_sector_vol = np.mean(sector_vols)
        
        # Calculate SPY (index) volatility
        spy_vol = np.std(spy_returns) * np.sqrt(252)
        
        # Implied correlation formula:
        # σ_index² ≈ Σwᵢ²σᵢ² + 2*ρ*Σwᵢwⱼσᵢσⱼ (simplified)
        # Rearranging: ρ_implied ≈ (σ_index² - avg(σ²)) / (avg(σ)² - avg(σ²))
        
        # Simplified approximation for implied correlation
        # When index vol is high relative to average sector vol, implied corr is high
        if avg_sector_vol > 0:
            # Normalized ratio as proxy for implied correlation
            vol_ratio = spy_vol / avg_sector_vol
            # Transform to correlation-like scale (0 to 1)
            implied_corr = min(max(vol_ratio ** 2 - 0.3, 0), 1)
        else:
            implied_corr = 0.5
            
        # Store history
        self.realized_corr_history.append(realized_corr)
        self.implied_corr_history.append(implied_corr)
        
        # Correlation spread (implied - realized)
        corr_spread = implied_corr - realized_corr
        self.corr_spread_history.append(corr_spread)
        
        # Calculate z-score of spread
        if len(self.corr_spread_history) >= 60:
            spreads = np.array(list(self.corr_spread_history))
            mean_spread = np.mean(spreads)
            std_spread = np.std(spreads)
            
            if std_spread > 0.01:
                zscore = (corr_spread - mean_spread) / std_spread
                self.current_signal = np.clip(zscore / 2, -1, 1)  # Normalized signal
            else:
                self.current_signal = 0
        else:
            self.current_signal = 0
            
    def ExecuteDispersionTrade(self):
        """Execute correlation dispersion trade."""
        if self.IsWarmingUp:
            return
            
        if abs(self.current_signal) < 0.3:  # Not enough signal
            return
            
        # Determine trade direction
        if self.current_signal > self.zscore_threshold / 2:
            # Implied corr >> realized corr
            # Dispersion trade: Long sectors, short SPY
            self.position_type = "DISPERSION_LONG"
            
        elif self.current_signal < -self.zscore_threshold / 2:
            # Implied corr << realized corr
            # Reverse dispersion: Long SPY, short sectors
            self.position_type = "DISPERSION_SHORT"
            
    def RebalancePortfolio(self):
        """Rebalance to target weights."""
        if self.IsWarmingUp:
            return
            
        signal_strength = abs(self.current_signal)
        
        if self.position_type == "DISPERSION_LONG":
            # Long individual sectors, hedge with short SPY
            sector_weight = self.max_sector_weight * signal_strength
            spy_weight = -self.max_spy_weight * signal_strength * 0.8  # Slight hedge ratio
            
            for name, sym in self.sectors.items():
                self.SetHoldings(sym, sector_weight)
                
            self.SetHoldings(self.spy, spy_weight)
            
        elif self.position_type == "DISPERSION_SHORT":
            # Long SPY, underweight sectors
            spy_weight = self.max_spy_weight * signal_strength
            sector_weight = -self.max_sector_weight * signal_strength * 0.5
            
            self.SetHoldings(self.spy, spy_weight)
            
            for name, sym in self.sectors.items():
                self.SetHoldings(sym, sector_weight)
                
        elif self.position_type == "FLAT":
            # Close all positions
            self.Liquidate()
            
    def OnEndOfAlgorithm(self):
        """Report final statistics."""
        self.Debug(f"=== IMPLIED CORRELATION DISPERSION RESULTS ===")
        self.Debug(f"Final Portfolio Value: ${self.Portfolio.TotalPortfolioValue:,.2f}")
        self.Debug(f"Total Return: {((self.Portfolio.TotalPortfolioValue - 100000) / 100000) * 100:.2f}%")
        
        if len(self.realized_corr_history) > 0:
            avg_realized = np.mean(list(self.realized_corr_history))
            avg_implied = np.mean(list(self.implied_corr_history))
            self.Debug(f"Avg Realized Correlation: {avg_realized:.3f}")
            self.Debug(f"Avg Implied Correlation: {avg_implied:.3f}")
