#!/usr/bin/env python3
"""
V10 1S Scalping Bot - Main Application
High-frequency scalping bot for Volatility 10 (1s) Index on Deriv platform
"""

import asyncio
import logging
import signal
import sys
import threading
from typing import Optional
from datetime import datetime, timezone

from config.settings import Config
from src.utils import setup_logging, get_current_timestamp
from src.websocket_client import DerivWebSocketClient
from src.market_data import MarketDataEngine
from src.signal_generator import ScalpingSignalGenerator
from src.risk_manager import RiskManager
from src.trade_executor import TradeExecutor
from src.performance_tracker import PerformanceTracker

class V10ScalpingBot:
    """Main V10 Scalping Bot Application"""
    
    def __init__(self, enable_web_server: bool = True):
        # Load configuration
        self.config = Config.load()
        
        # Setup logging
        self.logger = setup_logging(
            log_level=self.config.system.log_level,
            log_dir=self.config.system.log_dir
        )
        
        # Validate configuration
        is_valid, errors = self.config.validate()
        if not is_valid:
            for error in errors:
                self.logger.error(f"Configuration error: {error}")
            raise ValueError("Invalid configuration")
        
        # Initialize components
        self.websocket_client: Optional[DerivWebSocketClient] = None
        self.market_data: Optional[MarketDataEngine] = None
        self.signal_generator: Optional[ScalpingSignalGenerator] = None
        self.risk_manager: Optional[RiskManager] = None
        self.trade_executor: Optional[TradeExecutor] = None
        self.performance_tracker: Optional[PerformanceTracker] = None
        
        # Web server integration
        self.enable_web_server = enable_web_server
        self.web_server = None
        self.web_server_thread = None
        
        # Application state
        self.running = False
        self.shutdown_requested = False
        self.startup_time = get_current_timestamp()
        
        # Performance monitoring
        self.last_balance_check = 0.0
        self.last_status_report = 0.0
        self.status_report_interval = 300  # 5 minutes
        
        # Setup signal handlers
        self._setup_signal_handlers()
        
        self.logger.info("V10 Scalping Bot initialized")
    
    async def initialize(self) -> bool:
        """Initialize all components"""
        try:
            self.logger.info("Initializing bot components...")
            
            # Initialize WebSocket client
            self.websocket_client = DerivWebSocketClient(self.config.api)
            
            # Initialize market data engine
            self.market_data = MarketDataEngine(
                symbol=self.config.trading.symbol,
                rsi_period=self.config.trading.rsi_period
            )
            
            # Initialize signal generator
            self.signal_generator = ScalpingSignalGenerator(self.config.trading)
            
            # Initialize risk manager
            self.risk_manager = RiskManager(self.config.risk, self.config.trading)
            
            # Initialize trade executor
            self.trade_executor = TradeExecutor(self.websocket_client, self.risk_manager)
            
            # Get initial balance for performance tracker
            if await self.websocket_client.connect():
                initial_balance = await self.websocket_client.get_balance()
                if initial_balance is None:
                    self.logger.error("Failed to get initial balance")
                    return False
                
                # Initialize performance tracker
                self.performance_tracker = PerformanceTracker(initial_balance)
                
                # Initialize risk manager with initial balance
                self.risk_manager.initial_balance = initial_balance
                self.risk_manager.current_balance = initial_balance
                self.risk_manager.peak_balance = initial_balance
                
                # Set up market data subscription
                await self.websocket_client.subscribe_ticks(
                    self.config.trading.symbol,
                    self._handle_tick_data
                )
                
                # Start web server if enabled
                if self.enable_web_server:
                    await self._start_web_server()
                
                self.logger.info(f"Bot initialized successfully with balance: ${initial_balance:.2f}")
                return True
            else:
                self.logger.error("Failed to connect to WebSocket")
                return False
                
        except Exception as e:
            self.logger.error(f"Error during initialization: {e}")
            return False
    
    async def _start_web_server(self):
        """Start the web server for dashboard"""
        try:
            from src.web_server import start_web_server
            
            # Start web server in a separate thread
            self.web_server, self.web_server_thread = start_web_server(
                bot=self,
                host="127.0.0.1",
                port=8000
            )
            
            self.logger.info("Web dashboard started at http://127.0.0.1:8000")
            
        except Exception as e:
            self.logger.error(f"Failed to start web server: {e}")
            self.logger.info("Continuing without web dashboard...")
    
    async def _handle_tick_data(self, tick_data: dict):
        """Handle incoming tick data"""
        try:
            # Process tick data
            if await self.market_data.process_tick(tick_data):
                # Generate trading signal
                signal = self.signal_generator.generate_signal(self.market_data)
                
                if signal:
                    # Get current balance
                    current_balance = await self.websocket_client.get_balance()
                    if current_balance is None:
                        self.logger.warning("Could not get current balance for trade execution")
                        return
                    
                    # Execute trade
                    execution_report = await self.trade_executor.execute_trade(signal, current_balance)
                    
                    # Log execution result
                    self.logger.info(
                        f"Trade execution: {execution_report.result.value} "
                        f"(Signal: {signal.signal_type.value}, "
                        f"Confidence: {signal.confidence:.3f})"
                    )
                    
                    # If trade was executed, track it
                    if execution_report.result.value == "SUCCESS" and execution_report.trade:
                        # The trade will be tracked when it completes
                        pass
                
        except Exception as e:
            self.logger.error(f"Error handling tick data: {e}")
    
    async def _trading_loop(self):
        """Main trading loop"""
        self.logger.info("Starting trading loop...")
        
        while self.running and not self.shutdown_requested:
            try:
                # Check WebSocket connection
                if not self.websocket_client.is_connected():
                    self.logger.warning("WebSocket disconnected, attempting reconnection...")
                    if not await self.websocket_client.reconnect():
                        self.logger.error("Failed to reconnect, stopping bot")
                        break
                
                # Check for expired trades
                await self.trade_executor.check_expired_trades()
                
                # Update performance tracker with completed trades
                await self._update_performance_tracking()
                
                # Periodic status report
                await self._periodic_status_report()
                
                # Sleep for a short interval
                await asyncio.sleep(1.0)
                
            except Exception as e:
                self.logger.error(f"Error in trading loop: {e}")
                await asyncio.sleep(5.0)  # Wait before retrying
    
    async def _update_performance_tracking(self):
        """Update performance tracking with completed trades"""
        try:
            # Get completed trades from executor
            recent_trades = self.trade_executor.get_recent_trades(50)  # Last 50 trades
            
            # Add new completed trades to performance tracker
            for trade in recent_trades:
                if trade.status.value in ['WON', 'LOST']:
                    # Check if we've already tracked this trade
                    if not any(t.trade_id == trade.trade_id for t in self.performance_tracker.trades):
                        self.performance_tracker.add_trade(trade)
                        
        except Exception as e:
            self.logger.error(f"Error updating performance tracking: {e}")
    
    async def _periodic_status_report(self):
        """Generate periodic status reports"""
        current_time = get_current_timestamp()
        
        if current_time - self.last_status_report > self.status_report_interval:
            try:
                # Get current balance
                current_balance = await self.websocket_client.get_balance()
                
                # Get performance summary
                performance_summary = self.performance_tracker.get_performance_summary()
                
                # Get execution stats
                execution_stats = self.trade_executor.get_execution_stats()
                
                # Get risk summary
                risk_summary = self.risk_manager.get_risk_summary()
                
                # Get market data summary
                market_summary = self.market_data.get_data_summary()
                
                # Get signal stats
                signal_stats = self.signal_generator.get_signal_stats()
                
                # Log comprehensive status
                self.logger.info("=== STATUS REPORT ===")
                self.logger.info(f"Runtime: {(current_time - self.startup_time) / 3600:.1f} hours")
                self.logger.info(f"Balance: ${current_balance:.2f} (ROI: {performance_summary['balance_info']['roi_percent']:.2f}%)")
                self.logger.info(f"Total Trades: {performance_summary['performance_metrics']['total_trades']}")
                self.logger.info(f"Win Rate: {performance_summary['performance_metrics']['win_rate']:.1f}%")
                self.logger.info(f"Total P&L: ${performance_summary['performance_metrics']['total_pnl']:.2f}")
                self.logger.info(f"Active Trades: {len(self.trade_executor.get_active_trades())}")
                self.logger.info(f"Signals Generated: {signal_stats['total_signals']}")
                self.logger.info(f"Current RSI: {market_summary['rsi']:.2f}")
                self.logger.info(f"Risk Status: {risk_summary['trading_status']}")
                if self.enable_web_server:
                    self.logger.info("Web Dashboard: http://127.0.0.1:8000")
                self.logger.info("===================")
                
                self.last_status_report = current_time
                
            except Exception as e:
                self.logger.error(f"Error generating status report: {e}")
    
    async def run(self):
        """Run the bot"""
        try:
            self.logger.info("Starting V10 Scalping Bot...")
            
            # Initialize components
            if not await self.initialize():
                self.logger.error("Failed to initialize bot")
                return False
            
            # Start trading
            self.running = True
            
            # Run trading loop
            await self._trading_loop()
            
            return True
            
        except Exception as e:
            self.logger.error(f"Error running bot: {e}")
            return False
        finally:
            await self.shutdown()
    
    async def shutdown(self):
        """Graceful shutdown"""
        if self.shutdown_requested:
            return
        
        self.shutdown_requested = True
        self.running = False
        
        self.logger.info("Shutting down V10 Scalping Bot...")
        
        try:
            # Stop web server
            if self.web_server:
                await self.web_server.stop_monitoring()
                self.logger.info("Web server monitoring stopped")
            
            # Stop trading executor
            if self.trade_executor:
                await self.trade_executor.shutdown()
            
            # Disconnect WebSocket
            if self.websocket_client:
                await self.websocket_client.disconnect()
            
            # Save final performance report
            if self.performance_tracker:
                report_file = self.performance_tracker.export_performance_report()
                self.logger.info(f"Final performance report saved: {report_file}")
            
            # Generate final summary
            await self._generate_final_summary()
            
            self.logger.info("Bot shutdown completed")
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}")
    
    async def _generate_final_summary(self):
        """Generate final trading session summary"""
        try:
            if not self.performance_tracker:
                return
            
            summary = self.performance_tracker.get_performance_summary()
            runtime_hours = (get_current_timestamp() - self.startup_time) / 3600
            
            self.logger.info("=== FINAL SESSION SUMMARY ===")
            self.logger.info(f"Session Runtime: {runtime_hours:.2f} hours")
            self.logger.info(f"Initial Balance: ${summary['balance_info']['initial_balance']:.2f}")
            self.logger.info(f"Final Balance: ${summary['balance_info']['current_balance']:.2f}")
            self.logger.info(f"Total Return: ${summary['balance_info']['total_return']:.2f}")
            self.logger.info(f"ROI: {summary['balance_info']['roi_percent']:.2f}%")
            self.logger.info(f"Total Trades: {summary['performance_metrics']['total_trades']}")
            self.logger.info(f"Win Rate: {summary['performance_metrics']['win_rate']:.1f}%")
            self.logger.info(f"Profit Factor: {summary['performance_metrics']['profit_factor']:.2f}")
            self.logger.info(f"Max Drawdown: {summary['drawdown_metrics']['max_drawdown']:.2f}%")
            self.logger.info(f"Sharpe Ratio: {summary['risk_metrics']['sharpe_ratio']:.2f}")
            
            # Strategy performance
            if summary['strategy_breakdown']:
                self.logger.info("Strategy Performance:")
                for strategy, metrics in summary['strategy_breakdown'].items():
                    self.logger.info(
                        f"  {strategy}: {metrics['total_trades']} trades, "
                        f"{metrics['win_rate']:.1f}% win rate, "
                        f"${metrics['total_pnl']:.2f} P&L"
                    )
            
            if self.enable_web_server:
                self.logger.info("Web Dashboard was available at: http://127.0.0.1:8000")
            
            self.logger.info("=============================")
            
        except Exception as e:
            self.logger.error(f"Error generating final summary: {e}")
    
    def _setup_signal_handlers(self):
        """Setup signal handlers for graceful shutdown"""
        def signal_handler(signum, frame):
            self.logger.info(f"Received signal {signum}, initiating shutdown...")
            asyncio.create_task(self.shutdown())
        
        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)
    
    def get_status(self) -> dict:
        """Get current bot status"""
        return {
            'running': self.running,
            'startup_time': self.startup_time,
            'runtime_seconds': get_current_timestamp() - self.startup_time,
            'websocket_connected': self.websocket_client.is_connected() if self.websocket_client else False,
            'active_trades': len(self.trade_executor.get_active_trades()) if self.trade_executor else 0,
            'total_trades': len(self.performance_tracker.trades) if self.performance_tracker else 0,
            'web_server_enabled': self.enable_web_server,
            'web_dashboard_url': 'http://127.0.0.1:8000' if self.enable_web_server else None
        }

async def main():
    """Main entry point"""
    try:
        # Check if web server should be enabled (default: yes)
        enable_web = '--no-web' not in sys.argv
        
        if enable_web:
            print("🌐 Starting V10 Scalping Bot with Web Dashboard...")
            print("📊 Dashboard will be available at: http://127.0.0.1:8000")
        else:
            print("🤖 Starting V10 Scalping Bot (headless mode)...")
        
        # Create and run bot
        bot = V10ScalpingBot(enable_web_server=enable_web)
        success = await bot.run()
        
        if success:
            print("Bot completed successfully")
            sys.exit(0)
        else:
            print("Bot failed to run")
            sys.exit(1)
            
    except KeyboardInterrupt:
        print("\nBot interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    # Run the bot
    asyncio.run(main())