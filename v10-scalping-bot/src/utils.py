import logging
import os
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from pathlib import Path

def setup_logging(log_level: str = 'INFO', log_dir: str = 'logs') -> logging.Logger:
    """Setup logging configuration"""
    # Create logs directory if it doesn't exist
    Path(log_dir).mkdir(exist_ok=True)
    
    # Configure logging
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    
    # File handler
    log_file = os.path.join(log_dir, f'v10_bot_{datetime.now().strftime("%Y%m%d")}.log')
    file_handler = logging.FileHandler(log_file)
    file_handler.setFormatter(logging.Formatter(log_format))
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(logging.Formatter(log_format))
    
    # Setup logger
    logger = logging.getLogger('V10ScalpingBot')
    logger.setLevel(getattr(logging, log_level.upper()))
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)
    
    return logger

def get_current_timestamp() -> float:
    """Get current UTC timestamp"""
    return datetime.now(timezone.utc).timestamp()

def format_timestamp(timestamp: float) -> str:
    """Format timestamp for display"""
    return datetime.fromtimestamp(timestamp, timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')

def save_json_data(data: Dict[str, Any], filepath: str) -> bool:
    """Save data to JSON file"""
    try:
        Path(filepath).parent.mkdir(parents=True, exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)
        return True
    except Exception as e:
        logging.error(f"Failed to save JSON data: {e}")
        return False

def load_json_data(filepath: str) -> Optional[Dict[str, Any]]:
    """Load data from JSON file"""
    try:
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                return json.load(f)
    except Exception as e:
        logging.error(f"Failed to load JSON data: {e}")
    return None

def calculate_percentage_change(old_value: float, new_value: float) -> float:
    """Calculate percentage change between two values"""
    if old_value == 0:
        return 0
    return ((new_value - old_value) / old_value) * 100

def round_to_precision(value: float, precision: int = 5) -> float:
    """Round value to specified decimal places"""
    return round(value, precision)

class RateLimiter:
    """Simple rate limiter for API calls"""
    
    def __init__(self, max_calls: int, time_window: int):
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls = []
    
    def can_proceed(self) -> bool:
        """Check if we can make another call"""
        now = get_current_timestamp()
        # Remove old calls outside the time window
        self.calls = [call_time for call_time in self.calls if now - call_time < self.time_window]
        return len(self.calls) < self.max_calls
    
    def record_call(self):
        """Record a new call"""
        self.calls.append(get_current_timestamp())