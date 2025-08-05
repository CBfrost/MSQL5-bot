import logging
import numpy as np
import pandas as pd
from collections import deque
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from datetime import datetime, timezone
import asyncio

from src.utils import get_current_timestamp, round_to_precision

@dataclass
class TickData:
    """Individual tick data point"""
    timestamp: float
    price: float
    symbol: str
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp,
            'price': self.price,
            'symbol': self.symbol
        }

@dataclass
class MarketStats:
    """Current market statistics"""
    current_price: float
    price_change: float
    price_change_pct: float
    volatility: float
    tick_count: int
    last_update: float
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'current_price': self.current_price,
            'price_change': self.price_change,
            'price_change_pct': self.price_change_pct,
            'volatility': self.volatility,
            'tick_count': self.tick_count,
            'last_update': self.last_update
        }

class RSICalculator:
    """Efficient RSI calculation with rolling window"""
    
    def __init__(self, period: int = 14):
        self.period = period
        self.prices = deque(maxlen=period + 1)  # Need one extra for price change calculation
        self.gains = deque(maxlen=period)
        self.losses = deque(maxlen=period)
        self.avg_gain = 0.0
        self.avg_loss = 0.0
        self.rsi_value = 50.0  # Start at neutral
        
    def add_price(self, price: float) -> float:
        """Add new price and calculate RSI"""
        self.prices.append(price)
        
        if len(self.prices) < 2:
            return self.rsi_value
        
        # Calculate price change
        change = self.prices[-1] - self.prices[-2]
        
        if change > 0:
            self.gains.append(change)
            self.losses.append(0.0)
        else:
            self.gains.append(0.0)
            self.losses.append(abs(change))
        
        # Need enough data points for RSI calculation
        if len(self.gains) < self.period:
            return self.rsi_value
        
        # Calculate average gain and loss
        if len(self.gains) == self.period:
            # Initial calculation (simple average)
            self.avg_gain = sum(self.gains) / self.period
            self.avg_loss = sum(self.losses) / self.period
        else:
            # Smoothed calculation (Wilder's smoothing)
            self.avg_gain = (self.avg_gain * (self.period - 1) + self.gains[-1]) / self.period
            self.avg_loss = (self.avg_loss * (self.period - 1) + self.losses[-1]) / self.period
        
        # Calculate RSI
        if self.avg_loss == 0:
            self.rsi_value = 100.0
        else:
            rs = self.avg_gain / self.avg_loss
            self.rsi_value = 100.0 - (100.0 / (1.0 + rs))
        
        return round_to_precision(self.rsi_value, 2)
    
    def get_rsi(self) -> float:
        """Get current RSI value"""
        return self.rsi_value
    
    def is_ready(self) -> bool:
        """Check if RSI has enough data for reliable calculation"""
        return len(self.gains) >= self.period

