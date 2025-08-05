#!/usr/bin/env python3
"""
V10 Scalping Bot Dashboard Demo
Shows the web dashboard with simulated data for testing
"""

import asyncio
import random
import time
from datetime import datetime
from pathlib import Path

# Add project root to Python path
import sys
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.web_server import BotWebServer
import uvicorn

class MockBot:
    """Mock bot for demonstration purposes"""
    
    def __init__(self):
        self.startup_time = time.time()
        self.running = True
        self.balance = 5.0
        self.initial_balance = 5.0
        self.trades_count = 0
        self.wins = 0
        self.current_rsi = 50.0
        
    def get_status(self):
        return {
            'running': self.running,
            'startup_time': self.startup_time,
            'runtime_seconds': time.time() - self.startup_time,
            'websocket_connected': True,
            'active_trades': random.randint(0, 3),
            'total_trades': self.trades_count,
            'web_server_enabled': True,
            'web_dashboard_url': 'http://127.0.0.1:8000'
        }
    
    def get_mock_performance(self):
        roi = ((self.balance - self.initial_balance) / self.initial_balance) * 100
        win_rate = (self.wins / max(self.trades_count, 1)) * 100
        
        return {
            'status': 'success',
            'data': {
                'balance_info': {
                    'current_balance': self.balance,
                    'initial_balance': self.initial_balance,
                    'total_return': self.balance - self.initial_balance,
                    'roi_percent': roi
                },
                'performance_metrics': {
                    'total_trades': self.trades_count,
                    'win_rate': win_rate,
                    'total_wins': self.wins,
                    'total_losses': self.trades_count - self.wins
                }
            }
        }
    
    def get_mock_market_data(self):
        # Simulate RSI movement
        self.current_rsi += random.uniform(-5, 5)
        self.current_rsi = max(0, min(100, self.current_rsi))
        
        return {
            'status': 'success',
            'data': {
                'rsi': self.current_rsi,
                'current_price': 1000 + random.uniform(-50, 50),
                'volatility': random.uniform(0.1, 0.5)
            }
        }
    
    def get_mock_trades(self):
        active_trades = []
        recent_trades = []
        
        # Generate some mock active trades
        for i in range(random.randint(0, 2)):
            active_trades.append({
                'trade_id': f'mock_active_{i}',
                'contract_type': random.choice(['CALL', 'PUT']),
                'stake': 0.25,
                'duration': random.randint(3, 7),
                'entry_price': 1000 + random.uniform(-20, 20),
                'status': 'ACTIVE'
            })
        
        # Generate some mock recent trades
        for i in range(10):
            profit_loss = random.uniform(-0.25, 0.45) if random.random() > 0.3 else random.uniform(-0.25, -0.20)
            status = 'WON' if profit_loss > 0 else 'LOST'
            
            recent_trades.append({
                'trade_id': f'mock_recent_{i}',
                'contract_type': random.choice(['CALL', 'PUT']),
                'stake': 0.25,
                'duration': random.randint(3, 7),
                'entry_price': 1000 + random.uniform(-20, 20),
                'exit_price': 1000 + random.uniform(-20, 20),
                'exit_time': time.time() - random.randint(60, 3600),
                'profit_loss': profit_loss,
                'status': status,
                'signal': {'strategy': random.choice(['RSI_MEAN_REVERSION', 'MOMENTUM_EXHAUSTION'])}
            })
        
        return {
            'status': 'success',
            'data': {
                'active_trades': active_trades,
                'recent_trades': recent_trades
            }
        }
    
    def get_mock_signals(self):
        signals = []
        
        for i in range(5):
            signal_type = 'CALL' if self.current_rsi < 30 else 'PUT' if self.current_rsi > 70 else random.choice(['CALL', 'PUT'])
            signals.append({
                'timestamp': time.time() - random.randint(10, 300),
                'signal_type': signal_type,
                'confidence': random.uniform(0.6, 0.95),
                'strategy': random.choice(['RSI_MEAN_REVERSION', 'MOMENTUM_EXHAUSTION']),
                'rsi_value': self.current_rsi + random.uniform(-5, 5)
            })
        
        return {
            'status': 'success',
            'data': {
                'recent_signals': signals,
                'signal_stats': {
                    'total_signals': len(signals) + random.randint(10, 50),
                    'signals_per_hour': random.uniform(5, 15)
                }
            }
        }
    
    def get_mock_risk(self):
        return {
            'status': 'success',
            'data': {
                'trading_status': 'ACTIVE',
                'performance': {
                    'daily_pnl': self.balance - self.initial_balance
                },
                'risk_metrics': {
                    'consecutive_losses': random.randint(0, 3),
                    'current_drawdown_pct': random.uniform(0, 15),
                    'hourly_trade_count': random.randint(0, 10)
                }
            }
        }
    
    def simulate_trading(self):
        """Simulate some trading activity"""
        if random.random() < 0.1:  # 10% chance of new trade
            self.trades_count += 1
            if random.random() < 0.7:  # 70% win rate
                self.wins += 1
                self.balance += random.uniform(0.15, 0.45)
            else:
                self.balance -= random.uniform(0.20, 0.25)

