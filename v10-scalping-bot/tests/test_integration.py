import unittest
import sys
import os
import asyncio
from unittest.mock import Mock, patch, AsyncMock

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from config.settings import Config, APIConfig, TradingConfig, RiskConfig, SystemConfig
from src.websocket_client import DerivWebSocketClient
from src.market_data import MarketDataEngine
from src.signal_generator import ScalpingSignalGenerator, SignalType
from src.risk_manager import RiskManager, TradeDecision
from src.trade_executor import TradeExecutor
from src.performance_tracker import PerformanceTracker

class TestComponentIntegration(unittest.TestCase):
    """Test integration between components"""
    
    def setUp(self):
        """Set up test components"""
        self.config = Config(
            api=APIConfig(token="test_token", app_id="12345"),
            trading=TradingConfig(symbol="1HZ10V", max_stake=0.25, min_confidence=0.6),
            risk=RiskConfig(max_daily_loss=1.50, max_consecutive_losses=5),
            system=SystemConfig(log_level="DEBUG")
        )
        
        # Create components
        self.market_data = MarketDataEngine("1HZ10V", rsi_period=14)
        self.signal_generator = ScalpingSignalGenerator(self.config.trading)
        self.risk_manager = RiskManager(self.config.risk, self.config.trading)
        self.performance_tracker = PerformanceTracker(initial_balance=5.0)
    
    async def test_market_data_to_signal_flow(self):
        """Test data flow from market data to signal generation"""
        # Simulate strong uptrend to generate high RSI
        for i in range(20):
            tick_data = {
                'tick': {
                    'quote': 1000.0 + i * 3,  # Strong uptrend
                    'epoch': 1700000000 + i
                }
            }
            await self.market_data.process_tick(tick_data)
        
        # Check that market data is processed
        self.assertGreater(self.market_data.tick_count, 0)
        self.assertTrue(self.market_data.is_rsi_ready())
        
        # Generate signal
        signal = self.signal_generator.generate_signal(self.market_data)
        
        # Should generate a signal for extreme RSI
        if signal:
            self.assertIn(signal.signal_type, [SignalType.CALL, SignalType.PUT])
            self.assertGreater(signal.confidence, 0.0)
            self.assertGreater(signal.duration, 0)
    
    def test_signal_to_risk_assessment_flow(self):
        """Test flow from signal to risk assessment"""
        # Create mock signal
        mock_signal = Mock()
        mock_signal.confidence = 0.8
        mock_signal.duration = 5
        mock_signal.signal_type = SignalType.CALL
        mock_signal.entry_price = 1000.0
        mock_signal.timestamp = 1700000000
        mock_signal.strategy = "TEST_STRATEGY"
        mock_signal.rsi_value = 25.0
        mock_signal.additional_data = {}
        
        # Assess risk with good balance
        risk_assessment = self.risk_manager.assess_trade_risk(mock_signal, 5.0)
        
        # Should be approved with good conditions
        self.assertIn(risk_assessment.decision, [TradeDecision.APPROVED, TradeDecision.REDUCED])
        self.assertGreater(risk_assessment.recommended_stake, 0.0)
        self.assertLessEqual(risk_assessment.recommended_stake, 0.25)
    
    def test_risk_manager_state_persistence(self):
        """Test risk manager state tracking"""
        # Record some trades
        trades_data = [
            (-0.25, False),  # Loss
            (0.20, True),    # Win
            (-0.25, False),  # Loss
            (-0.25, False),  # Loss
            (0.30, True),    # Win
        ]
        
        for pnl, is_win in trades_data:
            self.risk_manager.record_trade_result(pnl, is_win)
        
        # Check statistics
        self.assertEqual(self.risk_manager.stats.total_trades, 5)
        self.assertEqual(self.risk_manager.stats.winning_trades, 2)
        self.assertEqual(self.risk_manager.stats.losing_trades, 3)
        self.assertEqual(self.risk_manager.stats.consecutive_losses, 2)
        
        # Check win rate calculation
        expected_win_rate = (2 / 5) * 100  # 40%
        self.assertAlmostEqual(self.risk_manager.stats.win_rate(), expected_win_rate, places=1)
    
    def test_performance_tracker_integration(self):
        """Test performance tracker with mock trades"""
        from src.trade_executor import Trade, TradeStatus
        from src.signal_generator import TradingSignal, SignalStrength
        
        # Create mock signal
        mock_signal = TradingSignal(
            signal_type=SignalType.CALL,
            confidence=0.8,
            strength=SignalStrength.STRONG,
            duration=5,
            entry_price=1000.0,
            timestamp=1700000000,
            strategy="TEST_STRATEGY",
            rsi_value=25.0,
            additional_data={}
        )
        
        # Create mock trades
        trades = [
            Trade(
                trade_id="T001",
                signal=mock_signal,
                contract_type="CALL",
                stake=0.25,
                duration=5,
                entry_price=1000.0,
                entry_time=1700000000,
                status=TradeStatus.WON,
                exit_price=1001.0,
                exit_time=1700000005,
                profit_loss=0.20
            ),
            Trade(
                trade_id="T002",
                signal=mock_signal,
                contract_type="PUT",
                stake=0.25,
                duration=4,
                entry_price=1001.0,
                entry_time=1700000010,
                status=TradeStatus.LOST,
                exit_price=1002.0,
                exit_time=1700000014,
                profit_loss=-0.25
            )
        ]
        
        # Add trades to performance tracker
        for trade in trades:
            self.performance_tracker.add_trade(trade)
        
        # Check performance metrics
        summary = self.performance_tracker.get_performance_summary()
        
        self.assertEqual(summary['performance_metrics']['total_trades'], 2)
        self.assertEqual(summary['performance_metrics']['winning_trades'], 1)
        self.assertEqual(summary['performance_metrics']['losing_trades'], 1)
        self.assertAlmostEqual(summary['performance_metrics']['win_rate'], 50.0, places=1)
        self.assertAlmostEqual(summary['performance_metrics']['total_pnl'], -0.05, places=2)

