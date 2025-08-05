#!/usr/bin/env python3
"""
Adaptive Backtesting System for V10 Scalping Bot
Continuously learns from live demo trading and optimizes strategies
"""

import asyncio
import json
import logging
import numpy as np
import pandas as pd
from collections import defaultdict, deque
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from pathlib import Path

from src.utils import get_current_timestamp, save_json_data, load_json_data
from src.signal_generator import TradingSignal, SignalType
from src.trade_executor import Trade

@dataclass
class StrategyPerformance:
    """Track performance metrics for each strategy"""
    strategy_name: str
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    total_profit: float = 0.0
    total_loss: float = 0.0
    win_rate: float = 0.0
    profit_factor: float = 0.0
    avg_win: float = 0.0
    avg_loss: float = 0.0
    max_consecutive_wins: int = 0
    max_consecutive_losses: int = 0
    current_streak: int = 0
    last_result: str = ""
    
    def update_performance(self):
        """Recalculate performance metrics"""
        if self.total_trades > 0:
            self.win_rate = (self.winning_trades / self.total_trades) * 100
            
        if self.winning_trades > 0:
            self.avg_win = self.total_profit / self.winning_trades
            
        if self.losing_trades > 0:
            self.avg_loss = abs(self.total_loss) / self.losing_trades
            
        if self.total_loss != 0:
            self.profit_factor = abs(self.total_profit / self.total_loss)
    
    def add_trade_result(self, profit_loss: float):
        """Add a trade result and update metrics"""
        self.total_trades += 1
        
        if profit_loss > 0:
            self.winning_trades += 1
            self.total_profit += profit_loss
            if self.last_result == "WIN":
                self.current_streak += 1
            else:
                self.current_streak = 1
            self.max_consecutive_wins = max(self.max_consecutive_wins, self.current_streak)
            self.last_result = "WIN"
        else:
            self.losing_trades += 1
            self.total_loss += profit_loss
            if self.last_result == "LOSS":
                self.current_streak += 1
            else:
                self.current_streak = 1
            self.max_consecutive_losses = max(self.max_consecutive_losses, self.current_streak)
            self.last_result = "LOSS"
        
        self.update_performance()
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        return asdict(self)

@dataclass
class MarketCondition:
    """Track market conditions for strategy optimization"""
    timestamp: float
    rsi: float
    volatility: float
    price: float
    price_change: float
    consecutive_moves: int
    market_regime: str  # "trending", "ranging", "volatile"
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

@dataclass
class StrategyOptimization:
    """Strategy parameter optimization results"""
    strategy_name: str
    optimal_params: Dict[str, Any]
    confidence_score: float
    sample_size: int
    last_optimization: float
    
    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

