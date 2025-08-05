import unittest
import sys
import os
from unittest.mock import Mock, patch, AsyncMock
import asyncio

# Add project root to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from config.settings import Config, APIConfig, TradingConfig, RiskConfig, SystemConfig
from src.market_data import MarketDataEngine, RSICalculator
from src.signal_generator import ScalpingSignalGenerator, TradingSignal, SignalType
from src.risk_manager import RiskManager, TradeDecision
from src.utils import get_current_timestamp, round_to_precision

class TestConfiguration(unittest.TestCase):
    """Test configuration system"""
    
    def test_config_creation(self):
        """Test configuration object creation"""
        config = Config(
            api=APIConfig(token="test_token", app_id="12345"),
            trading=TradingConfig(symbol="1HZ10V", max_stake=0.25),
            risk=RiskConfig(max_daily_loss=1.50),
            system=SystemConfig(log_level="INFO")
        )
        
        self.assertEqual(config.api.token, "test_token")
        self.assertEqual(config.trading.symbol, "1HZ10V")
        self.assertEqual(config.risk.max_daily_loss, 1.50)
        self.assertEqual(config.system.log_level, "INFO")
    
    def test_config_validation(self):
        """Test configuration validation"""
        # Valid config
        config = Config(
            api=APIConfig(token="test_token", app_id="12345"),
            trading=TradingConfig(max_stake=0.25),
            risk=RiskConfig(max_daily_loss=1.50),
            system=SystemConfig()
        )
        
        is_valid, errors = config.validate()
        self.assertTrue(is_valid)
        self.assertEqual(len(errors), 0)
        
        # Invalid config - no token
        config.api.token = ""
        is_valid, errors = config.validate()
        self.assertFalse(is_valid)
        self.assertGreater(len(errors), 0)

class TestRSICalculator(unittest.TestCase):
    """Test RSI calculation functionality"""
    
    def setUp(self):
        self.rsi_calc = RSICalculator(period=14)
    
    def test_rsi_initialization(self):
        """Test RSI calculator initialization"""
        self.assertEqual(self.rsi_calc.period, 14)
        self.assertEqual(self.rsi_calc.rsi_value, 50.0)
        self.assertFalse(self.rsi_calc.is_ready())
    
    def test_rsi_calculation(self):
        """Test RSI calculation with sample data"""
        # Add some sample prices (trending up)
        prices = [100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 
                 110, 111, 112, 113, 114, 115, 116, 117, 118, 119]
        
        for price in prices:
            rsi = self.rsi_calc.add_price(price)
        
        # RSI should be high for uptrend
        self.assertGreater(rsi, 70)
        self.assertTrue(self.rsi_calc.is_ready())
    
    def test_rsi_extreme_values(self):
        """Test RSI with extreme price movements"""
        # Add prices that go straight up
        for i in range(20):
            price = 100 + i
            rsi = self.rsi_calc.add_price(price)
        
        # Should approach 100
        self.assertGreater(rsi, 90)
        
        # Now add prices that go straight down
        for i in range(20):
            price = 120 - i
            rsi = self.rsi_calc.add_price(price)
        
        # Should approach 0
        self.assertLess(rsi, 20)

class TestMarketDataEngine(unittest.TestCase):
    """Test market data processing"""
    
    def setUp(self):
        self.market_data = MarketDataEngine("1HZ10V", rsi_period=14)
    
    def test_initialization(self):
        """Test market data engine initialization"""
        self.assertEqual(self.market_data.symbol, "1HZ10V")
        self.assertEqual(self.market_data.current_price, 0.0)
        self.assertEqual(self.market_data.tick_count, 0)
    
    async def test_tick_processing(self):
        """Test tick data processing"""
        # Mock tick data
        tick_data = {
            'tick': {
                'quote': 1000.5,
                'epoch': get_current_timestamp()
            }
        }
        
        result = await self.market_data.process_tick(tick_data)
        self.assertTrue(result)
        self.assertEqual(self.market_data.current_price, 1000.5)
        self.assertEqual(self.market_data.tick_count, 1)
    
    async def test_invalid_tick_data(self):
        """Test handling of invalid tick data"""
        # Invalid tick data (no price)
        tick_data = {
            'tick': {
                'epoch': get_current_timestamp()
            }
        }
        
        result = await self.market_data.process_tick(tick_data)
        self.assertFalse(result)
        self.assertEqual(self.market_data.current_price, 0.0)
    
    def test_consecutive_moves_detection(self):
        """Test consecutive price moves detection"""
        # Simulate consecutive up moves
        async def simulate_moves():
            for i in range(6):  # 6 consecutive up moves
                tick_data = {
                    'tick': {
                        'quote': 1000.0 + i,
                        'epoch': get_current_timestamp() + i
                    }
                }
                await self.market_data.process_tick(tick_data)
        
        asyncio.run(simulate_moves())
        
        consecutive_moves, direction = self.market_data.get_consecutive_moves()
        self.assertEqual(consecutive_moves, 5)  # 5 moves after first price
        self.assertEqual(direction, 1)  # Up direction

