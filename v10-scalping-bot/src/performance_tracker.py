import logging
import json
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from datetime import datetime, timezone, timedelta
import numpy as np
from collections import defaultdict, deque

from src.trade_executor import Trade, TradeStatus
from src.utils import get_current_timestamp, save_json_data, load_json_data, calculate_percentage_change

@dataclass
class PerformanceMetrics:
    """Core performance metrics"""
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    total_pnl: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0
    profit_factor: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    max_win: float = 0.0
    max_loss: float = 0.0
    consecutive_wins: int = 0
    consecutive_losses: int = 0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class DrawdownMetrics:
    """Drawdown analysis metrics"""
    current_drawdown: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_duration: int = 0  # in trades
    recovery_factor: float = 0.0
    drawdown_periods: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class RiskMetrics:
    """Risk analysis metrics"""
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0
    volatility: float = 0.0
    var_95: float = 0.0  # Value at Risk 95%
    expected_shortfall: float = 0.0
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class TimeBasedMetrics:
    """Time-based performance metrics"""
    hourly_pnl: Dict[int, float]
    daily_pnl: Dict[str, float]
    weekly_pnl: Dict[str, float]
    monthly_pnl: Dict[str, float]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'hourly_pnl': self.hourly_pnl,
            'daily_pnl': self.daily_pnl,
            'weekly_pnl': self.weekly_pnl,
            'monthly_pnl': self.monthly_pnl
        }