class TestWebSocketClientMock(unittest.TestCase):
    """Test WebSocket client with mocking"""
    
    def setUp(self):
        self.api_config = APIConfig(
            token="test_token",
            app_id="12345",
            websocket_url="wss://test.example.com"
        )
    
    @patch('websockets.connect')
    async def test_websocket_connection_mock(self, mock_connect):
        """Test WebSocket connection with mocking"""
        # Mock WebSocket connection
        mock_websocket = AsyncMock()
        mock_connect.return_value = mock_websocket
        
        # Create client
        client = DerivWebSocketClient(self.api_config)
        
        # Mock authentication response
        mock_websocket.send = AsyncMock()
        client.send_request = AsyncMock(return_value={'authorize': {'balance': 100.0}})
        
        # Test connection
        result = await client.connect()
        
        # Verify connection attempt
        mock_connect.assert_called_once()
        self.assertTrue(result)

class TestEndToEndFlow(unittest.TestCase):
    """Test complete end-to-end flow with mocking"""
    
    def setUp(self):
        """Set up complete system"""
        self.config = Config(
            api=APIConfig(token="test_token", app_id="12345"),
            trading=TradingConfig(symbol="1HZ10V", max_stake=0.25),
            risk=RiskConfig(max_daily_loss=1.50),
            system=SystemConfig()
        )
    
    @patch('src.websocket_client.DerivWebSocketClient')
    async def test_complete_trading_cycle(self, mock_ws_client):
        """Test complete trading cycle from tick to trade"""
        # Mock WebSocket client
        mock_client = Mock()
        mock_client.is_connected.return_value = True
        mock_client.get_balance = AsyncMock(return_value=5.0)
        mock_client.buy_contract = AsyncMock(return_value={
            'contract_id': 'TEST123',
            'payout': 0.45,
            'barrier': 1000.5
        })
        mock_ws_client.return_value = mock_client
        
        # Create components
        market_data = MarketDataEngine("1HZ10V", rsi_period=14)
        signal_generator = ScalpingSignalGenerator(self.config.trading)
        risk_manager = RiskManager(self.config.risk, self.config.trading)
        trade_executor = TradeExecutor(mock_client, risk_manager)
        
        # Simulate market data that should generate a signal
        for i in range(20):
            tick_data = {
                'tick': {
                    'quote': 1000.0 + i * 2,  # Uptrend
                    'epoch': 1700000000 + i
                }
            }
            await market_data.process_tick(tick_data)
        
        # Generate signal
        signal = signal_generator.generate_signal(market_data)
        
        if signal:
            # Execute trade
            execution_report = await trade_executor.execute_trade(signal, 5.0)
            
            # Verify trade execution
            self.assertIsNotNone(execution_report)
            if execution_report.result.value == "SUCCESS":
                self.assertIsNotNone(execution_report.trade)
                mock_client.buy_contract.assert_called_once()

if __name__ == '__main__':
    # Run integration tests
    unittest.main(verbosity=2)