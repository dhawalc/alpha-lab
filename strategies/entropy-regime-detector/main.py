# region imports
from AlgorithmImports import *
import numpy as np
from collections import deque
from itertools import permutations
from math import factorial, log2
# endregion

class EntropyRegimeDetector(QCAlgorithm):
    """
    ENTROPY REGIME DETECTOR
    =======================
    Uses permutation entropy to detect market regime changes before they're visible
    in price action. Low entropy = trending/predictable. High entropy = chaotic/mean-reverting.
    
    NOVELTY: First known implementation using permutation entropy as a regime classifier
    combined with adaptive position sizing based on entropy confidence.
    
    HYPOTHESIS: Market regimes leave fingerprints in price sequence ordinal patterns.
    Entropy collapse precedes strong trends; entropy expansion precedes reversals.
    """
    
    def Initialize(self):
        self.SetStartDate(2022, 1, 1)
        self.SetEndDate(2024, 12, 31)
        self.SetCash(100000)
        
        # Primary asset
        self.spy = self.AddEquity("SPY", Resolution.Hour).Symbol
        self.qqq = self.AddEquity("QQQ", Resolution.Hour).Symbol
        self.iwm = self.AddEquity("IWM", Resolution.Hour).Symbol
        
        # Entropy parameters
        self.embedding_dim = 5  # Ordinal pattern length
        self.tau = 1  # Time delay
        self.lookback = 120  # Hours for entropy calculation
        
        # Regime thresholds (normalized 0-1)
        self.low_entropy_threshold = 0.65  # Trending regime
        self.high_entropy_threshold = 0.85  # Chaotic regime
        
        # Price history buffers
        self.price_buffer = {
            self.spy: deque(maxlen=self.lookback + self.embedding_dim * self.tau),
            self.qqq: deque(maxlen=self.lookback + self.embedding_dim * self.tau),
            self.iwm: deque(maxlen=self.lookback + self.embedding_dim * self.tau)
        }
        
        # Entropy history for regime change detection
        self.entropy_history = {
            self.spy: deque(maxlen=24),  # 24 hours of entropy readings
            self.qqq: deque(maxlen=24),
            self.iwm: deque(maxlen=24)
        }
        
        # Regime states
        self.current_regime = {self.spy: None, self.qqq: None, self.iwm: None}
        self.regime_confidence = {self.spy: 0, self.qqq: 0, self.iwm: 0}
        
        # Trade tracking
        self.entry_prices = {}
        self.stop_losses = {}
        
        # Risk management
        self.max_position_size = 0.3  # Max 30% per position
        self.base_stop_loss = 0.03  # 3% stop loss
        self.profit_target = 0.05  # 5% profit target
        
        # Schedule rebalancing
        self.Schedule.On(
            self.DateRules.EveryDay(self.spy),
            self.TimeRules.AfterMarketOpen(self.spy, 30),
            self.AnalyzeRegimes
        )
        
        # Warm up
        self.SetWarmUp(timedelta(days=30))
        
    def OnData(self, data):
        if self.IsWarmingUp:
            return
            
        # Update price buffers
        for symbol in [self.spy, self.qqq, self.iwm]:
            if data.Bars.ContainsKey(symbol):
                self.price_buffer[symbol].append(data.Bars[symbol].Close)
        
        # Check stops and targets
        self.ManagePositions(data)
    
    def CalculatePermutationEntropy(self, prices):
        """
        Calculate normalized permutation entropy of a price series.
        Returns value between 0 (perfectly predictable) and 1 (maximum randomness).
        """
        if len(prices) < self.embedding_dim + (self.embedding_dim - 1) * self.tau:
            return None
            
        prices = np.array(prices)
        n = len(prices)
        
        # Generate all embedding vectors
        m = self.embedding_dim
        tau = self.tau
        
        # Count pattern frequencies
        pattern_counts = {}
        total_patterns = 0
        
        for i in range(n - (m - 1) * tau):
            # Extract embedding vector
            embedding = [prices[i + j * tau] for j in range(m)]
            
            # Convert to ordinal pattern (ranking)
            pattern = tuple(sorted(range(m), key=lambda k: embedding[k]))
            
            pattern_counts[pattern] = pattern_counts.get(pattern, 0) + 1
            total_patterns += 1
        
        if total_patterns == 0:
            return None
        
        # Calculate Shannon entropy of pattern distribution
        entropy = 0
        for count in pattern_counts.values():
            p = count / total_patterns
            if p > 0:
                entropy -= p * log2(p)
        
        # Normalize by maximum possible entropy
        max_entropy = log2(factorial(m))
        normalized_entropy = entropy / max_entropy if max_entropy > 0 else 0
        
        return normalized_entropy
    
    def DetectRegimeChange(self, symbol):
        """
        Detect regime changes using entropy rate of change.
        Returns: 'trending', 'chaotic', 'transitioning', or None
        """
        if len(self.entropy_history[symbol]) < 6:
            return None, 0
            
        entropy_array = np.array(self.entropy_history[symbol])
        current_entropy = entropy_array[-1]
        entropy_ma = np.mean(entropy_array[-6:])
        entropy_change = current_entropy - np.mean(entropy_array[:-1])
        
        # Determine regime
        if current_entropy < self.low_entropy_threshold:
            regime = 'trending'
            confidence = (self.low_entropy_threshold - current_entropy) / self.low_entropy_threshold
        elif current_entropy > self.high_entropy_threshold:
            regime = 'chaotic'
            confidence = (current_entropy - self.high_entropy_threshold) / (1 - self.high_entropy_threshold)
        else:
            regime = 'transitioning'
            confidence = 0.3
        
        # Boost confidence if entropy is falling rapidly (regime solidifying)
        if abs(entropy_change) > 0.05:
            confidence = min(1.0, confidence * 1.5)
            
        return regime, min(1.0, confidence)
    
    def AnalyzeRegimes(self):
        """
        Main regime analysis and trading logic.
        """
        signals = {}
        
        for symbol in [self.spy, self.qqq, self.iwm]:
            if len(self.price_buffer[symbol]) < self.lookback:
                continue
                
            # Calculate current entropy
            prices = list(self.price_buffer[symbol])
            entropy = self.CalculatePermutationEntropy(prices[-self.lookback:])
            
            if entropy is None:
                continue
                
            self.entropy_history[symbol].append(entropy)
            
            # Detect regime
            regime, confidence = self.DetectRegimeChange(symbol)
            
            if regime is None:
                continue
                
            old_regime = self.current_regime[symbol]
            self.current_regime[symbol] = regime
            self.regime_confidence[symbol] = confidence
            
            # Generate signals based on regime transitions
            if old_regime != regime:
                self.Debug(f"{symbol}: Regime change {old_regime} -> {regime} (entropy: {entropy:.3f}, conf: {confidence:.2f})")
            
            # Trading logic
            current_holding = self.Portfolio[symbol].Quantity
            price = self.Securities[symbol].Price
            
            if regime == 'trending' and confidence > 0.5:
                # In trending regime: follow momentum
                if len(prices) >= 20:
                    momentum = (prices[-1] - prices[-20]) / prices[-20]
                    
                    if momentum > 0.02 and current_holding <= 0:
                        # Strong upward trend detected
                        signals[symbol] = ('BUY', confidence)
                    elif momentum < -0.02 and current_holding >= 0:
                        # Strong downward trend - go flat or short
                        signals[symbol] = ('SELL', confidence)
                        
            elif regime == 'chaotic' and confidence > 0.6:
                # In chaotic regime: mean reversion
                if len(prices) >= 20:
                    ma20 = np.mean(prices[-20:])
                    deviation = (prices[-1] - ma20) / ma20
                    
                    if deviation < -0.03 and current_holding <= 0:
                        # Oversold in chaotic regime - buy for reversion
                        signals[symbol] = ('BUY', confidence * 0.7)
                    elif deviation > 0.03 and current_holding > 0:
                        # Overbought - take profits
                        signals[symbol] = ('SELL', confidence * 0.7)
            
            elif regime == 'transitioning':
                # Reduce exposure during transitions
                if abs(current_holding) > 0:
                    signals[symbol] = ('REDUCE', 0.5)
        
        # Execute signals
        self.ExecuteSignals(signals)
    
    def ExecuteSignals(self, signals):
        """
        Execute trading signals with position sizing based on confidence.
        """
        for symbol, (action, confidence) in signals.items():
            price = self.Securities[symbol].Price
            
            if action == 'BUY':
                # Position size based on confidence
                position_size = self.max_position_size * confidence
                target_value = self.Portfolio.TotalPortfolioValue * position_size
                shares = int(target_value / price)
                
                if shares > 0:
                    self.MarketOrder(symbol, shares)
                    self.entry_prices[symbol] = price
                    self.stop_losses[symbol] = price * (1 - self.base_stop_loss)
                    self.Debug(f"BUY {shares} {symbol} @ {price:.2f} (conf: {confidence:.2f})")
                    
            elif action == 'SELL':
                current_qty = self.Portfolio[symbol].Quantity
                if current_qty > 0:
                    self.Liquidate(symbol)
                    self.Debug(f"SELL {current_qty} {symbol} @ {price:.2f}")
                    if symbol in self.entry_prices:
                        del self.entry_prices[symbol]
                        del self.stop_losses[symbol]
                        
            elif action == 'REDUCE':
                current_qty = self.Portfolio[symbol].Quantity
                if current_qty > 0:
                    reduce_qty = int(current_qty * 0.5)
                    if reduce_qty > 0:
                        self.MarketOrder(symbol, -reduce_qty)
                        self.Debug(f"REDUCE {reduce_qty} {symbol} @ {price:.2f}")
    
    def ManagePositions(self, data):
        """
        Manage stop losses and profit targets.
        """
        for symbol in [self.spy, self.qqq, self.iwm]:
            if symbol not in self.entry_prices:
                continue
                
            if not data.Bars.ContainsKey(symbol):
                continue
                
            price = data.Bars[symbol].Close
            entry = self.entry_prices[symbol]
            stop = self.stop_losses[symbol]
            
            current_qty = self.Portfolio[symbol].Quantity
            if current_qty <= 0:
                continue
            
            # Check stop loss
            if price < stop:
                self.Liquidate(symbol)
                self.Debug(f"STOP HIT: {symbol} @ {price:.2f} (entry: {entry:.2f})")
                del self.entry_prices[symbol]
                del self.stop_losses[symbol]
                continue
            
            # Check profit target
            if price >= entry * (1 + self.profit_target):
                # Take partial profits
                sell_qty = int(current_qty * 0.5)
                if sell_qty > 0:
                    self.MarketOrder(symbol, -sell_qty)
                    # Trail stop to breakeven
                    self.stop_losses[symbol] = entry
                    self.Debug(f"PARTIAL PROFIT: {symbol} @ {price:.2f}")
            
            # Trail stop for winners
            elif price > entry * 1.02:
                new_stop = price * 0.98
                if new_stop > self.stop_losses[symbol]:
                    self.stop_losses[symbol] = new_stop
    
    def OnEndOfAlgorithm(self):
        """Log final statistics."""
        self.Debug(f"=== ENTROPY REGIME DETECTOR FINAL STATS ===")
        self.Debug(f"Total Portfolio Value: ${self.Portfolio.TotalPortfolioValue:,.2f}")
        self.Debug(f"Total Profit: ${self.Portfolio.TotalProfit:,.2f}")
