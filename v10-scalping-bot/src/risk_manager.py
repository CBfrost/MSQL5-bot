import logging
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from enum import Enum
import json

from config.settings import RiskConfig, TradingConfig
from src.signal_generator import TradingSignal
from src.utils import get_current_timestamp, save_json_data, load_json_data

class RiskLevel(Enum):
    """Risk levels for different market conditions"""
    LOW = "LOW"
    MODERATE = "MODERATE"
    HIGH = "HIGH"
    EXTREME = "EXTREME"

class TradeDecision(Enum):
    """Trade decision outcomes"""
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REDUCED = "REDUCED"  # Approved but with reduced stake

@dataclass
class TradeRisk:
    """Risk assessment for a trade"""
    decision: TradeDecision
    recommended_stake: float
    risk_level: RiskLevel
    risk_score: float  # 0-100
    rejection_reasons: List[str]
    warnings: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'decision': self.decision.value,
            'recommended_stake': self.recommended_stake,
            'risk_level': self.risk_level.value,
            'risk_score': self.risk_score,
            'rejection_reasons': self.rejection_reasons,
            'warnings': self.warnings
        }

@dataclass
class TradingStats:
    """Trading statistics for risk assessment"""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    consecutive_losses: int = 0
    consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    total_profit_loss: float = 0.0
    daily_profit_loss: float = 0.0
    hourly_trades: int = 0
    last_trade_time: float = 0.0
    
    def win_rate(self) -> float:
        """Calculate win rate percentage"""
        if self.total_trades == 0:
            return 0.0
        return (self.winning_trades / self.total_trades) * 100
    
    def profit_factor(self) -> float:
        """Calculate profit factor (gross profit / gross loss)"""
        # This would need actual win/loss amounts to be accurate
        # For now, return a simplified version
        if self.losing_trades == 0:
            return float('inf') if self.winning_trades > 0 else 1.0
        return max(self.winning_trades / self.losing_trades, 0.1)

