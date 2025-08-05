# V10 1S Scalping Bot

A high-frequency scalping bot designed specifically for Volatility 10 (1s) Index trading on the Deriv platform. This bot implements advanced RSI-based mean reversion and momentum exhaustion strategies to achieve consistent profitability in the V10 1s market.

## 🎯 Project Goals

- **Primary Target**: Turn $5 into $50+ within 30 days using V10 1s scalping
- **Win Rate Target**: 70%+ (based on proven scalping strategies)
- **Trade Frequency**: 10-50 trades per day (high-frequency scalping)
- **Execution Speed**: <100ms from signal to trade execution
- **Risk Management**: Comprehensive protection with multiple safety layers

## 🏗️ Architecture

The bot consists of 8 core components working together:

1. **WebSocket Client** - Real-time connection to Deriv API
2. **Market Data Engine** - Tick data processing and RSI calculation
3. **Signal Generator** - Advanced scalping signal detection
4. **Risk Manager** - Multi-layer risk protection system
5. **Trade Executor** - High-speed order execution and management
6. **Performance Tracker** - Real-time analytics and reporting
7. **Configuration System** - Environment-based settings management
8. **Main Application** - Orchestrates all components

## 📊 Trading Strategies

### Primary Strategy: RSI Mean Reversion
- **RSI > 85**: Strong PUT signals (expect reversal down)
- **RSI < 15**: Strong CALL signals (expect reversal up)
- **RSI 70-85**: Moderate PUT signals
- **RSI 15-30**: Moderate CALL signals

### Secondary Strategy: Momentum Exhaustion
- **5+ consecutive moves up**: PUT signal (reversal expected)
- **5+ consecutive moves down**: CALL signal (reversal expected)
- **RSI confirmation**: Additional confidence boost

### Supporting Strategy: Volatility Spike Reversal
- Detects unusual price movements
- Expects mean reversion after volatility spikes
- RSI confirmation required

## 🛡️ Risk Management

### Position Sizing
- Maximum $0.25 per trade (5% of $5 starting balance)
- Dynamic sizing based on risk score
- Balance-adjusted position sizing

### Loss Limits
- **Daily Loss Limit**: $1.50 (30% of starting balance)
- **Consecutive Losses**: Maximum 5 in a row
- **Maximum Drawdown**: 40% from peak balance
- **Hourly Trade Limit**: 15 trades maximum

### Safety Features
- Automatic trading pause on limit breach
- Real-time balance monitoring
- Connection loss protection
- Trade expiry monitoring

## 🚀 Quick Start

### Prerequisites
- Python 3.8 or higher
- Deriv API token (demo or live account)
- Virtual environment (recommended)

### Installation

1. **Clone the repository**
```bash
git clone <repository-url>
cd v10-scalping-bot
```

2. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate     # Windows
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment**
```bash
cp .env.example .env
# Edit .env with your Deriv API credentials
```

5. **Run the bot**

#### 🌐 With Web Dashboard (Recommended)
```bash
# Run with real-time web dashboard
python run_with_dashboard.py

# Dashboard will be available at: http://127.0.0.1:8000
# Browser will open automatically
```

#### 🤖 Headless Mode
```bash
# Production run (no web interface)
python run.py

# Direct run
python -m src.main

# Disable web server
python -m src.main --no-web
```

## 🌐 Web Dashboard Features

The bot includes a comprehensive real-time web dashboard for monitoring and control:

### 📊 Real-Time Monitoring
- **Live Balance Tracking**: Current balance, ROI, and P&L
- **Performance Metrics**: Win rate, total trades, profit factor
- **RSI Indicator**: Live RSI values with overbought/oversold signals
- **Active Trades**: Real-time monitoring of open positions
- **Market Data**: Current tick prices and volatility

### 📈 Data Visualization
- **Balance Chart**: Historical balance progression
- **RSI Chart**: Live RSI indicator with signal zones
- **Trade History**: Complete trade log with results
- **Signal History**: Recent signals with confidence scores

### 🛡️ Risk Management Display
- **Daily P&L Progress**: Current vs. limit ($1.50)
- **Consecutive Losses**: Current streak vs. limit (5)
- **Drawdown Monitor**: Current vs. maximum (40%)
- **Trade Frequency**: Hourly trades vs. limit (15)

### 🎮 Bot Controls
- **Pause/Resume**: Temporarily stop trading
- **Emergency Stop**: Immediate bot shutdown
- **Status Monitoring**: Real-time bot health
- **Connection Status**: WebSocket and API connectivity

