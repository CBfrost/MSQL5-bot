#!/usr/bin/env python3
"""
V10 Scalping Bot with Web Dashboard Launcher
Starts the bot with real-time web monitoring dashboard
"""

import os
import sys
import asyncio
import webbrowser
import time
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.main import main

def setup_environment():
    """Setup environment for bot with dashboard"""
    # Ensure required directories exist
    directories = ['logs', 'data', 'data/trades', 'web/static/css', 'web/static/js', 'web/templates']
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
    
    # Check for .env file
    env_file = Path('.env')
    if not env_file.exists():
        print("⚠️  WARNING: .env file not found!")
        print("📝 Please copy .env.example to .env and configure your Deriv API settings:")
        print("   cp .env.example .env")
        print("   # Then edit .env with your API token")
        return False
    
    return True

def print_startup_banner():
    """Print startup banner with information"""
    print("=" * 60)
    print("🚀 V10 SCALPING BOT WITH WEB DASHBOARD")
    print("=" * 60)
    print("📊 Real-time monitoring dashboard will be available at:")
    print("   🌐 http://127.0.0.1:8000")
    print("")
    print("📈 Dashboard Features:")
    print("   • Real-time balance and P&L tracking")
    print("   • Live RSI and market data")
    print("   • Active trades monitoring")
    print("   • Signal generation history")
    print("   • Risk management status")
    print("   • Performance analytics")
    print("   • Bot control buttons")
    print("")
    print("🛡️  Risk Management:")
    print("   • Max stake: $0.25 per trade")
    print("   • Daily loss limit: $1.50")
    print("   • Max consecutive losses: 5")
    print("   • Max drawdown: 40%")
    print("")
    print("⚠️  Important:")
    print("   • Start with DEMO account for testing")
    print("   • Never risk money you cannot afford to lose")
    print("   • Monitor the dashboard closely")
    print("=" * 60)
    print("")

async def main_with_dashboard():
    """Main function with dashboard integration"""
    try:
        # Setup environment
        if not setup_environment():
            return False
        
        # Print banner
        print_startup_banner()
        
        # Wait a moment for user to read
        print("🔄 Starting bot components...")
        await asyncio.sleep(2)
        
        # Import and run main with web enabled
        success = await main()
        
        return success
        
    except KeyboardInterrupt:
        print("\n🛑 Bot stopped by user")
        return True
    except Exception as e:
        print(f"❌ Fatal error: {e}")
        return False

def open_dashboard_after_delay():
    """Open dashboard in browser after a delay"""
    time.sleep(5)  # Wait 5 seconds for server to start
    try:
        webbrowser.open('http://127.0.0.1:8000')
        print("🌐 Dashboard opened in your default browser")
    except Exception as e:
        print(f"⚠️  Could not auto-open browser: {e}")
        print("📊 Please manually open: http://127.0.0.1:8000")

if __name__ == "__main__":
    print("🤖 V10 Scalping Bot with Web Dashboard")
    print("====================================")
    
    # Check if user wants to auto-open browser
    auto_open = '--no-browser' not in sys.argv
    
    if auto_open:
        # Start browser opener in background
        import threading
        browser_thread = threading.Thread(target=open_dashboard_after_delay, daemon=True)
        browser_thread.start()
    
    # Run the bot
    try:
        success = asyncio.run(main_with_dashboard())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n👋 Goodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"💥 Startup error: {e}")
        sys.exit(1)