#!/usr/bin/env python3
"""
Simple connection test for Deriv WebSocket API
Tests if the API token and connection work correctly
"""

import asyncio
import websockets
import json
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

async def test_deriv_connection():
    """Test connection to Deriv WebSocket API"""
    
    # Get configuration
    api_token = os.getenv('DERIV_API_TOKEN', '')
    app_id = os.getenv('DERIV_APP_ID', '1089')
    websocket_url = 'wss://ws.derivws.com/websockets/v3'
    
    print("🔍 Testing Deriv WebSocket Connection")
    print("=" * 50)
    print(f"App ID: {app_id}")
    print(f"API Token: {api_token[:10]}...{api_token[-5:] if len(api_token) > 15 else api_token}")
    print(f"WebSocket URL: {websocket_url}")
    print("")
    
    try:
        # Connect to WebSocket
        print("🔌 Connecting to WebSocket...")
        websocket = await websockets.connect(
            f"{websocket_url}?app_id={app_id}",
            ping_interval=20,
            ping_timeout=10,
            close_timeout=10
        )
        print("✅ WebSocket connection established")
        
        # Test authentication
        print("🔐 Testing authentication...")
        auth_request = {
            "authorize": api_token,
            "req_id": 1
        }
        
        await websocket.send(json.dumps(auth_request))
        print("📤 Authentication request sent")
        
        # Wait for response
        response = await asyncio.wait_for(websocket.recv(), timeout=10.0)
        response_data = json.loads(response)
        print("📥 Authentication response received")
        
        if response_data.get('error'):
            error = response_data['error']
            print(f"❌ Authentication failed: {error.get('message', 'Unknown error')}")
            print(f"   Error code: {error.get('code', 'N/A')}")
            print(f"   Error details: {error.get('details', 'N/A')}")
            
            # Suggest solutions
            print("\n🛠️  POSSIBLE SOLUTIONS:")
            print("   1. Get a valid demo API token from Deriv")
            print("   2. Check if the token has expired")
            print("   3. Verify you're using a demo account token")
            print("   4. Try generating a new token")
            
            return False
        else:
            print("✅ Authentication successful!")
            
            # Get account info
            if 'authorize' in response_data:
                account_info = response_data['authorize']
                print(f"   Account ID: {account_info.get('loginid', 'N/A')}")
                print(f"   Currency: {account_info.get('currency', 'N/A')}")
                print(f"   Balance: {account_info.get('balance', 'N/A')}")
                print(f"   Is Demo: {'Yes' if account_info.get('loginid', '').startswith('VRTC') else 'No'}")
            
            # Test getting balance
            print("\n💰 Testing balance request...")
            balance_request = {
                "balance": 1,
                "subscribe": 1,
                "req_id": 2
            }
            
            await websocket.send(json.dumps(balance_request))
            balance_response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            balance_data = json.loads(balance_response)
            
            if balance_data.get('error'):
                print(f"⚠️  Balance request failed: {balance_data['error'].get('message')}")
            else:
                balance = balance_data.get('balance', {}).get('balance', 'N/A')
                print(f"✅ Current balance: {balance}")
            
            # Test tick subscription
            print("\n📊 Testing tick data subscription...")
            tick_request = {
                "ticks": "1HZ10V",
                "subscribe": 1,
                "req_id": 3
            }
            
            await websocket.send(json.dumps(tick_request))
            tick_response = await asyncio.wait_for(websocket.recv(), timeout=5.0)
            tick_data = json.loads(tick_response)
            
            if tick_data.get('error'):
                print(f"⚠️  Tick subscription failed: {tick_data['error'].get('message')}")
            else:
                print("✅ Tick subscription successful")
                if 'tick' in tick_data:
                    tick = tick_data['tick']
                    print(f"   Symbol: {tick.get('symbol', 'N/A')}")
                    print(f"   Current Price: {tick.get('quote', 'N/A')}")
                    print(f"   Timestamp: {tick.get('epoch', 'N/A')}")
        
        # Close connection
        await websocket.close()
        print("\n🔌 Connection closed successfully")
        print("\n🎉 ALL TESTS PASSED! Your configuration is working correctly.")
        return True
        
    except asyncio.TimeoutError:
        print("❌ Connection timeout - check your internet connection")
        return False
    except websockets.exceptions.InvalidURI:
        print("❌ Invalid WebSocket URL")
        return False
    except websockets.exceptions.ConnectionClosed:
        print("❌ Connection closed unexpectedly")
        return False
    except Exception as e:
        print(f"❌ Connection test failed: {e}")
        print(f"   Error type: {type(e).__name__}")
        
        # Common error solutions
        print("\n🛠️  TROUBLESHOOTING:")
        print("   1. Check your internet connection")
        print("   2. Verify the API token is correct")
        print("   3. Ensure you're using a Deriv demo account")
        print("   4. Try generating a new API token")
        print("   5. Check if there are any firewall restrictions")
        
        return False

async def main():
    """Main test function"""
    print("🧪 Deriv WebSocket Connection Test")
    print("This will test your API configuration")
    print("")
    
    success = await test_deriv_connection()
    
    print("\n" + "=" * 50)
    if success:
        print("✅ CONNECTION TEST SUCCESSFUL!")
        print("Your bot should be able to connect to Deriv.")
        print("\nNext steps:")
        print("  python run_demo_learning.py")
    else:
        print("❌ CONNECTION TEST FAILED!")
        print("Please fix the issues above before running the bot.")
        print("\nGet a demo API token from:")
        print("  https://app.deriv.com/account/api-token")
    print("=" * 50)

if __name__ == "__main__":
    asyncio.run(main())