class AdaptiveBacktester:
    """
    Adaptive backtesting system that learns from live demo trading
    and continuously optimizes strategy parameters
    """
    
    def __init__(self, data_dir: str = "data"):
        self.logger = logging.getLogger('AdaptiveBacktester')
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        
        # Performance tracking
        self.strategy_performance: Dict[str, StrategyPerformance] = {}
        self.market_conditions: deque = deque(maxlen=1000)  # Last 1000 market states
        self.trade_history: List[Dict[str, Any]] = []
        
        # Optimization tracking
        self.strategy_optimizations: Dict[str, StrategyOptimization] = {}
        self.optimization_interval = 3600  # Optimize every hour
        self.min_trades_for_optimization = 20
        
        # Learning parameters
        self.learning_window = 100  # Trades to consider for learning
        self.confidence_threshold = 0.7  # Minimum confidence for strategy changes
        
        # Market regime detection
        self.market_regimes = {
            "ranging": {"rsi_range": (30, 70), "volatility_max": 0.3},
            "trending": {"consecutive_moves": 5, "price_change_min": 0.5},
            "volatile": {"volatility_min": 0.5, "rsi_extremes": True}
        }
        
        # Load existing data
        self.load_historical_data()
        
        self.logger.info("Adaptive backtester initialized")
    
    def load_historical_data(self):
        """Load historical performance and optimization data"""
        try:
            # Load strategy performance
            perf_file = self.data_dir / "strategy_performance.json"
            if perf_file.exists():
                data = load_json_data(str(perf_file))
                for strategy_name, perf_data in data.items():
                    self.strategy_performance[strategy_name] = StrategyPerformance(**perf_data)
                self.logger.info(f"Loaded performance data for {len(self.strategy_performance)} strategies")
            
            # Load optimizations
            opt_file = self.data_dir / "strategy_optimizations.json"
            if opt_file.exists():
                data = load_json_data(str(opt_file))
                for strategy_name, opt_data in data.items():
                    self.strategy_optimizations[strategy_name] = StrategyOptimization(**opt_data)
                self.logger.info(f"Loaded optimization data for {len(self.strategy_optimizations)} strategies")
            
            # Load trade history
            history_file = self.data_dir / "adaptive_trade_history.json"
            if history_file.exists():
                self.trade_history = load_json_data(str(history_file))
                self.logger.info(f"Loaded {len(self.trade_history)} historical trades")
                
        except Exception as e:
            self.logger.error(f"Error loading historical data: {e}")
    
    def save_data(self):
        """Save current performance and optimization data"""
        try:
            # Save strategy performance
            perf_data = {name: perf.to_dict() for name, perf in self.strategy_performance.items()}
            save_json_data(perf_data, str(self.data_dir / "strategy_performance.json"))
            
            # Save optimizations
            opt_data = {name: opt.to_dict() for name, opt in self.strategy_optimizations.items()}
            save_json_data(opt_data, str(self.data_dir / "strategy_optimizations.json"))
            
            # Save trade history (last 500 trades only)
            recent_history = self.trade_history[-500:] if len(self.trade_history) > 500 else self.trade_history
            save_json_data(recent_history, str(self.data_dir / "adaptive_trade_history.json"))
            
            self.logger.debug("Adaptive backtester data saved")
            
        except Exception as e:
            self.logger.error(f"Error saving backtester data: {e}")
    
    def detect_market_regime(self, rsi: float, volatility: float, price_change: float, consecutive_moves: int) -> str:
        """Detect current market regime based on conditions"""
        try:
            # Volatile market
            if volatility > self.market_regimes["volatile"]["volatility_min"] or rsi > 80 or rsi < 20:
                return "volatile"
            
            # Trending market
            if consecutive_moves >= self.market_regimes["trending"]["consecutive_moves"] and \
               abs(price_change) >= self.market_regimes["trending"]["price_change_min"]:
                return "trending"
            
            # Ranging market (default)
            return "ranging"
            
        except Exception as e:
            self.logger.error(f"Error detecting market regime: {e}")
            return "ranging"
    
    def add_market_condition(self, rsi: float, volatility: float, price: float, 
                           price_change: float, consecutive_moves: int):
        """Add current market condition for analysis"""
        try:
            regime = self.detect_market_regime(rsi, volatility, price_change, consecutive_moves)
            
            condition = MarketCondition(
                timestamp=get_current_timestamp(),
                rsi=rsi,
                volatility=volatility,
                price=price,
                price_change=price_change,
                consecutive_moves=consecutive_moves,
                market_regime=regime
            )
            
            self.market_conditions.append(condition)
            
        except Exception as e:
            self.logger.error(f"Error adding market condition: {e}")
    
    def add_trade_result(self, trade: Trade, signal: TradingSignal, market_condition: MarketCondition):
        """Add a completed trade result for learning"""
        try:
            strategy_name = signal.strategy
            
            # Initialize strategy performance if not exists
            if strategy_name not in self.strategy_performance:
                self.strategy_performance[strategy_name] = StrategyPerformance(strategy_name)
            
            # Update strategy performance
            profit_loss = trade.profit_loss or 0.0
            self.strategy_performance[strategy_name].add_trade_result(profit_loss)
            
            # Add to trade history
            trade_data = {
                'timestamp': trade.exit_time or get_current_timestamp(),
                'strategy': strategy_name,
                'signal_type': signal.signal_type.value,
                'confidence': signal.confidence,
                'rsi': signal.rsi_value,
                'duration': signal.duration,
                'stake': trade.stake,
                'profit_loss': profit_loss,
                'result': 'WIN' if profit_loss > 0 else 'LOSS',
                'market_regime': market_condition.market_regime,
                'volatility': market_condition.volatility,
                'consecutive_moves': market_condition.consecutive_moves
            }
            
            self.trade_history.append(trade_data)
            
            # Log significant results
            if len(self.trade_history) % 10 == 0:  # Every 10 trades
                self.logger.info(f"Strategy {strategy_name}: {self.strategy_performance[strategy_name].win_rate:.1f}% win rate "
                               f"({self.strategy_performance[strategy_name].total_trades} trades)")
            
            # Check if optimization is needed
            if self.should_optimize_strategy(strategy_name):
                # Schedule optimization for later to avoid blocking
                import threading
                threading.Thread(
                    target=lambda: asyncio.run(self.optimize_strategy(strategy_name)),
                    daemon=True
                ).start()
            
            # Save data periodically
            if len(self.trade_history) % 25 == 0:  # Every 25 trades
                self.save_data()
                
        except Exception as e:
            self.logger.error(f"Error adding trade result: {e}")
    
    def should_optimize_strategy(self, strategy_name: str) -> bool:
        """Check if strategy should be optimized"""
        try:
            perf = self.strategy_performance.get(strategy_name)
            if not perf or perf.total_trades < self.min_trades_for_optimization:
                return False
            
            # Check if enough time has passed since last optimization
            last_opt = self.strategy_optimizations.get(strategy_name)
            if last_opt:
                time_since_opt = get_current_timestamp() - last_opt.last_optimization
                if time_since_opt < self.optimization_interval:
                    return False
            
            # Optimize if performance is declining
            recent_trades = [t for t in self.trade_history[-20:] if t['strategy'] == strategy_name]
            if len(recent_trades) >= 10:
                recent_wins = sum(1 for t in recent_trades if t['result'] == 'WIN')
                recent_win_rate = (recent_wins / len(recent_trades)) * 100
                
                if recent_win_rate < perf.win_rate - 10:  # 10% drop
                    return True
            
            return perf.total_trades % 50 == 0  # Optimize every 50 trades
            
        except Exception as e:
            self.logger.error(f"Error checking optimization need: {e}")
            return False
    
    async def optimize_strategy(self, strategy_name: str):
        """Optimize strategy parameters based on historical performance"""
        try:
            self.logger.info(f"Optimizing strategy: {strategy_name}")
            
            # Get recent trades for this strategy
            strategy_trades = [t for t in self.trade_history if t['strategy'] == strategy_name]
            if len(strategy_trades) < self.min_trades_for_optimization:
                return
            
            # Analyze performance by market conditions
            performance_by_regime = defaultdict(list)
            performance_by_rsi = defaultdict(list)
            performance_by_confidence = defaultdict(list)
            
            for trade in strategy_trades[-self.learning_window:]:
                regime = trade['market_regime']
                rsi = trade['rsi']
                confidence = trade['confidence']
                result = 1 if trade['result'] == 'WIN' else 0
                
                performance_by_regime[regime].append(result)
                
                # RSI buckets
                rsi_bucket = "oversold" if rsi < 30 else "overbought" if rsi > 70 else "neutral"
                performance_by_rsi[rsi_bucket].append(result)
                
                # Confidence buckets
                conf_bucket = "high" if confidence > 0.8 else "medium" if confidence > 0.6 else "low"
                performance_by_confidence[conf_bucket].append(result)
            
            # Find optimal parameters
            optimal_params = {}
            confidence_score = 0.0
            
            # Best market regime
            best_regime = max(performance_by_regime.items(), 
                            key=lambda x: np.mean(x[1]) if x[1] else 0)
            if best_regime[1]:
                optimal_params['preferred_market_regime'] = best_regime[0]
                optimal_params['regime_win_rate'] = np.mean(best_regime[1]) * 100
                confidence_score += 0.3
            
            # Best RSI conditions
            best_rsi = max(performance_by_rsi.items(), 
                          key=lambda x: np.mean(x[1]) if x[1] else 0)
            if best_rsi[1]:
                optimal_params['best_rsi_condition'] = best_rsi[0]
                optimal_params['rsi_win_rate'] = np.mean(best_rsi[1]) * 100
                confidence_score += 0.3
            
            # Minimum confidence threshold
            best_confidence = max(performance_by_confidence.items(), 
                                key=lambda x: np.mean(x[1]) if x[1] else 0)
            if best_confidence[1]:
                optimal_params['min_confidence_threshold'] = best_confidence[0]
                optimal_params['confidence_win_rate'] = np.mean(best_confidence[1]) * 100
                confidence_score += 0.4
            
            # Calculate overall confidence
            total_trades = len(strategy_trades)
            if total_trades >= 50:
                confidence_score += 0.2
            elif total_trades >= 100:
                confidence_score += 0.4
            
            # Save optimization
            optimization = StrategyOptimization(
                strategy_name=strategy_name,
                optimal_params=optimal_params,
                confidence_score=min(confidence_score, 1.0),
                sample_size=total_trades,
                last_optimization=get_current_timestamp()
            )
            
            self.strategy_optimizations[strategy_name] = optimization
            
            self.logger.info(f"Strategy {strategy_name} optimized with confidence {confidence_score:.2f}")
            self.logger.info(f"Optimal parameters: {optimal_params}")
            
        except Exception as e:
            self.logger.error(f"Error optimizing strategy {strategy_name}: {e}")
    
    def get_strategy_recommendation(self, strategy_name: str, current_conditions: Dict[str, Any]) -> Dict[str, Any]:
        """Get recommendation for strategy based on current conditions"""
        try:
            optimization = self.strategy_optimizations.get(strategy_name)
            performance = self.strategy_performance.get(strategy_name)
            
            if not optimization or not performance:
                return {"action": "proceed", "confidence": 0.5, "reason": "insufficient_data"}
            
            recommendation = {
                "action": "proceed",
                "confidence": 0.5,
                "reason": "default",
                "adjustments": {}
            }
            
            # Check if current conditions match optimal parameters
            if optimization.confidence_score >= self.confidence_threshold:
                optimal = optimization.optimal_params
                
                # Market regime check
                if 'preferred_market_regime' in optimal:
                    current_regime = current_conditions.get('market_regime', 'ranging')
                    if current_regime == optimal['preferred_market_regime']:
                        recommendation["confidence"] += 0.2
                        recommendation["reason"] = f"optimal_market_regime_{current_regime}"
                    else:
                        recommendation["confidence"] -= 0.1
                        recommendation["reason"] = f"suboptimal_market_regime_{current_regime}"
                
                # RSI condition check
                if 'best_rsi_condition' in optimal:
                    current_rsi = current_conditions.get('rsi', 50)
                    rsi_condition = "oversold" if current_rsi < 30 else "overbought" if current_rsi > 70 else "neutral"
                    
                    if rsi_condition == optimal['best_rsi_condition']:
                        recommendation["confidence"] += 0.2
                    else:
                        recommendation["confidence"] -= 0.1
                
                # Performance-based adjustment
                if performance.win_rate > 60:
                    recommendation["confidence"] += 0.1
                elif performance.win_rate < 50:
                    recommendation["confidence"] -= 0.2
                
                # Recent performance check
                recent_trades = [t for t in self.trade_history[-10:] if t['strategy'] == strategy_name]
                if recent_trades:
                    recent_wins = sum(1 for t in recent_trades if t['result'] == 'WIN')
                    recent_win_rate = (recent_wins / len(recent_trades)) * 100
                    
                    if recent_win_rate < 30:  # Poor recent performance
                        recommendation["action"] = "pause"
                        recommendation["reason"] = "poor_recent_performance"
                        recommendation["confidence"] = 0.2
                    elif recent_win_rate > 70:  # Good recent performance
                        recommendation["confidence"] += 0.1
            
            # Ensure confidence is within bounds
            recommendation["confidence"] = max(0.0, min(1.0, recommendation["confidence"]))
            
            return recommendation
            
        except Exception as e:
            self.logger.error(f"Error getting strategy recommendation: {e}")
            return {"action": "proceed", "confidence": 0.5, "reason": "error"}
    
    def get_performance_summary(self) -> Dict[str, Any]:
        """Get comprehensive performance summary"""
        try:
            summary = {
                "total_strategies": len(self.strategy_performance),
                "total_trades": sum(p.total_trades for p in self.strategy_performance.values()),
                "overall_win_rate": 0.0,
                "best_strategy": None,
                "worst_strategy": None,
                "strategy_details": {},
                "market_regime_performance": {},
                "optimization_status": {},
                "learning_progress": {
                    "trades_analyzed": len(self.trade_history),
                    "strategies_optimized": len(self.strategy_optimizations),
                    "confidence_level": "building" if len(self.trade_history) < 100 else "moderate" if len(self.trade_history) < 500 else "high"
                }
            }
            
            if self.strategy_performance:
                # Calculate overall win rate
                total_wins = sum(p.winning_trades for p in self.strategy_performance.values())
                total_trades = sum(p.total_trades for p in self.strategy_performance.values())
                if total_trades > 0:
                    summary["overall_win_rate"] = (total_wins / total_trades) * 100
                
                # Find best and worst strategies
                strategies_by_performance = sorted(
                    self.strategy_performance.items(),
                    key=lambda x: x[1].win_rate,
                    reverse=True
                )
                
                if strategies_by_performance:
                    summary["best_strategy"] = {
                        "name": strategies_by_performance[0][0],
                        "win_rate": strategies_by_performance[0][1].win_rate,
                        "total_trades": strategies_by_performance[0][1].total_trades
                    }
                    
                    summary["worst_strategy"] = {
                        "name": strategies_by_performance[-1][0],
                        "win_rate": strategies_by_performance[-1][1].win_rate,
                        "total_trades": strategies_by_performance[-1][1].total_trades
                    }
                
                # Strategy details
                for name, perf in self.strategy_performance.items():
                    summary["strategy_details"][name] = perf.to_dict()
            
            # Market regime performance
            regime_performance = defaultdict(list)
            for trade in self.trade_history:
                regime = trade.get('market_regime', 'unknown')
                result = 1 if trade['result'] == 'WIN' else 0
                regime_performance[regime].append(result)
            
            for regime, results in regime_performance.items():
                if results:
                    summary["market_regime_performance"][regime] = {
                        "trades": len(results),
                        "win_rate": np.mean(results) * 100
                    }
            
            # Optimization status
            for name, opt in self.strategy_optimizations.items():
                summary["optimization_status"][name] = {
                    "confidence_score": opt.confidence_score,
                    "sample_size": opt.sample_size,
                    "last_optimization": opt.last_optimization,
                    "optimal_params": opt.optimal_params
                }
            
            return summary
            
        except Exception as e:
            self.logger.error(f"Error generating performance summary: {e}")
            return {"error": str(e)}
    
    def should_graduate_to_live_trading(self) -> Dict[str, Any]:
        """Determine if bot is ready for live trading"""
        try:
            summary = self.get_performance_summary()
            
            graduation_criteria = {
                "min_trades": 200,
                "min_win_rate": 60.0,
                "min_profit_factor": 1.2,
                "max_consecutive_losses": 8,
                "min_strategies_optimized": 2,
                "min_confidence_score": 0.7
            }
            
            results = {
                "ready": False,
                "criteria_met": {},
                "recommendations": [],
                "confidence_score": 0.0
            }
            
            # Check each criterion
            total_trades = summary.get("total_trades", 0)
            results["criteria_met"]["min_trades"] = total_trades >= graduation_criteria["min_trades"]
            
            overall_win_rate = summary.get("overall_win_rate", 0)
            results["criteria_met"]["min_win_rate"] = overall_win_rate >= graduation_criteria["min_win_rate"]
            
            # Check profit factor for best strategy
            best_strategy = summary.get("best_strategy")
            if best_strategy and best_strategy["name"] in self.strategy_performance:
                profit_factor = self.strategy_performance[best_strategy["name"]].profit_factor
                results["criteria_met"]["min_profit_factor"] = profit_factor >= graduation_criteria["min_profit_factor"]
            else:
                results["criteria_met"]["min_profit_factor"] = False
            
            # Check max consecutive losses
            max_consecutive_losses = 0
            for perf in self.strategy_performance.values():
                max_consecutive_losses = max(max_consecutive_losses, perf.max_consecutive_losses)
            results["criteria_met"]["max_consecutive_losses"] = max_consecutive_losses <= graduation_criteria["max_consecutive_losses"]
            
            # Check optimization status
            optimized_strategies = len(self.strategy_optimizations)
            results["criteria_met"]["min_strategies_optimized"] = optimized_strategies >= graduation_criteria["min_strategies_optimized"]
            
            # Check confidence scores
            avg_confidence = 0.0
            if self.strategy_optimizations:
                avg_confidence = np.mean([opt.confidence_score for opt in self.strategy_optimizations.values()])
            results["criteria_met"]["min_confidence_score"] = avg_confidence >= graduation_criteria["min_confidence_score"]
            
            # Calculate overall readiness
            criteria_met = sum(results["criteria_met"].values())
            total_criteria = len(graduation_criteria)
            results["confidence_score"] = criteria_met / total_criteria
            results["ready"] = criteria_met == total_criteria
            
            # Generate recommendations
            if not results["criteria_met"]["min_trades"]:
                results["recommendations"].append(f"Need {graduation_criteria['min_trades'] - total_trades} more trades")
            
            if not results["criteria_met"]["min_win_rate"]:
                results["recommendations"].append(f"Improve win rate to {graduation_criteria['min_win_rate']}% (current: {overall_win_rate:.1f}%)")
            
            if not results["criteria_met"]["min_profit_factor"]:
                results["recommendations"].append("Improve profit factor through better risk/reward ratio")
            
            if not results["criteria_met"]["max_consecutive_losses"]:
                results["recommendations"].append("Reduce maximum consecutive losses through better risk management")
            
            if not results["criteria_met"]["min_strategies_optimized"]:
                results["recommendations"].append("Continue trading to optimize more strategies")
            
            if not results["criteria_met"]["min_confidence_score"]:
                results["recommendations"].append("Build more confidence through consistent performance")
            
            if results["ready"]:
                results["recommendations"].append("🎉 Ready for live trading! Start with minimum stakes.")
            
            return results
            
        except Exception as e:
            self.logger.error(f"Error checking graduation criteria: {e}")
            return {"ready": False, "error": str(e)}
    
    async def generate_learning_report(self) -> str:
        """Generate a comprehensive learning report"""
        try:
            summary = self.get_performance_summary()
            graduation = self.should_graduate_to_live_trading()
            
            report = []
            report.append("=" * 60)
            report.append("🧠 ADAPTIVE LEARNING REPORT")
            report.append("=" * 60)
            
            # Overall performance
            report.append(f"📊 OVERALL PERFORMANCE:")
            report.append(f"   Total Trades: {summary.get('total_trades', 0)}")
            report.append(f"   Overall Win Rate: {summary.get('overall_win_rate', 0):.1f}%")
            report.append(f"   Strategies Tracked: {summary.get('total_strategies', 0)}")
            report.append(f"   Learning Progress: {summary['learning_progress']['confidence_level'].title()}")
            report.append("")
            
            # Best/Worst strategies
            if summary.get("best_strategy"):
                best = summary["best_strategy"]
                report.append(f"🏆 BEST STRATEGY: {best['name']}")
                report.append(f"   Win Rate: {best['win_rate']:.1f}%")
                report.append(f"   Total Trades: {best['total_trades']}")
                report.append("")
            
            if summary.get("worst_strategy"):
                worst = summary["worst_strategy"]
                report.append(f"📉 WORST STRATEGY: {worst['name']}")
                report.append(f"   Win Rate: {worst['win_rate']:.1f}%")
                report.append(f"   Total Trades: {worst['total_trades']}")
                report.append("")
            
            # Market regime performance
            if summary.get("market_regime_performance"):
                report.append("🌍 MARKET REGIME PERFORMANCE:")
                for regime, perf in summary["market_regime_performance"].items():
                    report.append(f"   {regime.title()}: {perf['win_rate']:.1f}% ({perf['trades']} trades)")
                report.append("")
            
            # Optimization status
            if summary.get("optimization_status"):
                report.append("⚙️ STRATEGY OPTIMIZATIONS:")
                for strategy, opt in summary["optimization_status"].items():
                    report.append(f"   {strategy}:")
                    report.append(f"     Confidence: {opt['confidence_score']:.2f}")
                    report.append(f"     Sample Size: {opt['sample_size']}")
                    if opt.get("optimal_params"):
                        report.append(f"     Best Conditions: {list(opt['optimal_params'].keys())}")
                report.append("")
            
            # Graduation status
            report.append("🎓 LIVE TRADING READINESS:")
            report.append(f"   Overall Readiness: {graduation['confidence_score']:.1%}")
            report.append(f"   Ready for Live Trading: {'YES ✅' if graduation['ready'] else 'NO ❌'}")
            report.append("")
            
            if graduation.get("recommendations"):
                report.append("📋 RECOMMENDATIONS:")
                for rec in graduation["recommendations"]:
                    report.append(f"   • {rec}")
                report.append("")
            
            report.append("=" * 60)
            
            # Save report
            report_text = "\n".join(report)
            report_file = self.data_dir / f"learning_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(report_file, 'w') as f:
                f.write(report_text)
            
            self.logger.info(f"Learning report saved: {report_file}")
            return report_text
            
        except Exception as e:
            self.logger.error(f"Error generating learning report: {e}")
            return f"Error generating report: {e}"

# Global backtester instance
adaptive_backtester = None

def get_adaptive_backtester() -> AdaptiveBacktester:
    """Get or create the global adaptive backtester instance"""
    global adaptive_backtester
    if adaptive_backtester is None:
        adaptive_backtester = AdaptiveBacktester()
    return adaptive_backtester