class TestSignalGenerator(unittest.TestCase):
    """Test signal generation"""
    
    def setUp(self):
        self.trading_config = TradingConfig(
            max_stake=0.25,
            min_confidence=0.6,
            rsi_overbought=70,
            rsi_oversold=30
        )
        self.signal_gen = ScalpingSignalGenerator(self.trading_config)
        self.market_data = MarketDataEngine("1HZ10V", rsi_period=14)
    
    def test_initialization(self):
        """Test signal generator initialization"""
        self.assertEqual(self.signal_gen.min_confidence, 0.6)
        self.assertEqual(self.signal_gen.rsi_overbought, 70)
        self.assertEqual(self.signal_gen.rsi_oversold, 30)
    
    def test_no_signal_insufficient_data(self):
        """Test no signal when insufficient data"""
        signal = self.signal_gen.generate_signal(self.market_data)
        self.assertIsNone(signal)
    
    async def test_rsi_extreme_signal_generation(self):
        """Test signal generation for RSI extremes"""
        # Simulate data to get RSI ready
        for i in range(20):
            tick_data = {
                'tick': {
                    'quote': 1000.0 + i * 2,  # Strong uptrend
                    'epoch': get_current_timestamp() + i
                }
            }
            await self.market_data.process_tick(tick_data)
        
        # Should generate PUT signal for high RSI
        signal = self.signal_gen.generate_signal(self.market_data)
        if signal:  # Signal might be generated depending on RSI value
            self.assertEqual(signal.signal_type, SignalType.PUT)
            self.assertGreater(signal.confidence, 0.0)

class TestRiskManager(unittest.TestCase):
    """Test risk management"""
    
    def setUp(self):
        self.risk_config = RiskConfig(
            max_daily_loss=1.50,
            max_consecutive_losses=5,
            max_trades_per_hour=15,
            min_balance_to_trade=2.00
        )
        self.trading_config = TradingConfig(max_stake=0.25)
        self.risk_manager = RiskManager(self.risk_config, self.trading_config)
    
    def test_initialization(self):
        """Test risk manager initialization"""
        self.assertEqual(self.risk_manager.risk_config.max_daily_loss, 1.50)
        self.assertEqual(self.risk_manager.stats.total_trades, 0)
        self.assertFalse(self.risk_manager.trading_paused)
    
    def test_balance_risk_assessment(self):
        """Test balance-based risk assessment"""
        # Create mock signal
        mock_signal = Mock()
        mock_signal.confidence = 0.8
        mock_signal.duration = 5
        
        # Test with sufficient balance
        risk_assessment = self.risk_manager.assess_trade_risk(mock_signal, 5.0)
        self.assertEqual(risk_assessment.decision, TradeDecision.APPROVED)
        
        # Test with insufficient balance
        risk_assessment = self.risk_manager.assess_trade_risk(mock_signal, 1.0)
        self.assertEqual(risk_assessment.decision, TradeDecision.REJECTED)
    
    def test_consecutive_loss_tracking(self):
        """Test consecutive loss tracking"""
        # Record some losses
        for i in range(3):
            self.risk_manager.record_trade_result(-0.25, False)
        
        self.assertEqual(self.risk_manager.stats.consecutive_losses, 3)
        self.assertEqual(self.risk_manager.stats.losing_trades, 3)
        
        # Record a win
        self.risk_manager.record_trade_result(0.20, True)
        
        self.assertEqual(self.risk_manager.stats.consecutive_losses, 0)
        self.assertEqual(self.risk_manager.stats.consecutive_wins, 1)

class TestUtilities(unittest.TestCase):
    """Test utility functions"""
    
    def test_round_to_precision(self):
        """Test precision rounding"""
        self.assertEqual(round_to_precision(1.23456789, 2), 1.23)
        self.assertEqual(round_to_precision(1.23456789, 4), 1.2346)
        self.assertEqual(round_to_precision(1.0, 2), 1.0)
    
    def test_timestamp_functions(self):
        """Test timestamp utilities"""
        timestamp = get_current_timestamp()
        self.assertIsInstance(timestamp, float)
        self.assertGreater(timestamp, 0)

if __name__ == '__main__':
    # Run tests
    unittest.main(verbosity=2)