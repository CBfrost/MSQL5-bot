import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from enum import Enum
import numpy as np

from src.market_data import MarketDataEngine
from src.utils import get_current_timestamp, round_to_precision
from config.settings import TradingConfig

class SignalType(Enum):
    """Signal types for trading"""
    CALL = "CALL"  # Buy/Up signal
    PUT = "PUT"    # Sell/Down signal

class SignalStrength(Enum):
    """Signal strength levels"""
    WEAK = "WEAK"
    MODERATE = "MODERATE" 
    STRONG = "STRONG"
    VERY_STRONG = "VERY_STRONG"

@dataclass
class TradingSignal:
    """Trading signal with all relevant information"""
    signal_type: SignalType
    confidence: float  # 0.0 to 1.0
    strength: SignalStrength
    duration: int  # Recommended duration in ticks
    entry_price: float
    timestamp: float
    strategy: str  # Strategy that generated the signal
    rsi_value: float
    additional_data: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'signal_type': self.signal_type.value,
            'confidence': self.confidence,
            'strength': self.strength.value,
            'duration': self.duration,
            'entry_price': self.entry_price,
            'timestamp': self.timestamp,
            'strategy': self.strategy,
            'rsi_value': self.rsi_value,
            'additional_data': self.additional_data
        }

class ScalpingSignalGenerator:
    """Advanced signal generator for V10 1s scalping"""
    
    def __init__(self, config: TradingConfig):
        self.config = config
        self.logger = logging.getLogger('SignalGenerator')
        
        # Signal thresholds
        self.rsi_overbought = config.rsi_overbought
        self.rsi_oversold = config.rsi_oversold
        self.min_confidence = config.min_confidence
        
        # Advanced thresholds for different signal strengths
        self.rsi_extreme_overbought = 85  # Very strong PUT signals
        self.rsi_extreme_oversold = 15    # Very strong CALL signals
        self.rsi_strong_overbought = 80   # Strong PUT signals
        self.rsi_strong_oversold = 20     # Strong CALL signals
        
        # Momentum thresholds
        self.min_consecutive_moves = 5
        self.strong_consecutive_moves = 7
        self.extreme_consecutive_moves = 10
        
        # Volatility thresholds
        self.high_volatility_threshold = 2.0
        self.extreme_volatility_threshold = 3.0
        
        # Signal history for filtering
        self.recent_signals = []
        self.max_signal_history = 50
        
        # Performance tracking
        self.signals_generated = 0
        self.last_signal_time = 0.0
        self.min_signal_interval = 3.0  # Minimum seconds between signals
        
    def generate_signal(self, market_data: MarketDataEngine) -> Optional[TradingSignal]:
        """Generate trading signal based on current market conditions"""
        try:
            # Check if we have enough data
            if not market_data.is_rsi_ready():
                return None
            
            # Check minimum time interval between signals
            current_time = get_current_timestamp()
            if current_time - self.last_signal_time < self.min_signal_interval:
                return None
            
            # Get market data
            current_price = market_data.current_price
            rsi_value = market_data.get_rsi()
            consecutive_moves, move_direction = market_data.get_consecutive_moves()
            volatility_spike = market_data.detect_volatility_spike()
            
            # Try different strategies in order of priority
            signal = None
            
            # 1. RSI Extreme Reversal (Highest Priority)
            signal = self._rsi_extreme_strategy(current_price, rsi_value, market_data)
            if signal and signal.confidence >= self.min_confidence:
                return self._finalize_signal(signal)
            
            # 2. Momentum Exhaustion Strategy
            signal = self._momentum_exhaustion_strategy(
                current_price, rsi_value, consecutive_moves, move_direction, market_data
            )
            if signal and signal.confidence >= self.min_confidence:
                return self._finalize_signal(signal)
            
            # 3. RSI Mean Reversion Strategy
            signal = self._rsi_mean_reversion_strategy(current_price, rsi_value, market_data)
            if signal and signal.confidence >= self.min_confidence:
                return self._finalize_signal(signal)
            
            # 4. Volatility Spike Reversal
            if volatility_spike:
                signal = self._volatility_spike_strategy(current_price, rsi_value, market_data)
                if signal and signal.confidence >= self.min_confidence:
                    return self._finalize_signal(signal)
            
            return None
            
        except Exception as e:
            self.logger.error(f"Error generating signal: {e}")
            return None
    
    def _rsi_extreme_strategy(self, price: float, rsi: float, market_data: MarketDataEngine) -> Optional[TradingSignal]:
        """Generate signals for extreme RSI conditions"""
        signal = None
        confidence = 0.0
        strength = SignalStrength.WEAK
        duration = 3
        
        if rsi >= self.rsi_extreme_overbought:  # RSI >= 85
            confidence = min((rsi - self.rsi_extreme_overbought) / 15, 1.0)  # Scale 0-1
            strength = SignalStrength.VERY_STRONG
            duration = 3 + int(confidence * 5)  # 3-8 ticks
            
            signal = TradingSignal(
                signal_type=SignalType.PUT,
                confidence=round_to_precision(confidence, 3),
                strength=strength,
                duration=duration,
                entry_price=price,
                timestamp=get_current_timestamp(),
                strategy="RSI_EXTREME_OVERBOUGHT",
                rsi_value=rsi,
                additional_data={
                    'rsi_threshold': self.rsi_extreme_overbought,
                    'expected_reversal': 'DOWN'
                }
            )
            
        elif rsi <= self.rsi_extreme_oversold:  # RSI <= 15
            confidence = min((self.rsi_extreme_oversold - rsi) / 15, 1.0)  # Scale 0-1
            strength = SignalStrength.VERY_STRONG
            duration = 3 + int(confidence * 5)  # 3-8 ticks
            
            signal = TradingSignal(
                signal_type=SignalType.CALL,
                confidence=round_to_precision(confidence, 3),
                strength=strength,
                duration=duration,
                entry_price=price,
                timestamp=get_current_timestamp(),
                strategy="RSI_EXTREME_OVERSOLD",
                rsi_value=rsi,
                additional_data={
                    'rsi_threshold': self.rsi_extreme_oversold,
                    'expected_reversal': 'UP'
                }
            )
        
        return signal
    
    def _momentum_exhaustion_strategy(self, price: float, rsi: float, consecutive_moves: int, 
                                    move_direction: int, market_data: MarketDataEngine) -> Optional[TradingSignal]:
        """Generate signals based on momentum exhaustion"""
        if consecutive_moves < self.min_consecutive_moves:
            return None
        
        signal = None
        base_confidence = min((consecutive_moves - self.min_consecutive_moves) / 5, 0.8)  # Max 0.8 from momentum alone
        
        # RSI confirmation bonus
        rsi_bonus = 0.0
        if move_direction == 1 and rsi > 60:  # Up moves with high RSI
            rsi_bonus = min((rsi - 60) / 40, 0.2)  # Up to 0.2 bonus
        elif move_direction == -1 and rsi < 40:  # Down moves with low RSI
            rsi_bonus = min((40 - rsi) / 40, 0.2)  # Up to 0.2 bonus
        
        confidence = min(base_confidence + rsi_bonus, 1.0)
        
        # Determine signal strength based on consecutive moves
        if consecutive_moves >= self.extreme_consecutive_moves:
            strength = SignalStrength.VERY_STRONG
            duration = 5 + int(confidence * 3)  # 5-8 ticks
        elif consecutive_moves >= self.strong_consecutive_moves:
            strength = SignalStrength.STRONG
            duration = 4 + int(confidence * 3)  # 4-7 ticks
        else:
            strength = SignalStrength.MODERATE
            duration = 3 + int(confidence * 3)  # 3-6 ticks
        
        if move_direction == 1:  # Consecutive up moves - expect reversal down
            signal = TradingSignal(
                signal_type=SignalType.PUT,
                confidence=round_to_precision(confidence, 3),
                strength=strength,
                duration=duration,
                entry_price=price,
                timestamp=get_current_timestamp(),
                strategy="MOMENTUM_EXHAUSTION_UP",
                rsi_value=rsi,
                additional_data={
                    'consecutive_moves': consecutive_moves,
                    'move_direction': move_direction,
                    'rsi_bonus': rsi_bonus,
                    'expected_reversal': 'DOWN'
                }
            )
            
        elif move_direction == -1:  # Consecutive down moves - expect reversal up
            signal = TradingSignal(
                signal_type=SignalType.CALL,
                confidence=round_to_precision(confidence, 3),
                strength=strength,
                duration=duration,
                entry_price=price,
                timestamp=get_current_timestamp(),
                strategy="MOMENTUM_EXHAUSTION_DOWN",
                rsi_value=rsi,
                additional_data={
                    'consecutive_moves': consecutive_moves,
                    'move_direction': move_direction,
                    'rsi_bonus': rsi_bonus,
                    'expected_reversal': 'UP'
                }
            )
        
        return signal
    
    def _rsi_mean_reversion_strategy(self, price: float, rsi: float, market_data: MarketDataEngine) -> Optional[TradingSignal]:
        """Generate signals based on RSI mean reversion"""
        signal = None
        confidence = 0.0
        strength = SignalStrength.WEAK
        duration = 3
        
        if rsi >= self.rsi_strong_overbought:  # RSI >= 80
            confidence = min((rsi - self.rsi_strong_overbought) / 20, 0.9)  # Scale 0-0.9
            strength = SignalStrength.STRONG
            duration = 3 + int(confidence * 4)  # 3-7 ticks
            
            signal = TradingSignal(
                signal_type=SignalType.PUT,
                confidence=round_to_precision(confidence, 3),
                strength=strength,
                duration=duration,
                entry_price=price,
                timestamp=get_current_timestamp(),
                strategy="RSI_MEAN_REVERSION_OVERBOUGHT",
                rsi_value=rsi,
                additional_data={
                    'rsi_threshold': self.rsi_strong_overbought,
                    'expected_reversal': 'DOWN'
                }
            )
            
        elif rsi <= self.rsi_strong_oversold:  # RSI <= 20
            confidence = min((self.rsi_strong_oversold - rsi) / 20, 0.9)  # Scale 0-0.9
            strength = SignalStrength.STRONG
            duration = 3 + int(confidence * 4)  # 3-7 ticks
            
            signal = TradingSignal(
                signal_type=SignalType.CALL,
                confidence=round_to_precision(confidence, 3),
                strength=strength,
                duration=duration,
                entry_price=price,
                timestamp=get_current_timestamp(),
                strategy="RSI_MEAN_REVERSION_OVERSOLD",
                rsi_value=rsi,
                additional_data={
                    'rsi_threshold': self.rsi_strong_oversold,
                    'expected_reversal': 'UP'
                }
            )
            
        elif rsi >= self.rsi_overbought:  # RSI >= 70 (standard)
            confidence = min((rsi - self.rsi_overbought) / 10, 0.8)  # Scale 0-0.8, more sensitive
            strength = SignalStrength.MODERATE
            duration = 3 + int(confidence * 3)  # 3-6 ticks
            
            signal = TradingSignal(
                signal_type=SignalType.PUT,
                confidence=round_to_precision(confidence, 3),
                strength=strength,
                duration=duration,
                entry_price=price,
                timestamp=get_current_timestamp(),
                strategy="RSI_MEAN_REVERSION_MODERATE_OB",
                rsi_value=rsi,
                additional_data={
                    'rsi_threshold': self.rsi_overbought,
                    'expected_reversal': 'DOWN'
                }
            )
            
        elif rsi <= self.rsi_oversold:  # RSI <= 30 (standard)
            confidence = min((self.rsi_oversold - rsi) / 10, 0.8)  # Scale 0-0.8, more sensitive
            strength = SignalStrength.MODERATE
            duration = 3 + int(confidence * 3)  # 3-6 ticks
            
            signal = TradingSignal(
                signal_type=SignalType.CALL,
                confidence=round_to_precision(confidence, 3),
                strength=strength,
                duration=duration,
                entry_price=price,
                timestamp=get_current_timestamp(),
                strategy="RSI_MEAN_REVERSION_MODERATE_OS",
                rsi_value=rsi,
                additional_data={
                    'rsi_threshold': self.rsi_oversold,
                    'expected_reversal': 'UP'
                }
            )
        
        return signal
    
    def _volatility_spike_strategy(self, price: float, rsi: float, market_data: MarketDataEngine) -> Optional[TradingSignal]:
        """Generate signals based on volatility spikes (mean reversion)"""
        # Get recent price movement
        recent_prices = market_data.get_recent_prices(10)
        if len(recent_prices) < 5:
            return None
        
        # Calculate recent price change
        price_change = recent_prices[-1] - recent_prices[-5]
        price_change_pct = abs(price_change / recent_prices[-5]) * 100
        
        # Only consider significant moves
        if price_change_pct < 0.1:  # Less than 0.1% move
            return None
        
        # Base confidence from volatility spike
        base_confidence = min(price_change_pct / 0.5, 0.6)  # Max 0.6 from volatility
        
        # RSI confirmation
        rsi_confirmation = 0.0
        expected_direction = None
        
        if price_change > 0:  # Recent upward spike
            if rsi > 50:  # RSI supports reversal down
                rsi_confirmation = min((rsi - 50) / 50, 0.3)  # Up to 0.3 bonus
                expected_direction = 'DOWN'
                signal_type = SignalType.PUT
        else:  # Recent downward spike
            if rsi < 50:  # RSI supports reversal up
                rsi_confirmation = min((50 - rsi) / 50, 0.3)  # Up to 0.3 bonus
                expected_direction = 'UP'
                signal_type = SignalType.CALL
        
        if expected_direction is None:
            return None
        
        confidence = min(base_confidence + rsi_confirmation, 0.8)  # Max 0.8 for volatility strategy
        strength = SignalStrength.MODERATE if confidence > 0.5 else SignalStrength.WEAK
        duration = 4 + int(confidence * 2)  # 4-6 ticks
        
        return TradingSignal(
            signal_type=signal_type,
            confidence=round_to_precision(confidence, 3),
            strength=strength,
            duration=duration,
            entry_price=price,
            timestamp=get_current_timestamp(),
            strategy="VOLATILITY_SPIKE_REVERSAL",
            rsi_value=rsi,
            additional_data={
                'price_change': price_change,
                'price_change_pct': price_change_pct,
                'rsi_confirmation': rsi_confirmation,
                'expected_reversal': expected_direction
            }
        )
    
    def _finalize_signal(self, signal: TradingSignal) -> TradingSignal:
        """Finalize signal and update tracking"""
        # Add to signal history
        self.recent_signals.append(signal)
        if len(self.recent_signals) > self.max_signal_history:
            self.recent_signals.pop(0)
        
        # Update tracking
        self.signals_generated += 1
        self.last_signal_time = signal.timestamp
        
        # Log signal
        self.logger.info(
            f"Signal Generated: {signal.signal_type.value} "
            f"(Confidence: {signal.confidence:.3f}, "
            f"Strategy: {signal.strategy}, "
            f"RSI: {signal.rsi_value:.2f}, "
            f"Duration: {signal.duration})"
        )
        
        return signal
    
    def get_recent_signals(self, count: int = 10) -> List[TradingSignal]:
        """Get recent signals"""
        return self.recent_signals[-count:] if count <= len(self.recent_signals) else self.recent_signals.copy()
    
    def get_signal_stats(self) -> Dict[str, Any]:
        """Get signal generation statistics"""
        if not self.recent_signals:
            return {
                'total_signals': 0,
                'avg_confidence': 0.0,
                'call_signals': 0,
                'put_signals': 0,
                'strategy_breakdown': {}
            }
        
        call_signals = sum(1 for s in self.recent_signals if s.signal_type == SignalType.CALL)
        put_signals = sum(1 for s in self.recent_signals if s.signal_type == SignalType.PUT)
        avg_confidence = np.mean([s.confidence for s in self.recent_signals])
        
        # Strategy breakdown
        strategy_breakdown = {}
        for signal in self.recent_signals:
            strategy = signal.strategy
            if strategy not in strategy_breakdown:
                strategy_breakdown[strategy] = 0
            strategy_breakdown[strategy] += 1
        
        return {
            'total_signals': len(self.recent_signals),
            'avg_confidence': round_to_precision(avg_confidence, 3),
            'call_signals': call_signals,
            'put_signals': put_signals,
            'strategy_breakdown': strategy_breakdown,
            'signals_generated_total': self.signals_generated
        }
    
    def reset_signal_history(self):
        """Reset signal history"""
        self.recent_signals.clear()
        self.logger.info("Signal history reset")