class RiskManager:
    """Comprehensive risk management system"""
    
    def __init__(self, risk_config: RiskConfig, trading_config: TradingConfig):
        self.risk_config = risk_config
        self.trading_config = trading_config
        self.logger = logging.getLogger('RiskManager')
        
        # Trading statistics
        self.stats = TradingStats()
        
        # Balance tracking
        self.initial_balance = 0.0
        self.current_balance = 0.0
        self.peak_balance = 0.0
        self.daily_start_balance = 0.0
        
        # Time-based tracking
        self.daily_reset_time = self._get_daily_reset_time()
        self.hourly_trade_count = 0
        self.hourly_reset_time = self._get_hourly_reset_time()
        
        # Risk state
        self.trading_paused = False
        self.pause_reason = ""
        self.pause_until = 0.0
        
        # Load persisted data
        self._load_risk_data()
        
    def assess_trade_risk(self, signal: TradingSignal, current_balance: float) -> TradeRisk:
        """Comprehensive trade risk assessment"""
        try:
            self.current_balance = current_balance
            self._update_peak_balance()
            self._check_daily_reset()
            self._check_hourly_reset()
            
            # Initialize risk assessment
            risk_score = 0.0
            warnings = []
            rejection_reasons = []
            recommended_stake = self.trading_config.max_stake
            
            # 1. Check if trading is paused
            if self.trading_paused:
                if get_current_timestamp() < self.pause_until:
                    rejection_reasons.append(f"Trading paused: {self.pause_reason}")
                    return TradeRisk(
                        TradeDecision.REJECTED, 0.0, RiskLevel.EXTREME, 100.0,
                        rejection_reasons, warnings
                    )
                else:
                    self._resume_trading()
            
            # 2. Balance checks
            balance_risk, balance_warnings, balance_rejections = self._assess_balance_risk()
            risk_score += balance_risk
            warnings.extend(balance_warnings)
            rejection_reasons.extend(balance_rejections)
            
            # 3. Daily loss limits
            daily_risk, daily_warnings, daily_rejections = self._assess_daily_risk()
            risk_score += daily_risk
            warnings.extend(daily_warnings)
            rejection_reasons.extend(daily_rejections)
            
            # 4. Consecutive loss limits
            consecutive_risk, consecutive_warnings, consecutive_rejections = self._assess_consecutive_risk()
            risk_score += consecutive_risk
            warnings.extend(consecutive_warnings)
            rejection_reasons.extend(consecutive_rejections)
            
            # 5. Trade frequency limits
            frequency_risk, frequency_warnings, frequency_rejections = self._assess_frequency_risk()
            risk_score += frequency_risk
            warnings.extend(frequency_warnings)
            rejection_reasons.extend(frequency_rejections)
            
            # 6. Drawdown limits
            drawdown_risk, drawdown_warnings, drawdown_rejections = self._assess_drawdown_risk()
            risk_score += drawdown_risk
            warnings.extend(drawdown_warnings)
            rejection_reasons.extend(drawdown_rejections)
            
            # 7. Signal quality assessment
            signal_risk, signal_warnings = self._assess_signal_risk(signal)
            risk_score += signal_risk
            warnings.extend(signal_warnings)
            
            # Determine decision based on risk assessment
            if rejection_reasons:
                decision = TradeDecision.REJECTED
                recommended_stake = 0.0
                risk_level = RiskLevel.EXTREME
            else:
                # Adjust stake based on risk score
                stake_multiplier = max(0.1, 1.0 - (risk_score / 100.0))
                recommended_stake = min(
                    recommended_stake * stake_multiplier,
                    self.trading_config.max_stake
                )
                
                # Determine risk level and decision
                if risk_score >= 75:
                    risk_level = RiskLevel.EXTREME
                    decision = TradeDecision.REJECTED
                    recommended_stake = 0.0
                    rejection_reasons.append("Risk score too high")
                elif risk_score >= 50:
                    risk_level = RiskLevel.HIGH
                    decision = TradeDecision.REDUCED if stake_multiplier < 0.8 else TradeDecision.APPROVED
                elif risk_score >= 25:
                    risk_level = RiskLevel.MODERATE
                    decision = TradeDecision.REDUCED if stake_multiplier < 0.9 else TradeDecision.APPROVED
                else:
                    risk_level = RiskLevel.LOW
                    decision = TradeDecision.APPROVED
            
            return TradeRisk(
                decision=decision,
                recommended_stake=round(recommended_stake, 2),
                risk_level=risk_level,
                risk_score=round(risk_score, 1),
                rejection_reasons=rejection_reasons,
                warnings=warnings
            )
            
        except Exception as e:
            self.logger.error(f"Error in risk assessment: {e}")
            return TradeRisk(
                TradeDecision.REJECTED, 0.0, RiskLevel.EXTREME, 100.0,
                [f"Risk assessment error: {str(e)}"], []
            )
    
    def _assess_balance_risk(self) -> Tuple[float, List[str], List[str]]:
        """Assess balance-related risks"""
        risk_score = 0.0
        warnings = []
        rejections = []
        
        # Minimum balance check
        if self.current_balance < self.risk_config.min_balance_to_trade:
            rejections.append(f"Balance too low: ${self.current_balance:.2f} < ${self.risk_config.min_balance_to_trade:.2f}")
            risk_score += 50.0
        elif self.current_balance < self.risk_config.min_balance_to_trade * 1.5:
            warnings.append("Balance approaching minimum threshold")
            risk_score += 20.0
        
        # Stake size vs balance
        stake_percentage = (self.trading_config.max_stake / self.current_balance) * 100
        if stake_percentage > 10:  # More than 10% of balance per trade
            warnings.append(f"High stake percentage: {stake_percentage:.1f}% of balance")
            risk_score += min(stake_percentage - 10, 25.0)
        
        return risk_score, warnings, rejections
    
    def _assess_daily_risk(self) -> Tuple[float, List[str], List[str]]:
        """Assess daily trading risks"""
        risk_score = 0.0
        warnings = []
        rejections = []
        
        # Daily loss limit
        if abs(self.stats.daily_profit_loss) >= self.risk_config.max_daily_loss:
            if self.stats.daily_profit_loss < 0:  # Actual loss
                rejections.append(f"Daily loss limit reached: ${abs(self.stats.daily_profit_loss):.2f}")
                risk_score += 50.0
        elif abs(self.stats.daily_profit_loss) >= self.risk_config.max_daily_loss * 0.8:
            warnings.append("Approaching daily loss limit")
            risk_score += 30.0
        elif abs(self.stats.daily_profit_loss) >= self.risk_config.max_daily_loss * 0.6:
            warnings.append("60% of daily loss limit used")
            risk_score += 15.0
        
        # Daily trade count
        daily_trades = self._get_daily_trade_count()
        if daily_trades >= self.risk_config.max_trades_per_day:
            rejections.append(f"Daily trade limit reached: {daily_trades}")
            risk_score += 30.0
        elif daily_trades >= self.risk_config.max_trades_per_day * 0.9:
            warnings.append("Approaching daily trade limit")
            risk_score += 15.0
        
        return risk_score, warnings, rejections
    
    def _assess_consecutive_risk(self) -> Tuple[float, List[str], List[str]]:
        """Assess consecutive loss risks"""
        risk_score = 0.0
        warnings = []
        rejections = []
        
        if self.stats.consecutive_losses >= self.risk_config.max_consecutive_losses:
            rejections.append(f"Consecutive loss limit reached: {self.stats.consecutive_losses}")
            risk_score += 40.0
        elif self.stats.consecutive_losses >= self.risk_config.max_consecutive_losses - 1:
            warnings.append("One loss away from consecutive loss limit")
            risk_score += 25.0
        elif self.stats.consecutive_losses >= self.risk_config.max_consecutive_losses - 2:
            warnings.append("Approaching consecutive loss limit")
            risk_score += 15.0
        
        return risk_score, warnings, rejections
    
    def _assess_frequency_risk(self) -> Tuple[float, List[str], List[str]]:
        """Assess trade frequency risks"""
        risk_score = 0.0
        warnings = []
        rejections = []
        
        if self.hourly_trade_count >= self.risk_config.max_trades_per_hour:
            rejections.append(f"Hourly trade limit reached: {self.hourly_trade_count}")
            risk_score += 25.0
        elif self.hourly_trade_count >= self.risk_config.max_trades_per_hour * 0.9:
            warnings.append("Approaching hourly trade limit")
            risk_score += 10.0
        
        return risk_score, warnings, rejections
    
    def _assess_drawdown_risk(self) -> Tuple[float, List[str], List[str]]:
        """Assess drawdown risks"""
        risk_score = 0.0
        warnings = []
        rejections = []
        
        if self.peak_balance > 0:
            current_drawdown = ((self.peak_balance - self.current_balance) / self.peak_balance) * 100
            
            if current_drawdown >= self.risk_config.max_drawdown_percent:
                rejections.append(f"Maximum drawdown exceeded: {current_drawdown:.1f}%")
                risk_score += 50.0
            elif current_drawdown >= self.risk_config.max_drawdown_percent * 0.8:
                warnings.append(f"High drawdown: {current_drawdown:.1f}%")
                risk_score += 30.0
            elif current_drawdown >= self.risk_config.max_drawdown_percent * 0.6:
                warnings.append(f"Moderate drawdown: {current_drawdown:.1f}%")
                risk_score += 15.0
        
        return risk_score, warnings, rejections
    
    def _assess_signal_risk(self, signal: TradingSignal) -> Tuple[float, List[str]]:
        """Assess signal quality risks"""
        risk_score = 0.0
        warnings = []
        
        # Low confidence signals
        if signal.confidence < 0.7:
            risk_score += (0.7 - signal.confidence) * 30  # Up to 21 points
            if signal.confidence < 0.6:
                warnings.append(f"Low confidence signal: {signal.confidence:.2f}")
        
        # Very short duration signals (higher risk)
        if signal.duration <= 3:
            risk_score += 5.0
            warnings.append("Very short duration signal")
        
        return risk_score, warnings
    
    def record_trade_result(self, profit_loss: float, was_winner: bool):
        """Record trade result and update statistics"""
        try:
            # Update basic stats
            self.stats.total_trades += 1
            self.stats.total_profit_loss += profit_loss
            self.stats.daily_profit_loss += profit_loss
            self.stats.last_trade_time = get_current_timestamp()
            self.hourly_trade_count += 1
            
            # Update win/loss tracking
            if was_winner:
                self.stats.winning_trades += 1
                self.stats.consecutive_wins += 1
                self.stats.consecutive_losses = 0
            else:
                self.stats.losing_trades += 1
                self.stats.consecutive_losses += 1
                self.stats.consecutive_wins = 0
                
                # Update max consecutive losses
                if self.stats.consecutive_losses > self.stats.max_consecutive_losses:
                    self.stats.max_consecutive_losses = self.stats.consecutive_losses
            
            # Check for automatic trading pause conditions
            self._check_auto_pause_conditions()
            
            # Save updated stats
            self._save_risk_data()
            
            self.logger.info(
                f"Trade recorded: P&L=${profit_loss:.2f}, "
                f"Win Rate: {self.stats.win_rate():.1f}%, "
                f"Consecutive: {self.stats.consecutive_losses} losses, {self.stats.consecutive_wins} wins"
            )
            
        except Exception as e:
            self.logger.error(f"Error recording trade result: {e}")
    
    def _check_auto_pause_conditions(self):
        """Check if trading should be automatically paused"""
        # Consecutive losses
        if self.stats.consecutive_losses >= self.risk_config.max_consecutive_losses:
            self._pause_trading(
                f"Consecutive loss limit reached: {self.stats.consecutive_losses}",
                self.risk_config.cooldown_minutes * 60
            )
        
        # Daily loss limit
        if abs(self.stats.daily_profit_loss) >= self.risk_config.max_daily_loss and self.stats.daily_profit_loss < 0:
            self._pause_trading(
                f"Daily loss limit reached: ${abs(self.stats.daily_profit_loss):.2f}",
                self._get_seconds_until_daily_reset()
            )
        
        # Drawdown limit
        if self.peak_balance > 0:
            current_drawdown = ((self.peak_balance - self.current_balance) / self.peak_balance) * 100
            if current_drawdown >= self.risk_config.max_drawdown_percent:
                self._pause_trading(
                    f"Maximum drawdown exceeded: {current_drawdown:.1f}%",
                    self.risk_config.cooldown_minutes * 60
                )
    
    def _pause_trading(self, reason: str, duration_seconds: int):
        """Pause trading for specified duration"""
        self.trading_paused = True
        self.pause_reason = reason
        self.pause_until = get_current_timestamp() + duration_seconds
        
        self.logger.warning(f"Trading paused: {reason} (Duration: {duration_seconds/60:.1f} minutes)")
    
    def _resume_trading(self):
        """Resume trading after pause period"""
        self.trading_paused = False
        self.pause_reason = ""
        self.pause_until = 0.0
        
        self.logger.info("Trading resumed after pause period")
    
    def force_resume_trading(self):
        """Manually resume trading (override pause)"""
        if self.trading_paused:
            self.logger.warning("Trading manually resumed (overriding pause)")
            self._resume_trading()
    
    def _update_peak_balance(self):
        """Update peak balance tracking"""
        if self.current_balance > self.peak_balance:
            self.peak_balance = self.current_balance
    
    def _get_daily_reset_time(self) -> float:
        """Get next daily reset time (midnight UTC)"""
        now = datetime.now(timezone.utc)
        next_midnight = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        return next_midnight.timestamp()
    
    def _get_hourly_reset_time(self) -> float:
        """Get next hourly reset time"""
        now = datetime.now(timezone.utc)
        next_hour = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        return next_hour.timestamp()
    
    def _check_daily_reset(self):
        """Check if daily stats should be reset"""
        current_time = get_current_timestamp()
        if current_time >= self.daily_reset_time:
            self.stats.daily_profit_loss = 0.0
            self.daily_start_balance = self.current_balance
            self.daily_reset_time = self._get_daily_reset_time()
            self.logger.info("Daily stats reset")
    
    def _check_hourly_reset(self):
        """Check if hourly stats should be reset"""
        current_time = get_current_timestamp()
        if current_time >= self.hourly_reset_time:
            self.hourly_trade_count = 0
            self.hourly_reset_time = self._get_hourly_reset_time()
    
    def _get_daily_trade_count(self) -> int:
        """Get number of trades today (simplified - would need trade history for accuracy)"""
        # This is a simplified version - in a real implementation,
        # you'd track trades with timestamps
        return self.stats.total_trades  # Placeholder
    
    def _get_seconds_until_daily_reset(self) -> int:
        """Get seconds until next daily reset"""
        return int(self.daily_reset_time - get_current_timestamp())
    
    def _save_risk_data(self):
        """Save risk management data to file"""
        try:
            data = {
                'stats': {
                    'total_trades': self.stats.total_trades,
                    'winning_trades': self.stats.winning_trades,
                    'losing_trades': self.stats.losing_trades,
                    'consecutive_losses': self.stats.consecutive_losses,
                    'consecutive_wins': self.stats.consecutive_wins,
                    'max_consecutive_losses': self.stats.max_consecutive_losses,
                    'total_profit_loss': self.stats.total_profit_loss,
                    'daily_profit_loss': self.stats.daily_profit_loss,
                    'last_trade_time': self.stats.last_trade_time
                },
                'balance_tracking': {
                    'initial_balance': self.initial_balance,
                    'peak_balance': self.peak_balance,
                    'daily_start_balance': self.daily_start_balance
                },
                'pause_state': {
                    'trading_paused': self.trading_paused,
                    'pause_reason': self.pause_reason,
                    'pause_until': self.pause_until
                }
            }
            
            save_json_data(data, 'data/risk_data.json')
            
        except Exception as e:
            self.logger.error(f"Error saving risk data: {e}")
    
    def _load_risk_data(self):
        """Load risk management data from file"""
        try:
            data = load_json_data('data/risk_data.json')
            if not data:
                return
            
            # Load stats
            if 'stats' in data:
                stats_data = data['stats']
                self.stats.total_trades = stats_data.get('total_trades', 0)
                self.stats.winning_trades = stats_data.get('winning_trades', 0)
                self.stats.losing_trades = stats_data.get('losing_trades', 0)
                self.stats.consecutive_losses = stats_data.get('consecutive_losses', 0)
                self.stats.consecutive_wins = stats_data.get('consecutive_wins', 0)
                self.stats.max_consecutive_losses = stats_data.get('max_consecutive_losses', 0)
                self.stats.total_profit_loss = stats_data.get('total_profit_loss', 0.0)
                self.stats.daily_profit_loss = stats_data.get('daily_profit_loss', 0.0)
                self.stats.last_trade_time = stats_data.get('last_trade_time', 0.0)
            
            # Load balance tracking
            if 'balance_tracking' in data:
                balance_data = data['balance_tracking']
                self.initial_balance = balance_data.get('initial_balance', 0.0)
                self.peak_balance = balance_data.get('peak_balance', 0.0)
                self.daily_start_balance = balance_data.get('daily_start_balance', 0.0)
            
            # Load pause state
            if 'pause_state' in data:
                pause_data = data['pause_state']
                self.trading_paused = pause_data.get('trading_paused', False)
                self.pause_reason = pause_data.get('pause_reason', '')
                self.pause_until = pause_data.get('pause_until', 0.0)
            
            self.logger.info("Risk data loaded successfully")
            
        except Exception as e:
            self.logger.error(f"Error loading risk data: {e}")
    
    def get_risk_summary(self) -> Dict[str, Any]:
        """Get comprehensive risk management summary"""
        current_drawdown = 0.0
        if self.peak_balance > 0:
            current_drawdown = ((self.peak_balance - self.current_balance) / self.peak_balance) * 100
        
        return {
            'trading_status': 'PAUSED' if self.trading_paused else 'ACTIVE',
            'pause_reason': self.pause_reason,
            'pause_until': self.pause_until,
            'balance': {
                'current': self.current_balance,
                'peak': self.peak_balance,
                'initial': self.initial_balance,
                'daily_start': self.daily_start_balance
            },
            'performance': {
                'total_trades': self.stats.total_trades,
                'win_rate': self.stats.win_rate(),
                'total_pnl': self.stats.total_profit_loss,
                'daily_pnl': self.stats.daily_profit_loss,
                'profit_factor': self.stats.profit_factor()
            },
            'risk_metrics': {
                'consecutive_losses': self.stats.consecutive_losses,
                'max_consecutive_losses': self.stats.max_consecutive_losses,
                'current_drawdown_pct': current_drawdown,
                'hourly_trade_count': self.hourly_trade_count
            },
            'limits': {
                'max_daily_loss': self.risk_config.max_daily_loss,
                'max_consecutive_losses': self.risk_config.max_consecutive_losses,
                'max_trades_per_hour': self.risk_config.max_trades_per_hour,
                'max_drawdown_percent': self.risk_config.max_drawdown_percent
            }
        }
    
    def reset_daily_stats(self):
        """Manually reset daily statistics"""
        self.stats.daily_profit_loss = 0.0
        self.daily_start_balance = self.current_balance
        self.logger.info("Daily stats manually reset")
    
    def reset_all_stats(self):
        """Reset all statistics (use with caution)"""
        self.stats = TradingStats()
        self.initial_balance = self.current_balance
        self.peak_balance = self.current_balance
        self.daily_start_balance = self.current_balance
        self.hourly_trade_count = 0
        self._resume_trading()
        self.logger.warning("All risk management stats reset")