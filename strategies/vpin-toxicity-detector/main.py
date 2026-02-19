# region imports
from AlgorithmImports import *
import numpy as np
from collections import deque
from scipy.stats import norm
# endregion

class VPINToxicityDetector(QCAlgorithm):
    """
    VPIN TOXICITY DETECTOR
    ======================
    Implements Volume-Synchronized Probability of Informed Trading (VPIN)
    to detect order flow toxicity as a leading indicator for price moves.
    
    NOVELTY: Uses VPIN as a predictive signal for equity trading, not just
    risk management. Combines toxicity detection with volatility regime
    adaptation for optimal entry timing.
    
    HYPOTHESIS: High VPIN indicates informed traders are active. Rising VPIN
    with price increases = continuation. Rising VPIN with stable prices = 
    imminent directional move. Falling VPIN = consolidation incoming.
    """
    
    def Initialize(self):
        self.SetStartDate(2022, 1, 1)
        self.SetEndDate(2024, 12, 31)
        self.SetCash(100000)
        
        # High-volume assets for meaningful VPIN
        self.spy = self.AddEquity("SPY", Resolution.Minute).Symbol
        self.qqq = self.AddEquity("QQQ", Resolution.Minute).Symbol
        
        # VPIN parameters
        self.bucket_size = 50000  # Volume per bucket (shares)
        self.n_buckets = 50  # Number of buckets for VPIN calculation
        
        # Trade classification method: Bulk Volume Classification (BVC)
        self.sigma_lookback = 20  # Bars for volatility estimation
        
        # Current bucket accumulators
        self.current_bucket = {
            self.spy: {'volume': 0, 'buy_volume': 0, 'trades': []},
            self.qqq: {'volume': 0, 'buy_volume': 0, 'trades': []}
        }
        
        # Completed bucket history
        self.bucket_history = {
            self.spy: deque(maxlen=self.n_buckets),
            self.qqq: deque(maxlen=self.n_buckets)
        }
        
        # Price and volume history for BVC
        self.price_history = {
            self.spy: deque(maxlen=100),
            self.qqq: deque(maxlen=100)
        }
        
        # VPIN history for trend detection
        self.vpin_history = {
            self.spy: deque(maxlen=100),
            self.qqq: deque(maxlen=100)
        }
        
        # Toxicity regimes
        self.toxicity_state = {self.spy: 'normal', self.qqq: 'normal'}
        self.toxicity_direction = {self.spy: None, self.qqq: None}
        
        # Thresholds
        self.high_toxicity = 0.65  # VPIN > 0.65 = high informed trading
        self.low_toxicity = 0.35   # VPIN < 0.35 = low informed trading
        self.vpin_acceleration = 0.05  # Rising VPIN threshold
        
        # Position management
        self.entry_prices = {}
        self.entry_vpin = {}
        self.stop_losses = {}
        
        # Risk parameters
        self.max_position = 0.30
        self.base_stop = 0.02  # 2% stop
        self.profit_target = 0.04  # 4% target
        
        # Hourly analysis for signals
        self.hourly_consolidator_spy = TradeBarConsolidator(timedelta(hours=1))
        self.hourly_consolidator_spy.DataConsolidated += self.OnHourlyData
        self.SubscriptionManager.AddConsolidator(self.spy, self.hourly_consolidator_spy)
        
        self.hourly_consolidator_qqq = TradeBarConsolidator(timedelta(hours=1))
        self.hourly_consolidator_qqq.DataConsolidated += self.OnHourlyData
        self.SubscriptionManager.AddConsolidator(self.qqq, self.hourly_consolidator_qqq)
        
        # Track last analysis time
        self.last_signal_time = {}
        
        self.SetWarmUp(timedelta(days=10))
        
    def OnData(self, data):
        if self.IsWarmingUp:
            return
        
        # Process minute bars for VPIN calculation
        for symbol in [self.spy, self.qqq]:
            if not data.Bars.ContainsKey(symbol):
                continue
                
            bar = data.Bars[symbol]
            self.ProcessBarForVPIN(symbol, bar)
            
            # Update price history
            self.price_history[symbol].append(bar.Close)
        
        # Manage existing positions
        self.ManagePositions(data)
    
    def ProcessBarForVPIN(self, symbol, bar):
        """
        Process a bar for VPIN calculation using Bulk Volume Classification.
        BVC estimates buy/sell volume from price changes without tick data.
        """
        volume = bar.Volume
        if volume == 0:
            return
        
        # Calculate standardized price change for BVC
        if len(self.price_history[symbol]) < self.sigma_lookback:
            # Not enough history, use 50/50 split
            buy_vol = volume * 0.5
        else:
            prices = np.array(self.price_history[symbol])
            returns = np.diff(np.log(prices[-self.sigma_lookback:]))
            sigma = np.std(returns) if len(returns) > 0 else 0.01
            
            # Price change for this bar
            if len(prices) > 0:
                price_change = np.log(bar.Close / prices[-1])
            else:
                price_change = 0
            
            # Standardize
            z = price_change / sigma if sigma > 0 else 0
            
            # Probability of buy = Phi(z) using normal CDF
            buy_prob = norm.cdf(z)
            buy_vol = volume * buy_prob
        
        # Add to current bucket
        bucket = self.current_bucket[symbol]
        bucket['volume'] += volume
        bucket['buy_volume'] += buy_vol
        bucket['trades'].append({
            'price': bar.Close,
            'volume': volume,
            'buy_volume': buy_vol
        })
        
        # Check if bucket is complete
        while bucket['volume'] >= self.bucket_size:
            # Calculate bucket metrics
            overflow = bucket['volume'] - self.bucket_size
            overflow_ratio = overflow / bucket['volume'] if bucket['volume'] > 0 else 0
            
            # Finalize bucket
            final_buy = bucket['buy_volume'] * (1 - overflow_ratio)
            final_sell = self.bucket_size - final_buy
            
            # Store completed bucket
            self.bucket_history[symbol].append({
                'buy_volume': final_buy,
                'sell_volume': final_sell,
                'order_imbalance': abs(final_buy - final_sell)
            })
            
            # Calculate VPIN if enough buckets
            if len(self.bucket_history[symbol]) >= self.n_buckets:
                vpin = self.CalculateVPIN(symbol)
                self.vpin_history[symbol].append(vpin)
            
            # Reset bucket with overflow
            new_buy_vol = bucket['buy_volume'] * overflow_ratio
            bucket['volume'] = overflow
            bucket['buy_volume'] = new_buy_vol
            bucket['trades'] = []
    
    def CalculateVPIN(self, symbol):
        """
        Calculate VPIN from bucket history.
        VPIN = Sum(|Buy_i - Sell_i|) / Sum(Volume_i)
        """
        if len(self.bucket_history[symbol]) < self.n_buckets:
            return None
        
        buckets = list(self.bucket_history[symbol])[-self.n_buckets:]
        
        total_imbalance = sum(b['order_imbalance'] for b in buckets)
        total_volume = self.n_buckets * self.bucket_size
        
        vpin = total_imbalance / total_volume if total_volume > 0 else 0
        
        return vpin
    
    def DetectToxicityRegime(self, symbol):
        """
        Detect toxicity regime and predict direction.
        """
        if len(self.vpin_history[symbol]) < 10:
            return None, None, 0
        
        vpin_array = np.array(self.vpin_history[symbol])
        current_vpin = vpin_array[-1]
        vpin_ma = np.mean(vpin_array[-10:])
        vpin_change = current_vpin - np.mean(vpin_array[-5:-1]) if len(vpin_array) > 5 else 0
        
        # Price momentum for direction
        if len(self.price_history[symbol]) >= 20:
            prices = np.array(self.price_history[symbol])
            momentum = (prices[-1] - prices[-20]) / prices[-20]
        else:
            momentum = 0
        
        # Determine regime
        if current_vpin > self.high_toxicity:
            regime = 'toxic'
            # High toxicity with momentum = continuation
            # High toxicity without momentum = imminent move
            if abs(momentum) > 0.01:
                direction = 'LONG' if momentum > 0 else 'SHORT'
                confidence = min(1.0, (current_vpin - 0.5) * 2)
            else:
                # Buildup without price move - predict breakout
                direction = 'PENDING'
                confidence = min(1.0, (current_vpin - 0.5) * 1.5)
                
        elif current_vpin < self.low_toxicity:
            regime = 'clean'
            direction = None
            confidence = 0
            
        else:
            regime = 'normal'
            # Check for VPIN acceleration
            if vpin_change > self.vpin_acceleration:
                direction = 'RISING'
                confidence = min(1.0, vpin_change / 0.1)
            else:
                direction = None
                confidence = 0
        
        return regime, direction, confidence
    
    def OnHourlyData(self, sender, bar):
        """
        Analyze toxicity and generate signals on hourly bars.
        """
        symbol = bar.Symbol
        
        if symbol not in self.vpin_history:
            return
            
        if len(self.vpin_history[symbol]) < 20:
            return
        
        # Detect regime
        regime, direction, confidence = self.DetectToxicityRegime(symbol)
        
        if regime is None:
            return
        
        old_state = self.toxicity_state[symbol]
        self.toxicity_state[symbol] = regime
        self.toxicity_direction[symbol] = direction
        
        current_vpin = self.vpin_history[symbol][-1]
        
        # Log regime changes
        if old_state != regime:
            self.Debug(f"{symbol}: Toxicity {old_state} -> {regime} | VPIN: {current_vpin:.3f} | Direction: {direction}")
        
        # Generate trading signals
        current_qty = self.Portfolio[symbol].Quantity
        price = bar.Close
        
        # Rate limit signals
        current_time = self.Time
        if symbol in self.last_signal_time:
            if (current_time - self.last_signal_time[symbol]).total_seconds() < 3600:
                return
        
        if regime == 'toxic' and confidence > 0.5:
            if direction == 'LONG' and current_qty <= 0:
                self.EnterLong(symbol, price, current_vpin, confidence)
                self.last_signal_time[symbol] = current_time
                
            elif direction == 'PENDING' and current_qty == 0:
                # Prepare for breakout - wait for direction
                # Could implement straddle here, but for now track
                self.Debug(f"{symbol}: PENDING breakout, VPIN={current_vpin:.3f}")
                
        elif regime == 'clean' and current_qty > 0:
            # Low toxicity = informed traders exiting, follow them out
            self.Debug(f"{symbol}: Clean regime - considering exit")
    
    def EnterLong(self, symbol, price, vpin, confidence):
        """
        Enter long position based on toxicity signal.
        """
        position_size = self.max_position * confidence
        target_value = self.Portfolio.TotalPortfolioValue * position_size
        shares = int(target_value / price)
        
        if shares > 0:
            self.MarketOrder(symbol, shares)
            self.entry_prices[symbol] = price
            self.entry_vpin[symbol] = vpin
            self.stop_losses[symbol] = price * (1 - self.base_stop)
            
            self.Debug(f"LONG {shares} {symbol} @ {price:.2f} | VPIN: {vpin:.3f} | Conf: {confidence:.2f}")
    
    def ManagePositions(self, data):
        """
        Manage positions with VPIN-aware stops.
        """
        for symbol in list(self.entry_prices.keys()):
            if not data.Bars.ContainsKey(symbol):
                continue
            
            price = data.Bars[symbol].Close
            entry = self.entry_prices[symbol]
            stop = self.stop_losses[symbol]
            
            current_qty = self.Portfolio[symbol].Quantity
            if current_qty <= 0:
                self.CleanupPosition(symbol)
                continue
            
            pnl_pct = (price - entry) / entry
            
            # Check current VPIN
            current_vpin = None
            if len(self.vpin_history[symbol]) > 0:
                current_vpin = self.vpin_history[symbol][-1]
            
            # Stop loss
            if price < stop:
                self.Liquidate(symbol)
                self.Debug(f"STOP: {symbol} @ {price:.2f}")
                self.CleanupPosition(symbol)
                continue
            
            # Profit target
            if pnl_pct >= self.profit_target:
                self.Liquidate(symbol)
                self.Debug(f"TARGET: {symbol} @ {price:.2f} | PnL: {pnl_pct*100:.1f}%")
                self.CleanupPosition(symbol)
                continue
            
            # VPIN-based exit: if toxicity drops significantly, exit
            if current_vpin is not None and symbol in self.entry_vpin:
                vpin_drop = self.entry_vpin[symbol] - current_vpin
                if vpin_drop > 0.15 and pnl_pct > 0:
                    # Informed traders leaving, take profits
                    self.Liquidate(symbol)
                    self.Debug(f"VPIN EXIT: {symbol} @ {price:.2f} | VPIN dropped {vpin_drop:.3f}")
                    self.CleanupPosition(symbol)
                    continue
            
            # Trail stop after 2% gain
            if pnl_pct > 0.02:
                new_stop = price * 0.985  # 1.5% trailing
                if new_stop > self.stop_losses[symbol]:
                    self.stop_losses[symbol] = new_stop
    
    def CleanupPosition(self, symbol):
        """Clean up position tracking."""
        for d in [self.entry_prices, self.entry_vpin, self.stop_losses]:
            if symbol in d:
                del d[symbol]
    
    def OnEndOfAlgorithm(self):
        """Final statistics."""
        self.Debug(f"=== VPIN TOXICITY DETECTOR FINAL STATS ===")
        self.Debug(f"Portfolio Value: ${self.Portfolio.TotalPortfolioValue:,.2f}")
        self.Debug(f"Total Profit: ${self.Portfolio.TotalProfit:,.2f}")
        
        # Log final VPIN values
        for symbol in [self.spy, self.qqq]:
            if len(self.vpin_history[symbol]) > 0:
                self.Debug(f"{symbol} Final VPIN: {self.vpin_history[symbol][-1]:.3f}")
