#!/usr/bin/env python3
"""
Demo Trading Validator for V10 Scalping Bot
Ensures safe demo trading and validates graduation to live trading
"""

import logging
import os
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from pathlib import Path

from src.utils import get_current_timestamp, save_json_data, load_json_data

class DemoTradingValidator:
    """
    Validates demo trading environment and manages graduation to live trading
    """
    
    def __init__(self):
        self.logger = logging.getLogger('DemoTradingValidator')
        self.validation_file = Path("data/demo_validation.json")
        
        # Demo trading requirements
        self.demo_requirements = {
            "min_demo_days": 7,  # Minimum 7 days of demo trading
            "min_demo_trades": 100,  # Minimum 100 demo trades
            "min_win_rate": 55.0,  # Minimum 55% win rate
            "max_daily_loss_breaches": 2,  # Max 2 daily loss limit breaches
            "max_consecutive_losses": 10,  # Max 10 consecutive losses
            "min_profit_factor": 1.1,  # Minimum profit factor
            "required_balance_growth": 10.0,  # Minimum 10% balance growth
        }
        
        # Load existing validation data
        self.validation_data = self.load_validation_data()
        
        self.logger.info("Demo trading validator initialized")
    
    def load_validation_data(self) -> Dict[str, Any]:
        """Load existing validation data"""
        try:
            if self.validation_file.exists():
                data = load_json_data(str(self.validation_file))
                self.logger.info("Loaded existing demo validation data")
                return data
            else:
                # Initialize new validation data
                data = {
                    "demo_start_date": get_current_timestamp(),
                    "demo_end_date": None,
                    "total_demo_trades": 0,
                    "demo_balance_start": 0.0,
                    "demo_balance_current": 0.0,
                    "daily_loss_breaches": 0,
                    "consecutive_losses_max": 0,
                    "validation_passed": False,
                    "graduation_date": None,
                    "validation_notes": []
                }
                self.save_validation_data(data)
                return data
        except Exception as e:
            self.logger.error(f"Error loading validation data: {e}")
            return {}
    
    def save_validation_data(self, data: Dict[str, Any]):
        """Save validation data"""
        try:
            Path("data").mkdir(exist_ok=True)
            save_json_data(data, str(self.validation_file))
        except Exception as e:
            self.logger.error(f"Error saving validation data: {e}")
    
    def is_demo_account(self) -> bool:
        """Check if current account is demo account"""
        try:
            # Check environment variables for demo indicators
            api_token = os.getenv('DERIV_API_TOKEN', '')
            
            # Demo tokens typically contain 'demo' or are shorter
            if 'demo' in api_token.lower():
                return True
            
            # Demo tokens are usually shorter than live tokens
            if len(api_token) < 20:
                return True
            
            # Additional checks can be added here
            return False
            
        except Exception as e:
            self.logger.error(f"Error checking demo account: {e}")
            return False
    
    def validate_demo_environment(self) -> Dict[str, Any]:
        """Validate that we're in a safe demo environment"""
        validation_result = {
            "is_safe": False,
            "is_demo": False,
            "warnings": [],
            "errors": []
        }
        
        try:
            # Check if demo account
            validation_result["is_demo"] = self.is_demo_account()
            
            if not validation_result["is_demo"]:
                validation_result["errors"].append("NOT USING DEMO ACCOUNT - LIVE TRADING DETECTED!")
                validation_result["warnings"].append("Switch to demo account before testing")
                return validation_result
            
            # Check API token
            api_token = os.getenv('DERIV_API_TOKEN', '')
            if not api_token:
                validation_result["errors"].append("No API token configured")
                return validation_result
            
            # Check app ID
            app_id = os.getenv('DERIV_APP_ID', '')
            if not app_id:
                validation_result["warnings"].append("No app ID configured, using default")
            
            # Check balance limits for demo
            max_stake = float(os.getenv('MAX_STAKE', '0.25'))
            if max_stake > 1.0:
                validation_result["warnings"].append(f"High max stake for demo: ${max_stake}")
            
            # All checks passed
            validation_result["is_safe"] = True
            self.logger.info("Demo environment validation passed")
            
        except Exception as e:
            validation_result["errors"].append(f"Validation error: {e}")
            self.logger.error(f"Demo environment validation failed: {e}")
        
        return validation_result
    
    def update_demo_progress(self, balance: float, total_trades: int, 
                           daily_loss_breaches: int, max_consecutive_losses: int):
        """Update demo trading progress"""
        try:
            # Initialize demo balance if not set
            if self.validation_data.get("demo_balance_start", 0.0) == 0.0:
                self.validation_data["demo_balance_start"] = balance
            
            # Update current progress
            self.validation_data["demo_balance_current"] = balance
            self.validation_data["total_demo_trades"] = total_trades
            self.validation_data["daily_loss_breaches"] = daily_loss_breaches
            self.validation_data["consecutive_losses_max"] = max_consecutive_losses
            
            # Save progress
            self.save_validation_data(self.validation_data)
            
        except Exception as e:
            self.logger.error(f"Error updating demo progress: {e}")
    
    def should_graduate_to_live_trading(self) -> Dict[str, Any]:
        """Determine if bot is ready for live trading - alias for check_graduation_criteria"""
        # Get current performance summary from adaptive backtester
        try:
            from src.adaptive_backtester import get_adaptive_backtester
            adaptive_backtester = get_adaptive_backtester()
            performance_summary = adaptive_backtester.get_performance_summary()
            return self.check_graduation_criteria(performance_summary)
        except Exception as e:
            self.logger.error(f"Error in graduation check: {e}")
            return {"ready": False, "error": str(e)}
    
    def check_graduation_criteria(self, performance_summary: Dict[str, Any]) -> Dict[str, Any]:
        """Check if bot meets graduation criteria for live trading"""
        try:
            graduation_result = {
                "ready_for_live": False,
                "criteria_met": {},
                "criteria_failed": {},
                "overall_score": 0.0,
                "recommendations": []
            }
            
            # Check demo duration
            demo_start = self.validation_data.get("demo_start_date", get_current_timestamp())
            days_in_demo = (get_current_timestamp() - demo_start) / (24 * 3600)
            
            graduation_result["criteria_met"]["demo_duration"] = days_in_demo >= self.demo_requirements["min_demo_days"]
            if not graduation_result["criteria_met"]["demo_duration"]:
                graduation_result["criteria_failed"]["demo_duration"] = f"Need {self.demo_requirements['min_demo_days'] - days_in_demo:.1f} more days"
            
            # Check trade count
            total_trades = performance_summary.get("performance_metrics", {}).get("total_trades", 0)
            graduation_result["criteria_met"]["trade_count"] = total_trades >= self.demo_requirements["min_demo_trades"]
            if not graduation_result["criteria_met"]["trade_count"]:
                graduation_result["criteria_failed"]["trade_count"] = f"Need {self.demo_requirements['min_demo_trades'] - total_trades} more trades"
            
            # Check win rate
            win_rate = performance_summary.get("performance_metrics", {}).get("win_rate", 0.0)
            graduation_result["criteria_met"]["win_rate"] = win_rate >= self.demo_requirements["min_win_rate"]
            if not graduation_result["criteria_met"]["win_rate"]:
                graduation_result["criteria_failed"]["win_rate"] = f"Need {self.demo_requirements['min_win_rate'] - win_rate:.1f}% improvement"
            
            # Check daily loss breaches
            daily_breaches = self.validation_data.get("daily_loss_breaches", 0)
            graduation_result["criteria_met"]["daily_loss_control"] = daily_breaches <= self.demo_requirements["max_daily_loss_breaches"]
            if not graduation_result["criteria_met"]["daily_loss_control"]:
                graduation_result["criteria_failed"]["daily_loss_control"] = f"Too many daily loss breaches: {daily_breaches}"
            
            # Check consecutive losses
            max_consecutive = self.validation_data.get("consecutive_losses_max", 0)
            graduation_result["criteria_met"]["consecutive_loss_control"] = max_consecutive <= self.demo_requirements["max_consecutive_losses"]
            if not graduation_result["criteria_met"]["consecutive_loss_control"]:
                graduation_result["criteria_failed"]["consecutive_loss_control"] = f"Max consecutive losses too high: {max_consecutive}"
            
            # Check profit factor
            profit_factor = performance_summary.get("performance_metrics", {}).get("profit_factor", 0.0)
            graduation_result["criteria_met"]["profit_factor"] = profit_factor >= self.demo_requirements["min_profit_factor"]
            if not graduation_result["criteria_met"]["profit_factor"]:
                graduation_result["criteria_failed"]["profit_factor"] = f"Profit factor too low: {profit_factor:.2f}"
            
            # Check balance growth
            start_balance = self.validation_data.get("demo_balance_start", 1.0)
            current_balance = self.validation_data.get("demo_balance_current", 1.0)
            balance_growth = ((current_balance - start_balance) / start_balance) * 100
            
            graduation_result["criteria_met"]["balance_growth"] = balance_growth >= self.demo_requirements["required_balance_growth"]
            if not graduation_result["criteria_met"]["balance_growth"]:
                graduation_result["criteria_failed"]["balance_growth"] = f"Need {self.demo_requirements['required_balance_growth'] - balance_growth:.1f}% more growth"
            
            # Calculate overall score
            criteria_met = sum(graduation_result["criteria_met"].values())
            total_criteria = len(self.demo_requirements)
            graduation_result["overall_score"] = criteria_met / total_criteria
            
            # Determine if ready for live trading
            graduation_result["ready_for_live"] = criteria_met == total_criteria
            
            # Generate recommendations
            if not graduation_result["ready_for_live"]:
                graduation_result["recommendations"].append("Continue demo trading to meet all criteria")
                for criterion, reason in graduation_result["criteria_failed"].items():
                    graduation_result["recommendations"].append(f"• {criterion}: {reason}")
            else:
                graduation_result["recommendations"].append("🎉 Ready for live trading!")
                graduation_result["recommendations"].append("• Start with minimum stakes")
                graduation_result["recommendations"].append("• Monitor performance closely")
                graduation_result["recommendations"].append("• Be prepared to return to demo if needed")
            
            return graduation_result
            
        except Exception as e:
            self.logger.error(f"Error checking graduation criteria: {e}")
            return {"ready_for_live": False, "error": str(e)}
    
    def approve_graduation(self) -> bool:
        """Approve graduation to live trading"""
        try:
            self.validation_data["validation_passed"] = True
            self.validation_data["graduation_date"] = get_current_timestamp()
            self.validation_data["demo_end_date"] = get_current_timestamp()
            
            # Add graduation note
            graduation_note = {
                "timestamp": get_current_timestamp(),
                "event": "graduation_approved",
                "message": "Bot approved for live trading based on demo performance"
            }
            
            if "validation_notes" not in self.validation_data:
                self.validation_data["validation_notes"] = []
            
            self.validation_data["validation_notes"].append(graduation_note)
            
            # Save graduation approval
            self.save_validation_data(self.validation_data)
            
            self.logger.info("🎓 Bot approved for live trading!")
            return True
            
        except Exception as e:
            self.logger.error(f"Error approving graduation: {e}")
            return False
    
    def generate_demo_report(self, performance_summary: Dict[str, Any], 
                           adaptive_summary: Dict[str, Any]) -> str:
        """Generate comprehensive demo trading report"""
        try:
            report = []
            report.append("=" * 60)
            report.append("📊 DEMO TRADING VALIDATION REPORT")
            report.append("=" * 60)
            
            # Demo period info
            demo_start = self.validation_data.get("demo_start_date", get_current_timestamp())
            demo_days = (get_current_timestamp() - demo_start) / (24 * 3600)
            
            report.append(f"📅 DEMO PERIOD:")
            report.append(f"   Start Date: {datetime.fromtimestamp(demo_start).strftime('%Y-%m-%d %H:%M:%S')}")
            report.append(f"   Duration: {demo_days:.1f} days")
            report.append(f"   Status: {'Completed' if self.validation_data.get('validation_passed') else 'In Progress'}")
            report.append("")
            
            # Performance summary
            report.append(f"📈 PERFORMANCE SUMMARY:")
            report.append(f"   Total Trades: {performance_summary.get('performance_metrics', {}).get('total_trades', 0)}")
            report.append(f"   Win Rate: {performance_summary.get('performance_metrics', {}).get('win_rate', 0):.1f}%")
            report.append(f"   Profit Factor: {performance_summary.get('performance_metrics', {}).get('profit_factor', 0):.2f}")
            
            start_balance = self.validation_data.get("demo_balance_start", 0)
            current_balance = self.validation_data.get("demo_balance_current", 0)
            if start_balance > 0:
                growth = ((current_balance - start_balance) / start_balance) * 100
                report.append(f"   Balance Growth: {growth:.1f}% (${start_balance:.2f} → ${current_balance:.2f})")
            report.append("")
            
            # Risk management
            report.append(f"🛡️ RISK MANAGEMENT:")
            report.append(f"   Daily Loss Breaches: {self.validation_data.get('daily_loss_breaches', 0)}")
            report.append(f"   Max Consecutive Losses: {self.validation_data.get('consecutive_losses_max', 0)}")
            report.append("")
            
            # Adaptive learning
            if adaptive_summary:
                report.append(f"🧠 ADAPTIVE LEARNING:")
                report.append(f"   Learning Progress: {adaptive_summary.get('learning_progress', {}).get('confidence_level', 'Unknown').title()}")
                report.append(f"   Strategies Optimized: {adaptive_summary.get('total_strategies', 0)}")
                
                best_strategy = adaptive_summary.get("best_strategy")
                if best_strategy:
                    report.append(f"   Best Strategy: {best_strategy['name']} ({best_strategy['win_rate']:.1f}% win rate)")
                report.append("")
            
            # Graduation check
            graduation = self.check_graduation_criteria(performance_summary)
            report.append(f"🎓 LIVE TRADING READINESS:")
            report.append(f"   Overall Score: {graduation['overall_score']:.1%}")
            report.append(f"   Ready for Live: {'YES ✅' if graduation['ready_for_live'] else 'NO ❌'}")
            report.append("")
            
            if graduation.get("recommendations"):
                report.append("📋 RECOMMENDATIONS:")
                for rec in graduation["recommendations"]:
                    report.append(f"   {rec}")
                report.append("")
            
            # Criteria breakdown
            report.append("📊 GRADUATION CRITERIA:")
            for criterion, met in graduation["criteria_met"].items():
                status = "✅" if met else "❌"
                report.append(f"   {status} {criterion.replace('_', ' ').title()}")
                if not met and criterion in graduation["criteria_failed"]:
                    report.append(f"      → {graduation['criteria_failed'][criterion]}")
            report.append("")
            
            report.append("=" * 60)
            
            # Save report
            report_text = "\n".join(report)
            report_file = Path("data") / f"demo_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            with open(report_file, 'w') as f:
                f.write(report_text)
            
            self.logger.info(f"Demo trading report saved: {report_file}")
            return report_text
            
        except Exception as e:
            self.logger.error(f"Error generating demo report: {e}")
            return f"Error generating report: {e}"
    
    def get_safety_warnings(self) -> List[str]:
        """Get current safety warnings"""
        warnings = []
        
        try:
            # Check if using live account
            if not self.is_demo_account():
                warnings.append("🚨 CRITICAL: Using LIVE account - switch to DEMO immediately!")
            
            # Check if demo period is too short
            demo_start = self.validation_data.get("demo_start_date", get_current_timestamp())
            demo_days = (get_current_timestamp() - demo_start) / (24 * 3600)
            
            if demo_days < 3:
                warnings.append("⚠️ Demo period very short - extend testing period")
            
            # Check for high risk settings
            max_stake = float(os.getenv('MAX_STAKE', '0.25'))
            if max_stake > 0.5:
                warnings.append(f"⚠️ High max stake setting: ${max_stake}")
            
            # Check performance issues
            current_balance = self.validation_data.get("demo_balance_current", 0)
            start_balance = self.validation_data.get("demo_balance_start", 1)
            
            if current_balance < start_balance * 0.8:  # Lost more than 20%
                warnings.append("⚠️ Significant balance loss detected - review strategy")
            
        except Exception as e:
            warnings.append(f"⚠️ Error checking safety: {e}")
        
        return warnings

# Global validator instance
demo_validator = None

def get_demo_validator() -> DemoTradingValidator:
    """Get or create the global demo validator instance"""
    global demo_validator
    if demo_validator is None:
        demo_validator = DemoTradingValidator()
    return demo_validator