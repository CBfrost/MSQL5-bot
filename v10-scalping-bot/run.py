#!/usr/bin/env python3
"""
Production runner for V10 Scalping Bot
"""

import os
import sys
import asyncio
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from src.main import main

def setup_environment():
    """Setup environment for production run"""
    # Ensure required directories exist
    directories = ['logs', 'data', 'data/trades']
    for directory in directories:
        Path(directory).mkdir(parents=True, exist_ok=True)
    
    # Check for .env file
    env_file = Path('.env')
    if not env_file.exists():
        print("WARNING: .env file not found. Please copy .env.example to .env and configure your settings.")
        print("Example: cp .env.example .env")
        return False
    
    return True

if __name__ == "__main__":
    print("V10 Scalping Bot - Production Runner")
    print("====================================")
    
    # Setup environment
    if not setup_environment():
        sys.exit(1)
    
    # Run the bot
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nBot stopped by user")
    except Exception as e:
        print(f"Fatal error: {e}")
        sys.exit(1)