class MarketDataEngine:
    """Real-time market data processing and analysis"""
    
    def __init__(self, symbol: str, rsi_period: int = 14, max_history: int = 1000):
        self.symbol = symbol
        self.logger = logging.getLogger('MarketData')
        
        # Data storage
        self.tick_history = deque(maxlen=max_history)
        self.price_history = deque(maxlen=max_history)
        self.timestamps = deque(maxlen=max_history)
        
        # Technical indicators
        self.rsi_calculator = RSICalculator(rsi_period)
        
        # Market state
        self.current_price = 0.0
        self.previous_price = 0.0
        self.tick_count = 0
        self.last_update = 0.0
        
        # Volatility calculation
        self.volatility_window = 50
        self.price_changes = deque(maxlen=self.volatility_window)
        
        # Pattern detection
        self.consecutive_moves = 0
        self.last_move_direction = 0  # 1 for up, -1 for down, 0 for no move
        
        # Statistics
        self.stats = MarketStats(0.0, 0.0, 0.0, 0.0, 0, 0.0)
        
    async def process_tick(self, tick_data: Dict[str, Any]) -> bool:
        """Process incoming tick data"""
        try:
            # Extract tick information
            tick = tick_data.get('tick', {})
            price = float(tick.get('quote', 0))
            timestamp = float(tick.get('epoch', get_current_timestamp()))
            
            if price <= 0:
                self.logger.warning("Invalid price received")
                return False
            
            # Create tick data object
            tick_obj = TickData(timestamp, price, self.symbol)
            
            # Update price tracking
            self.previous_price = self.current_price
            self.current_price = price
            self.last_update = timestamp
            self.tick_count += 1
            
            # Store tick data
            self.tick_history.append(tick_obj)
            self.price_history.append(price)
            self.timestamps.append(timestamp)
            
            # Calculate RSI
            rsi_value = self.rsi_calculator.add_price(price)
            
            # Update volatility
            self._update_volatility()
            
            # Update pattern detection
            self._update_patterns()
            
            # Update statistics
            self._update_stats(rsi_value)
            
            self.logger.debug(f"Processed tick: {price} (RSI: {rsi_value:.2f})")
            return True
            
        except Exception as e:
            self.logger.error(f"Error processing tick: {e}")
            return False
    
    def _update_volatility(self):
        """Update volatility calculation"""
        if len(self.price_history) < 2:
            return
        
        # Calculate price change
        price_change = self.current_price - self.previous_price
        self.price_changes.append(price_change)
        
        # Calculate volatility (standard deviation of price changes)
        if len(self.price_changes) >= 10:
            volatility = np.std(list(self.price_changes))
            self.stats.volatility = round_to_precision(volatility, 5)
    
    def _update_patterns(self):
        """Update pattern detection for consecutive moves"""
        if self.previous_price == 0:
            return
        
        # Determine move direction
        if self.current_price > self.previous_price:
            current_direction = 1  # Up
        elif self.current_price < self.previous_price:
            current_direction = -1  # Down
        else:
            current_direction = 0  # No change
        
        # Update consecutive moves counter
        if current_direction == self.last_move_direction and current_direction != 0:
            self.consecutive_moves += 1
        else:
            self.consecutive_moves = 1 if current_direction != 0 else 0
            self.last_move_direction = current_direction
    
    def _update_stats(self, rsi_value: float):
        """Update market statistics"""
        if self.previous_price > 0:
            price_change = self.current_price - self.previous_price
            price_change_pct = (price_change / self.previous_price) * 100
        else:
            price_change = 0.0
            price_change_pct = 0.0
        
        self.stats = MarketStats(
            current_price=self.current_price,
            price_change=round_to_precision(price_change, 5),
            price_change_pct=round_to_precision(price_change_pct, 3),
            volatility=self.stats.volatility,
            tick_count=self.tick_count,
            last_update=self.last_update
        )
    
    def get_rsi(self) -> float:
        """Get current RSI value"""
        return self.rsi_calculator.get_rsi()
    
    def is_rsi_ready(self) -> bool:
        """Check if RSI calculation is ready"""
        return self.rsi_calculator.is_ready()
    
    def get_recent_prices(self, count: int = 10) -> List[float]:
        """Get most recent prices"""
        if count > len(self.price_history):
            count = len(self.price_history)
        return list(self.price_history)[-count:] if count > 0 else []
    
    def get_recent_ticks(self, count: int = 10) -> List[TickData]:
        """Get most recent tick data"""
        if count > len(self.tick_history):
            count = len(self.tick_history)
        return list(self.tick_history)[-count:] if count > 0 else []
    
    def get_price_movement_stats(self, lookback: int = 20) -> Dict[str, Any]:
        """Get price movement statistics"""
        if len(self.price_history) < lookback:
            lookback = len(self.price_history)
        
        if lookback < 2:
            return {
                'avg_change': 0.0,
                'max_change': 0.0,
                'min_change': 0.0,
                'up_moves': 0,
                'down_moves': 0,
                'no_moves': 0
            }
        
        recent_prices = list(self.price_history)[-lookback:]
        changes = [recent_prices[i] - recent_prices[i-1] for i in range(1, len(recent_prices))]
        
        up_moves = sum(1 for change in changes if change > 0)
        down_moves = sum(1 for change in changes if change < 0)
        no_moves = sum(1 for change in changes if change == 0)
        
        return {
            'avg_change': round_to_precision(np.mean(changes), 5),
            'max_change': round_to_precision(max(changes), 5),
            'min_change': round_to_precision(min(changes), 5),
            'up_moves': up_moves,
            'down_moves': down_moves,
            'no_moves': no_moves
        }
    
    def detect_volatility_spike(self, threshold_multiplier: float = 2.0) -> bool:
        """Detect if current volatility is significantly higher than average"""
        if len(self.price_changes) < 20:
            return False
        
        recent_changes = list(self.price_changes)[-10:]  # Last 10 changes
        historical_changes = list(self.price_changes)[:-10]  # Earlier changes
        
        if not historical_changes:
            return False
        
        recent_volatility = np.std(recent_changes)
        historical_volatility = np.std(historical_changes)
        
        if historical_volatility == 0:
            return False
        
        return recent_volatility > (historical_volatility * threshold_multiplier)
    
    def get_consecutive_moves(self) -> Tuple[int, int]:
        """Get consecutive moves count and direction"""
        return self.consecutive_moves, self.last_move_direction
    
    def get_support_resistance_levels(self, lookback: int = 100) -> Dict[str, float]:
        """Calculate basic support and resistance levels"""
        if len(self.price_history) < lookback:
            lookback = len(self.price_history)
        
        if lookback < 10:
            return {
                'support': self.current_price,
                'resistance': self.current_price,
                'pivot': self.current_price
            }
        
        recent_prices = list(self.price_history)[-lookback:]
        
        # Simple support/resistance calculation
        high = max(recent_prices)
        low = min(recent_prices)
        pivot = (high + low + self.current_price) / 3
        
        return {
            'support': round_to_precision(low, 5),
            'resistance': round_to_precision(high, 5),
            'pivot': round_to_precision(pivot, 5)
        }
    
    def get_market_stats(self) -> MarketStats:
        """Get current market statistics"""
        return self.stats
    
    def get_data_summary(self) -> Dict[str, Any]:
        """Get comprehensive data summary"""
        consecutive_moves, move_direction = self.get_consecutive_moves()
        movement_stats = self.get_price_movement_stats()
        sr_levels = self.get_support_resistance_levels()
        
        return {
            'current_price': self.current_price,
            'rsi': self.get_rsi(),
            'rsi_ready': self.is_rsi_ready(),
            'volatility': self.stats.volatility,
            'consecutive_moves': consecutive_moves,
            'move_direction': move_direction,
            'tick_count': self.tick_count,
            'last_update': self.last_update,
            'volatility_spike': self.detect_volatility_spike(),
            'movement_stats': movement_stats,
            'support_resistance': sr_levels,
            'data_points': len(self.price_history)
        }
    
    def reset(self):
        """Reset all data and calculations"""
        self.tick_history.clear()
        self.price_history.clear()
        self.timestamps.clear()
        self.price_changes.clear()
        
        self.rsi_calculator = RSICalculator(self.rsi_calculator.period)
        
        self.current_price = 0.0
        self.previous_price = 0.0
        self.tick_count = 0
        self.last_update = 0.0
        self.consecutive_moves = 0
        self.last_move_direction = 0
        
        self.stats = MarketStats(0.0, 0.0, 0.0, 0.0, 0, 0.0)
        
        self.logger.info("Market data engine reset")