class PerformanceTracker:
    """Comprehensive performance tracking and analytics"""
    
    def __init__(self, initial_balance: float = 0.0):
        self.logger = logging.getLogger('PerformanceTracker')
        
        # Balance tracking
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        self.peak_balance = initial_balance
        self.balance_history = deque(maxlen=10000)  # Keep last 10k balance points
        
        # Trade data
        self.trades: List[Trade] = []
        self.daily_trades: Dict[str, List[Trade]] = defaultdict(list)
        
        # Performance metrics
        self.metrics = PerformanceMetrics()
        self.drawdown_metrics = DrawdownMetrics()
        self.risk_metrics = RiskMetrics()
        
        # Time-based tracking
        self.time_metrics = TimeBasedMetrics(
            hourly_pnl=defaultdict(float),
            daily_pnl=defaultdict(float),
            weekly_pnl=defaultdict(float),
            monthly_pnl=defaultdict(float)
        )
        
        # Strategy performance
        self.strategy_performance: Dict[str, PerformanceMetrics] = defaultdict(PerformanceMetrics)
        
        # Real-time tracking
        self.last_update_time = get_current_timestamp()
        self.update_interval = 60  # Update summary every minute
        
        # Load historical data
        self._load_performance_data()
    
    def add_trade(self, trade: Trade):
        """Add a completed trade to performance tracking"""
        try:
            if trade.status not in [TradeStatus.WON, TradeStatus.LOST]:
                return  # Only track completed trades
            
            if trade.profit_loss is None:
                self.logger.warning(f"Trade {trade.trade_id} has no P&L data")
                return
            
            # Add to trade list
            self.trades.append(trade)
            
            # Update balance
            self.current_balance += trade.profit_loss
            self.balance_history.append({
                'timestamp': trade.exit_time or get_current_timestamp(),
                'balance': self.current_balance,
                'trade_id': trade.trade_id,
                'pnl': trade.profit_loss
            })
            
            # Update peak balance
            if self.current_balance > self.peak_balance:
                self.peak_balance = self.current_balance
            
            # Add to daily trades
            trade_date = datetime.fromtimestamp(trade.entry_time, timezone.utc).strftime('%Y-%m-%d')
            self.daily_trades[trade_date].append(trade)
            
            # Update all metrics
            self._update_performance_metrics()
            self._update_drawdown_metrics()
            self._update_time_based_metrics(trade)
            self._update_strategy_performance(trade)
            
            # Save updated data periodically
            current_time = get_current_timestamp()
            if current_time - self.last_update_time > self.update_interval:
                self._save_performance_data()
                self.last_update_time = current_time
            
            self.logger.debug(f"Added trade {trade.trade_id} to performance tracking")
            
        except Exception as e:
            self.logger.error(f"Error adding trade to performance tracker: {e}")
    
    def _update_performance_metrics(self):
        """Update core performance metrics"""
        if not self.trades:
            return
        
        # Basic counts
        self.metrics.total_trades = len(self.trades)
        winning_trades = [t for t in self.trades if t.profit_loss > 0]
        losing_trades = [t for t in self.trades if t.profit_loss < 0]
        
        self.metrics.winning_trades = len(winning_trades)
        self.metrics.losing_trades = len(losing_trades)
        
        # Win rate
        if self.metrics.total_trades > 0:
            self.metrics.win_rate = (self.metrics.winning_trades / self.metrics.total_trades) * 100
        
        # P&L calculations
        profits = [t.profit_loss for t in winning_trades]
        losses = [abs(t.profit_loss) for t in losing_trades]
        
        self.metrics.total_pnl = sum(t.profit_loss for t in self.trades)
        self.metrics.gross_profit = sum(profits) if profits else 0.0
        self.metrics.gross_loss = sum(losses) if losses else 0.0
        
        # Profit factor
        if self.metrics.gross_loss > 0:
            self.metrics.profit_factor = self.metrics.gross_profit / self.metrics.gross_loss
        else:
            self.metrics.profit_factor = float('inf') if self.metrics.gross_profit > 0 else 0.0
        
        # Average win/loss
        self.metrics.avg_win = np.mean(profits) if profits else 0.0
        self.metrics.avg_loss = np.mean(losses) if losses else 0.0
        self.metrics.max_win = max(profits) if profits else 0.0
        self.metrics.max_loss = max(losses) if losses else 0.0
        
        # Consecutive wins/losses
        self._calculate_consecutive_streaks()
    
    def _calculate_consecutive_streaks(self):
        """Calculate consecutive win/loss streaks"""
        if not self.trades:
            return
        
        current_win_streak = 0
        current_loss_streak = 0
        max_win_streak = 0
        max_loss_streak = 0
        
        for trade in self.trades:
            if trade.profit_loss > 0:  # Win
                current_win_streak += 1
                current_loss_streak = 0
                max_win_streak = max(max_win_streak, current_win_streak)
            else:  # Loss
                current_loss_streak += 1
                current_win_streak = 0
                max_loss_streak = max(max_loss_streak, current_loss_streak)
        
        self.metrics.consecutive_wins = current_win_streak
        self.metrics.consecutive_losses = current_loss_streak
        self.metrics.max_consecutive_wins = max_win_streak
        self.metrics.max_consecutive_losses = max_loss_streak
    
    def _update_drawdown_metrics(self):
        """Update drawdown analysis"""
        if not self.balance_history:
            return
        
        # Calculate current drawdown
        current_drawdown = 0.0
        if self.peak_balance > 0:
            current_drawdown = ((self.peak_balance - self.current_balance) / self.peak_balance) * 100
        
        self.drawdown_metrics.current_drawdown = current_drawdown
        
        # Calculate maximum drawdown
        balances = [point['balance'] for point in self.balance_history]
        if len(balances) > 1:
            peak = balances[0]
            max_dd = 0.0
            dd_duration = 0
            current_dd_duration = 0
            max_dd_duration = 0
            
            for balance in balances[1:]:
                if balance > peak:
                    peak = balance
                    current_dd_duration = 0
                else:
                    current_dd_duration += 1
                    drawdown = ((peak - balance) / peak) * 100
                    if drawdown > max_dd:
                        max_dd = drawdown
                    max_dd_duration = max(max_dd_duration, current_dd_duration)
            
            self.drawdown_metrics.max_drawdown = max_dd
            self.drawdown_metrics.max_drawdown_duration = max_dd_duration
    
    def _update_time_based_metrics(self, trade: Trade):
        """Update time-based performance metrics"""
        if not trade.exit_time or trade.profit_loss is None:
            return
        
        trade_datetime = datetime.fromtimestamp(trade.exit_time, timezone.utc)
        
        # Hourly P&L
        hour = trade_datetime.hour
        self.time_metrics.hourly_pnl[hour] += trade.profit_loss
        
        # Daily P&L
        date_str = trade_datetime.strftime('%Y-%m-%d')
        self.time_metrics.daily_pnl[date_str] += trade.profit_loss
        
        # Weekly P&L
        week_str = trade_datetime.strftime('%Y-W%U')
        self.time_metrics.weekly_pnl[week_str] += trade.profit_loss
        
        # Monthly P&L
        month_str = trade_datetime.strftime('%Y-%m')
        self.time_metrics.monthly_pnl[month_str] += trade.profit_loss
    
    def _update_strategy_performance(self, trade: Trade):
        """Update per-strategy performance metrics"""
        strategy = trade.signal.strategy
        
        if strategy not in self.strategy_performance:
            self.strategy_performance[strategy] = PerformanceMetrics()
        
        metrics = self.strategy_performance[strategy]
        metrics.total_trades += 1
        
        if trade.profit_loss > 0:
            metrics.winning_trades += 1
            metrics.gross_profit += trade.profit_loss
        else:
            metrics.losing_trades += 1
            metrics.gross_loss += abs(trade.profit_loss)
        
        metrics.total_pnl += trade.profit_loss
        
        # Update win rate
        if metrics.total_trades > 0:
            metrics.win_rate = (metrics.winning_trades / metrics.total_trades) * 100
        
        # Update profit factor
        if metrics.gross_loss > 0:
            metrics.profit_factor = metrics.gross_profit / metrics.gross_loss
        else:
            metrics.profit_factor = float('inf') if metrics.gross_profit > 0 else 0.0
    
    def calculate_risk_metrics(self):
        """Calculate advanced risk metrics"""
        if len(self.trades) < 10:  # Need minimum trades for meaningful metrics
            return
        
        try:
            # Get returns (P&L as percentage of balance at trade time)
            returns = []
            balance = self.initial_balance
            
            for trade in self.trades:
                if balance > 0:
                    return_pct = (trade.profit_loss / balance) * 100
                    returns.append(return_pct)
                    balance += trade.profit_loss
            
            if not returns:
                return
            
            returns_array = np.array(returns)
            
            # Volatility (standard deviation of returns)
            self.risk_metrics.volatility = np.std(returns_array)
            
            # Sharpe Ratio (assuming risk-free rate of 0)
            mean_return = np.mean(returns_array)
            if self.risk_metrics.volatility > 0:
                self.risk_metrics.sharpe_ratio = mean_return / self.risk_metrics.volatility
            
            # Sortino Ratio (downside deviation)
            negative_returns = returns_array[returns_array < 0]
            if len(negative_returns) > 0:
                downside_deviation = np.std(negative_returns)
                if downside_deviation > 0:
                    self.risk_metrics.sortino_ratio = mean_return / downside_deviation
            
            # Calmar Ratio
            if self.drawdown_metrics.max_drawdown > 0:
                annualized_return = mean_return * 252  # Assuming daily trading
                self.risk_metrics.calmar_ratio = annualized_return / self.drawdown_metrics.max_drawdown
            
            # Value at Risk (95th percentile)
            self.risk_metrics.var_95 = np.percentile(returns_array, 5)
            
            # Expected Shortfall (average of worst 5% returns)
            worst_5_percent = returns_array[returns_array <= self.risk_metrics.var_95]
            if len(worst_5_percent) > 0:
                self.risk_metrics.expected_shortfall = np.mean(worst_5_percent)
                
        except Exception as e:
            self.logger.error(f"Error calculating risk metrics: {e}")
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary"""
        # Update risk metrics
        self.calculate_risk_metrics()
        
        # Calculate additional metrics
        roi = 0.0
        if self.initial_balance > 0:
            roi = ((self.current_balance - self.initial_balance) / self.initial_balance) * 100
        
        # Recent performance (last 10 trades)
        recent_trades = self.trades[-10:] if len(self.trades) >= 10 else self.trades
        recent_pnl = sum(t.profit_loss for t in recent_trades if t.profit_loss is not None)
        recent_win_rate = 0.0
        if recent_trades:
            recent_wins = sum(1 for t in recent_trades if t.profit_loss > 0)
            recent_win_rate = (recent_wins / len(recent_trades)) * 100
        
        return {
            'balance_info': {
                'initial_balance': self.initial_balance,
                'current_balance': self.current_balance,
                'peak_balance': self.peak_balance,
                'total_return': self.metrics.total_pnl,
                'roi_percent': roi
            },
            'performance_metrics': self.metrics.to_dict(),
            'drawdown_metrics': self.drawdown_metrics.to_dict(),
            'risk_metrics': self.risk_metrics.to_dict(),
            'recent_performance': {
                'last_10_trades_pnl': recent_pnl,
                'last_10_trades_win_rate': recent_win_rate,
                'trades_today': len(self.get_today_trades()),
                'today_pnl': self.get_today_pnl()
            },
            'time_analysis': {
                'best_hour': self._get_best_hour(),
                'worst_hour': self._get_worst_hour(),
                'best_day': self._get_best_day(),
                'worst_day': self._get_worst_day()
            },
            'strategy_breakdown': {
                strategy: metrics.to_dict() 
                for strategy, metrics in self.strategy_performance.items()
            }
        }
    
    def get_today_trades(self) -> List[Trade]:
        """Get today's trades"""
        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        return self.daily_trades.get(today, [])
    
    def get_today_pnl(self) -> float:
        """Get today's P&L"""
        today_trades = self.get_today_trades()
        return sum(t.profit_loss for t in today_trades if t.profit_loss is not None)
    
    def _get_best_hour(self) -> Tuple[int, float]:
        """Get the most profitable hour"""
        if not self.time_metrics.hourly_pnl:
            return 0, 0.0
        
        best_hour = max(self.time_metrics.hourly_pnl.items(), key=lambda x: x[1])
        return best_hour
    
    def _get_worst_hour(self) -> Tuple[int, float]:
        """Get the least profitable hour"""
        if not self.time_metrics.hourly_pnl:
            return 0, 0.0
        
        worst_hour = min(self.time_metrics.hourly_pnl.items(), key=lambda x: x[1])
        return worst_hour
    
    def _get_best_day(self) -> Tuple[str, float]:
        """Get the most profitable day"""
        if not self.time_metrics.daily_pnl:
            return "", 0.0
        
        best_day = max(self.time_metrics.daily_pnl.items(), key=lambda x: x[1])
        return best_day
    
    def _get_worst_day(self) -> Tuple[str, float]:
        """Get the least profitable day"""
        if not self.time_metrics.daily_pnl:
            return "", 0.0
        
        worst_day = min(self.time_metrics.daily_pnl.items(), key=lambda x: x[1])
        return worst_day
    
    def generate_daily_report(self, date: Optional[str] = None) -> Dict[str, Any]:
        """Generate detailed daily performance report"""
        if date is None:
            date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        
        daily_trades = self.daily_trades.get(date, [])
        
        if not daily_trades:
            return {
                'date': date,
                'no_trades': True,
                'message': 'No trades executed on this date'
            }
        
        # Calculate daily metrics
        total_pnl = sum(t.profit_loss for t in daily_trades if t.profit_loss is not None)
        wins = sum(1 for t in daily_trades if t.profit_loss > 0)
        losses = sum(1 for t in daily_trades if t.profit_loss < 0)
        win_rate = (wins / len(daily_trades)) * 100 if daily_trades else 0
        
        # Strategy breakdown
        strategy_stats = defaultdict(lambda: {'trades': 0, 'pnl': 0.0, 'wins': 0})
        for trade in daily_trades:
            strategy = trade.signal.strategy
            strategy_stats[strategy]['trades'] += 1
            strategy_stats[strategy]['pnl'] += trade.profit_loss or 0
            if trade.profit_loss > 0:
                strategy_stats[strategy]['wins'] += 1
        
        return {
            'date': date,
            'summary': {
                'total_trades': len(daily_trades),
                'winning_trades': wins,
                'losing_trades': losses,
                'win_rate': win_rate,
                'total_pnl': total_pnl,
                'avg_pnl_per_trade': total_pnl / len(daily_trades) if daily_trades else 0
            },
            'strategy_breakdown': dict(strategy_stats),
            'trades': [trade.to_dict() for trade in daily_trades]
        }
    
    def _save_performance_data(self):
        """Save performance data to files"""
        try:
            # Save main performance summary
            summary = self.get_performance_summary()
            save_json_data(summary, 'data/performance_summary.json')
            
            # Save balance history
            balance_data = {
                'initial_balance': self.initial_balance,
                'current_balance': self.current_balance,
                'peak_balance': self.peak_balance,
                'history': list(self.balance_history)
            }
            save_json_data(balance_data, 'data/balance_history.json')
            
            # Save time-based metrics
            save_json_data(self.time_metrics.to_dict(), 'data/time_metrics.json')
            
            self.logger.debug("Performance data saved successfully")
            
        except Exception as e:
            self.logger.error(f"Error saving performance data: {e}")
    
    def _load_performance_data(self):
        """Load historical performance data"""
        try:
            # Load balance history
            balance_data = load_json_data('data/balance_history.json')
            if balance_data:
                self.initial_balance = balance_data.get('initial_balance', 0.0)
                self.current_balance = balance_data.get('current_balance', 0.0)
                self.peak_balance = balance_data.get('peak_balance', 0.0)
                
                history = balance_data.get('history', [])
                for point in history:
                    self.balance_history.append(point)
            
            # Load time metrics
            time_data = load_json_data('data/time_metrics.json')
            if time_data:
                self.time_metrics.hourly_pnl.update(time_data.get('hourly_pnl', {}))
                self.time_metrics.daily_pnl.update(time_data.get('daily_pnl', {}))
                self.time_metrics.weekly_pnl.update(time_data.get('weekly_pnl', {}))
                self.time_metrics.monthly_pnl.update(time_data.get('monthly_pnl', {}))
            
            self.logger.info("Performance data loaded successfully")
            
        except Exception as e:
            self.logger.error(f"Error loading performance data: {e}")
    
    def reset_performance_data(self):
        """Reset all performance data (use with caution)"""
        self.trades.clear()
        self.daily_trades.clear()
        self.balance_history.clear()
        self.strategy_performance.clear()
        
        self.current_balance = self.initial_balance
        self.peak_balance = self.initial_balance
        
        self.metrics = PerformanceMetrics()
        self.drawdown_metrics = DrawdownMetrics()
        self.risk_metrics = RiskMetrics()
        
        self.time_metrics = TimeBasedMetrics(
            hourly_pnl=defaultdict(float),
            daily_pnl=defaultdict(float),
            weekly_pnl=defaultdict(float),
            monthly_pnl=defaultdict(float)
        )
        
        self.logger.warning("All performance data has been reset")
    
    def export_performance_report(self, filename: Optional[str] = None) -> str:
        """Export comprehensive performance report"""
        if filename is None:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'data/performance_report_{timestamp}.json'
        
        report = {
            'generated_at': get_current_timestamp(),
            'report_period': {
                'start_date': min(t.entry_time for t in self.trades) if self.trades else None,
                'end_date': max(t.exit_time for t in self.trades if t.exit_time) if self.trades else None,
                'total_days': None  # Could calculate this
            },
            'performance_summary': self.get_performance_summary(),
            'daily_reports': {
                date: self.generate_daily_report(date) 
                for date in sorted(self.daily_trades.keys())
            }
        }
        
        save_json_data(report, filename)
        self.logger.info(f"Performance report exported to {filename}")
        return filename