### 📱 Responsive Design
- Works on desktop, tablet, and mobile
- Dark theme optimized for trading
- Real-time updates via WebSocket
- Professional trading interface

**Access Dashboard**: http://127.0.0.1:8000 (when bot is running)

## ⚙️ Configuration

### Environment Variables (.env file)

```bash
# Deriv API Configuration
DERIV_API_TOKEN=your_api_token_here
DERIV_APP_ID=85633

# Trading Configuration
SYMBOL=1HZ10V
MAX_STAKE=0.25
MIN_CONFIDENCE=0.6
RSI_PERIOD=14
RSI_OVERBOUGHT=70
RSI_OVERSOLD=30

# Risk Management
MAX_DAILY_LOSS=1.50
MAX_CONSECUTIVE_LOSSES=5
MAX_TRADES_PER_HOUR=15
COOLDOWN_MINUTES=60

# System Configuration
LOG_LEVEL=INFO
SAVE_TRADES=true
REPORT_INTERVAL=3600
```

### Getting Deriv API Token

1. Visit [Deriv API](https://app.deriv.com/account/api-token)
2. Create a new token with trading permissions
3. Copy the token to your .env file
4. **Important**: Start with a demo account for testing

## 📈 Performance Monitoring

### Real-time Metrics
- Current balance and P&L
- Win rate and trade statistics
- Active trades and positions
- Risk metrics and drawdown
- Strategy performance breakdown

### Reports
- **Status Reports**: Every 5 minutes during operation
- **Daily Reports**: Detailed daily performance analysis
- **Final Summary**: Comprehensive session report on shutdown

### Data Storage
- All trades saved to `data/trades/`
- Performance metrics in `data/performance_summary.json`
- Balance history in `data/balance_history.json`
- Logs stored in `logs/` directory

## 🔧 Development

### Project Structure
```
v10-scalping-bot/
├── src/                    # Core application code
│   ├── main.py            # Main application
│   ├── websocket_client.py # Deriv API client
│   ├── market_data.py     # Market data processing
│   ├── signal_generator.py # Trading signals
│   ├── risk_manager.py    # Risk management
│   ├── trade_executor.py  # Trade execution
│   ├── performance_tracker.py # Analytics
│   └── utils.py           # Utilities
├── config/                # Configuration
│   └── settings.py        # Settings management
├── tests/                 # Test files
├── logs/                  # Log files
├── data/                  # Trade data and reports
├── .env                   # Environment variables
├── requirements.txt       # Dependencies
├── run.py                 # Production runner
└── README.md             # This file
```

### Running Tests
```bash
python -m pytest tests/
```

### Code Quality
```bash
# Format code
black src/ config/

# Check types
mypy src/

# Lint code
flake8 src/
```

## 📊 Expected Performance

### Conservative Projections
- **Week 1-2**: $5.00 → $5.50-6.50 (Learning phase)
- **Week 3-4**: $6.50 → $8.00-10.00 (Strategy refinement)
- **Week 5-6**: $10.00 → $15.00-20.00 (Optimization)
- **Week 7-8**: $20.00 → $25.00-35.00 (Scaling)

### Key Metrics Targets
- **Win Rate**: 65-75%
- **Profit Factor**: 1.5-2.0
- **Maximum Drawdown**: <30%
- **Sharpe Ratio**: >1.0

## ⚠️ Important Warnings

### Risk Disclaimer
- **Trading involves significant risk of loss**
- **Never risk money you cannot afford to lose**
- **Past performance does not guarantee future results**
- **Start with demo account for testing**

### Technical Considerations
- Requires stable internet connection
- Monitor system resources during operation
- Keep API credentials secure
- Regular backups of performance data recommended

## 🆘 Troubleshooting

### Common Issues

**Connection Problems**
```bash
# Check internet connection
ping ws.derivws.com

# Verify API token
# Check token permissions in Deriv account
```

**Installation Issues**
```bash
# Update pip
pip install --upgrade pip

# Install dependencies individually
pip install websockets pandas numpy python-dotenv
```

**Performance Issues**
```bash
# Check system resources
htop  # Linux/Mac
# Task Manager on Windows

# Reduce log level in .env
LOG_LEVEL=WARNING
```

### Support
- Check logs in `logs/` directory for detailed error information
- Ensure all environment variables are properly configured
- Verify Deriv API token has correct permissions
- Test with demo account first

## 📝 License

This project is for educational purposes. Use at your own risk.

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📞 Contact

For questions or support, please open an issue in the repository.

---

**Happy Trading! 🚀**

*Remember: The key to successful scalping is discipline, patience, and proper risk management.*