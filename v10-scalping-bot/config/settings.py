import os
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

@dataclass
class APIConfig:
    """Deriv API configuration"""
    token: str = os.getenv('DERIV_API_TOKEN', '')
    app_id: str = os.getenv('DERIV_APP_ID', '85633')
    websocket_url: str = 'wss://ws.derivws.com/websockets/v3'
    
    def validate(self) -> bool:
        """Validate API configuration"""
        return bool(self.token and self.app_id)

@dataclass
class TradingConfig:
    """Trading strategy configuration"""
    symbol: str = os.getenv('SYMBOL', '1HZ10V')
    max_stake: float = float(os.getenv('MAX_STAKE', '0.25'))
    min_confidence: float = float(os.getenv('MIN_CONFIDENCE', '0.6'))
    rsi_period: int = int(os.getenv('RSI_PERIOD', '14'))
    rsi_overbought: float = float(os.getenv('RSI_OVERBOUGHT', '70'))
    rsi_oversold: float = float(os.getenv('RSI_OVERSOLD', '30'))

@dataclass
class RiskConfig:
    """Risk management configuration"""
    max_daily_loss: float = float(os.getenv('MAX_DAILY_LOSS', '1.50'))
    max_consecutive_losses: int = int(os.getenv('MAX_CONSECUTIVE_LOSSES', '5'))
    max_trades_per_hour: int = int(os.getenv('MAX_TRADES_PER_HOUR', '15'))
    max_trades_per_day: int = int(os.getenv('MAX_TRADES_PER_DAY', '100'))
    cooldown_minutes: int = int(os.getenv('COOLDOWN_MINUTES', '60'))
    min_balance_to_trade: float = float(os.getenv('MIN_BALANCE_TO_TRADE', '2.00'))
    max_drawdown_percent: float = float(os.getenv('MAX_DRAWDOWN_PERCENT', '40'))

@dataclass
class SystemConfig:
    """System configuration"""
    log_level: str = os.getenv('LOG_LEVEL', 'INFO')
    save_trades: bool = os.getenv('SAVE_TRADES', 'true').lower() == 'true'
    report_interval: int = int(os.getenv('REPORT_INTERVAL', '3600'))
    data_dir: str = os.getenv('DATA_DIR', 'data')
    log_dir: str = os.getenv('LOG_DIR', 'logs')

@dataclass
class Config:
    """Main configuration container"""
    api: APIConfig
    trading: TradingConfig
    risk: RiskConfig
    system: SystemConfig
    
    @classmethod
    def load(cls) -> 'Config':
        """Load configuration from environment"""
        return cls(
            api=APIConfig(),
            trading=TradingConfig(),
            risk=RiskConfig(),
            system=SystemConfig()
        )
    
    def validate(self) -> tuple[bool, list[str]]:
        """Validate all configuration"""
        errors = []
        
        if not self.api.validate():
            errors.append("Missing or invalid API configuration")
        
        if self.trading.max_stake <= 0:
            errors.append("Max stake must be positive")
        
        if self.risk.max_daily_loss <= 0:
            errors.append("Max daily loss must be positive")
        
        return len(errors) == 0, errors