class MockBotWebServer(BotWebServer):
    """Extended web server with mock data endpoints"""
    
    def __init__(self):
        super().__init__(bot=None)
        self.mock_bot = MockBot()
        
        # Override routes with mock data
        self._setup_mock_routes()
    
    def _setup_mock_routes(self):
        """Setup mock data routes for demo"""
        
        @self.app.get("/api/status")
        async def get_mock_status():
            return {
                "status": "connected",
                "data": self.mock_bot.get_status(),
                "timestamp": time.time()
            }
        
        @self.app.get("/api/performance")
        async def get_mock_performance():
            return self.mock_bot.get_mock_performance()
        
        @self.app.get("/api/trades")
        async def get_mock_trades():
            return self.mock_bot.get_mock_trades()
        
        @self.app.get("/api/market_data")
        async def get_mock_market_data():
            return self.mock_bot.get_mock_market_data()
        
        @self.app.get("/api/signals")
        async def get_mock_signals():
            return self.mock_bot.get_mock_signals()
        
        @self.app.get("/api/risk")
        async def get_mock_risk():
            return self.mock_bot.get_mock_risk()
    
    async def start_mock_simulation(self):
        """Start mock data simulation"""
        while True:
            try:
                # Simulate trading
                self.mock_bot.simulate_trading()
                
                # Broadcast mock updates
                update_data = {
                    "type": "update",
                    "timestamp": time.time(),
                    "data": {
                        "status": {"status": "connected", "data": self.mock_bot.get_status()},
                        "performance": self.mock_bot.get_mock_performance(),
                        "market": self.mock_bot.get_mock_market_data(),
                        "trades": self.mock_bot.get_mock_trades(),
                        "signals": self.mock_bot.get_mock_signals(),
                        "risk": self.mock_bot.get_mock_risk()
                    }
                }
                
                await self.websocket_manager.broadcast(update_data)
                
                await asyncio.sleep(2)  # Update every 2 seconds
                
            except Exception as e:
                print(f"Error in mock simulation: {e}")
                await asyncio.sleep(5)

async def run_demo():
    """Run the dashboard demo"""
    print("🚀 V10 Scalping Bot Dashboard Demo")
    print("=" * 40)
    print("📊 Starting demo with simulated data...")
    print("🌐 Dashboard will be available at: http://127.0.0.1:8000")
    print("📈 Watch the real-time updates!")
    print("🛑 Press Ctrl+C to stop")
    print("=" * 40)
    
    # Create mock web server
    mock_server = MockBotWebServer()
    
    # Start simulation task
    simulation_task = asyncio.create_task(mock_server.start_mock_simulation())
    
    # Start web server
    config = uvicorn.Config(mock_server.app, host="127.0.0.1", port=8000, log_level="info")
    server = uvicorn.Server(config)
    
    try:
        await server.serve()
    except KeyboardInterrupt:
        print("\n🛑 Demo stopped by user")
        simulation_task.cancel()
    except Exception as e:
        print(f"❌ Demo error: {e}")
        simulation_task.cancel()

if __name__ == "__main__":
    print("🎮 V10 Scalping Bot Dashboard Demo")
    print("This will show the dashboard with simulated trading data")
    print("Perfect for testing the interface before live trading!")
    print()
    
    try:
        asyncio.run(run_demo())
    except KeyboardInterrupt:
        print("\n👋 Demo ended!")
    except Exception as e:
        print(f"💥 Demo error: {e}")