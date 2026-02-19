# region imports
from AlgorithmImports import *
import numpy as np
from collections import deque, defaultdict
from datetime import timedelta
# endregion

class SectorRotationVelocity(QCAlgorithm):
    """
    EXOTIC ALPHA: Sector Rotation Velocity (Second Derivative Strategy)
    
    Hypothesis:
    -----------
    Everyone watches relative strength (RS). No one watches the RATE OF CHANGE
    of relative strength (RS velocity) or the ACCELERATION (RS acceleration).
    
    The second derivative of relative strength reveals:
    - Accelerating RS = Trend BEGINNING (get in early)
    - Decelerating RS = Trend ENDING (get out before reversal)
    - Inflection points = Maximum information density
    
    Key Insight:
    ------------
    Traditional sector rotation looks at: "Which sector is strongest?"
    We look at: "Which sector is GAINING strength FASTEST?"
    
    This gives us lead time on traditional rotators.
    
    Signal Generation:
    -----------------
    1. Calculate 20-day relative strength (sector/SPY)
    2. Calculate RS velocity (first derivative)
    3. Calculate RS acceleration (second derivative)
    4. Rank sectors by ACCELERATION, not level
    5. Long accelerating sectors, avoid decelerating
    
    Novelty:
    --------
    - Second derivative of relative strength (unprecedented)
    - Momentum of momentum = meta-momentum
    - Identifies trend inflection points
    - Early entry, early exit optimization
    """
    
    def Initialize(self):
        self.SetStartDate(2022, 1, 1)
        self.SetEndDate(2024, 12, 31)
        self.SetCash(100000)
        
        # Benchmark
        self.spy = self.AddEquity("SPY", Resolution.Hour).Symbol
        
        # Sector ETFs
        self.sectors = {
            "XLK": {"name": "Technology", "symbol": None},
            "XLF": {"name": "Financials", "symbol": None},
            "XLE": {"name": "Energy", "symbol": None},
            "XLV": {"name": "Healthcare", "symbol": None},
            "XLI": {"name": "Industrials", "symbol": None},
            "XLC": {"name": "Communications", "symbol": None},
            "XLY": {"name": "Consumer Discretionary", "symbol": None},
            "XLP": {"name": "Consumer Staples", "symbol": None},
            "XLU": {"name": "Utilities", "symbol": None},
            "XLB": {"name": "Materials", "symbol": None},
            "XLRE": {"name": "Real Estate", "symbol": None},
        }
        
        # Add all sectors
        for ticker in self.sectors:
            self.sectors[ticker]["symbol"] = self.AddEquity(ticker, Resolution.Hour).Symbol
            
        # Price histories
        self.price_history = {self.spy: deque(maxlen=100)}
        for ticker, data in self.sectors.items():
            self.price_history[data["symbol"]] = deque(maxlen=100)
            
        # Relative strength histories (for derivatives)
        self.rs_history = {ticker: deque(maxlen=40) for ticker in self.sectors}
        self.rs_velocity = {ticker: deque(maxlen=20) for ticker in self.sectors}
        self.rs_acceleration = {ticker: 0.0 for ticker in self.sectors}
        
        # Signal parameters
        self.rs_lookback = 20  # Days for RS calculation
        self.velocity_lookback = 10  # Days for velocity smoothing
        self.accel_lookback = 5  # Days for acceleration
        
        # Position parameters
        self.top_n_sectors = 3  # Number of sectors to hold
        self.max_sector_weight = 0.25  # Max weight per sector
        self.total_equity_exposure = 0.90  # Total market exposure
        
        # Momentum filters
        self.min_rs_velocity = 0.0  # Only long if velocity positive
        self.min_rs_level = 0.95  # Only long if RS > 0.95 (near benchmark)
        
        # Risk management
        self.max_drawdown = 0.18
        self.sector_stop_loss = 0.08  # Individual sector stop
        self.peak_value = self.Portfolio.TotalPortfolioValue
        self.entry_prices = {}
        
        # Current rankings
        self.sector_rankings = []
        self.last_rebalance = self.Time
        self.rebalance_days = 5  # Minimum days between rebalances
        
        # Schedule daily analysis
        self.Schedule.On(
            self.DateRules.EveryDay("SPY"),
            self.TimeRules.AfterMarketOpen("SPY", 30),
            self.CalculateRotationVelocity
        )
        
        # Weekly rebalance
        self.Schedule.On(
            self.DateRules.Every(DayOfWeek.Monday, DayOfWeek.Thursday),
            self.TimeRules.AfterMarketOpen("SPY", 60),
            self.RebalancePortfolio
        )
        
        self.SetWarmUp(60, Resolution.Daily)
        
    def OnData(self, data: Slice):
        """Collect price data."""
        if self.IsWarmingUp:
            return
            
        # Update price histories
        if data.ContainsKey(self.spy) and data[self.spy] is not None:
            self.price_history[self.spy].append(data[self.spy].Close)
            
        for ticker, sector_data in self.sectors.items():
            sym = sector_data["symbol"]
            if data.ContainsKey(sym) and data[sym] is not None:
                self.price_history[sym].append(data[sym].Close)
                
        # Drawdown management
        current_value = self.Portfolio.TotalPortfolioValue
        self.peak_value = max(self.peak_value, current_value)
        drawdown = (self.peak_value - current_value) / self.peak_value
        
        if drawdown > self.max_drawdown:
            self.Liquidate()
            self.Debug(f"MAX DRAWDOWN: {drawdown:.2%}")
            
        # Individual sector stop losses
        for ticker, sector_data in self.sectors.items():
            sym = sector_data["symbol"]
            if self.Portfolio[sym].Invested:
                if sym in self.entry_prices:
                    current_price = self.Securities[sym].Price
                    entry_price = self.entry_prices[sym]
                    if current_price < entry_price * (1 - self.sector_stop_loss):
                        self.Liquidate(sym)
                        self.Debug(f"STOP LOSS: {ticker}")
                        
    def CalculateRotationVelocity(self):
        """Calculate RS, velocity, and acceleration for all sectors."""
        if len(self.price_history[self.spy]) < self.rs_lookback + 10:
            return
            
        spy_prices = list(self.price_history[self.spy])
        spy_current = spy_prices[-1]
        spy_past = spy_prices[-self.rs_lookback]
        
        if spy_past <= 0:
            return
            
        spy_return = (spy_current / spy_past) - 1
        
        for ticker, sector_data in self.sectors.items():
            sym = sector_data["symbol"]
            
            if len(self.price_history[sym]) < self.rs_lookback + 10:
                continue
                
            sector_prices = list(self.price_history[sym])
            sector_current = sector_prices[-1]
            sector_past = sector_prices[-self.rs_lookback]
            
            if sector_past <= 0:
                continue
                
            sector_return = (sector_current / sector_past) - 1
            
            # Relative Strength (sector return / spy return)
            # Using ratio instead of difference for better normalization
            if spy_return != 0:
                rs = (1 + sector_return) / (1 + spy_return)
            else:
                rs = 1.0
                
            self.rs_history[ticker].append(rs)
            
            # Calculate RS Velocity (first derivative)
            if len(self.rs_history[ticker]) >= self.velocity_lookback:
                rs_series = list(self.rs_history[ticker])
                velocity = (rs_series[-1] - rs_series[-self.velocity_lookback]) / self.velocity_lookback
                self.rs_velocity[ticker].append(velocity)
                
                # Calculate RS Acceleration (second derivative)
                if len(self.rs_velocity[ticker]) >= self.accel_lookback:
                    vel_series = list(self.rs_velocity[ticker])
                    acceleration = (vel_series[-1] - vel_series[-self.accel_lookback]) / self.accel_lookback
                    self.rs_acceleration[ticker] = acceleration
                    
        # Rank sectors by acceleration
        self.RankSectors()
        
    def RankSectors(self):
        """Rank sectors by rotation velocity metrics."""
        rankings = []
        
        for ticker, sector_data in self.sectors.items():
            if len(self.rs_history[ticker]) < 10:
                continue
                
            rs_level = list(self.rs_history[ticker])[-1] if self.rs_history[ticker] else 1.0
            rs_vel = list(self.rs_velocity[ticker])[-1] if self.rs_velocity[ticker] else 0.0
            rs_accel = self.rs_acceleration[ticker]
            
            # Composite score: Weight acceleration highest
            # Acceleration = 50%, Velocity = 30%, Level = 20%
            composite_score = (
                0.50 * self.normalize_acceleration(rs_accel) +
                0.30 * self.normalize_velocity(rs_vel) +
                0.20 * self.normalize_level(rs_level)
            )
            
            rankings.append({
                "ticker": ticker,
                "symbol": sector_data["symbol"],
                "name": sector_data["name"],
                "rs_level": rs_level,
                "rs_velocity": rs_vel,
                "rs_acceleration": rs_accel,
                "composite_score": composite_score
            })
            
        # Sort by composite score (highest first)
        self.sector_rankings = sorted(rankings, key=lambda x: x["composite_score"], reverse=True)
        
    def normalize_acceleration(self, accel):
        """Normalize acceleration to 0-1 scale."""
        # Typical acceleration range: -0.01 to +0.01
        return np.clip((accel + 0.01) / 0.02, 0, 1)
        
    def normalize_velocity(self, vel):
        """Normalize velocity to 0-1 scale."""
        # Typical velocity range: -0.05 to +0.05
        return np.clip((vel + 0.05) / 0.10, 0, 1)
        
    def normalize_level(self, level):
        """Normalize RS level to 0-1 scale."""
        # Typical RS range: 0.8 to 1.2
        return np.clip((level - 0.8) / 0.4, 0, 1)
        
    def RebalancePortfolio(self):
        """Rebalance to top-ranked sectors."""
        if self.IsWarmingUp:
            return
            
        if len(self.sector_rankings) < self.top_n_sectors:
            return
            
        # Check rebalance frequency
        if (self.Time - self.last_rebalance).days < self.rebalance_days:
            return
            
        self.last_rebalance = self.Time
        
        # Get top sectors with positive acceleration
        top_sectors = []
        for sector in self.sector_rankings[:self.top_n_sectors * 2]:  # Consider more sectors
            # Filter: Must have positive velocity AND positive acceleration
            if sector["rs_velocity"] > self.min_rs_velocity and sector["rs_acceleration"] > 0:
                top_sectors.append(sector)
                if len(top_sectors) >= self.top_n_sectors:
                    break
                    
        if len(top_sectors) == 0:
            # No good sectors, go defensive
            self.Liquidate()
            return
            
        # Calculate weights (equal weight for simplicity, or score-weighted)
        total_score = sum(s["composite_score"] for s in top_sectors)
        
        # Close positions not in top sectors
        top_symbols = [s["symbol"] for s in top_sectors]
        for ticker, sector_data in self.sectors.items():
            sym = sector_data["symbol"]
            if self.Portfolio[sym].Invested and sym not in top_symbols:
                self.Liquidate(sym)
                
        # Open/adjust positions in top sectors
        for sector in top_sectors:
            # Score-weighted allocation
            weight = (sector["composite_score"] / total_score) * self.total_equity_exposure
            weight = min(weight, self.max_sector_weight)
            
            self.SetHoldings(sector["symbol"], weight)
            self.entry_prices[sector["symbol"]] = self.Securities[sector["symbol"]].Price
            
        # Log rotation
        sector_names = [s["ticker"] for s in top_sectors]
        self.Debug(f"ROTATION: {sector_names} | Scores: {[f'{s[\"composite_score\"]:.3f}' for s in top_sectors]}")
        
    def OnEndOfAlgorithm(self):
        """Report final statistics."""
        self.Debug(f"=== SECTOR ROTATION VELOCITY RESULTS ===")
        self.Debug(f"Final Portfolio Value: ${self.Portfolio.TotalPortfolioValue:,.2f}")
        self.Debug(f"Total Return: {((self.Portfolio.TotalPortfolioValue - 100000) / 100000) * 100:.2f}%")
        
        if self.sector_rankings:
            self.Debug("Final Sector Rankings (by acceleration):")
            for i, sector in enumerate(self.sector_rankings[:5]):
                self.Debug(f"  {i+1}. {sector['ticker']}: Accel={sector['rs_acceleration']:.4f}, "
                          f"Vel={sector['rs_velocity']:.4f}, RS={sector['rs_level']:.3f}")
