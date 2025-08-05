import asyncio
import json
import logging
import websockets
from typing import Dict, Any, Optional, Callable, Awaitable
from datetime import datetime, timezone
import time
from dataclasses import dataclass

from config.settings import APIConfig
from src.utils import get_current_timestamp, RateLimiter

@dataclass
class ConnectionState:
    """Track WebSocket connection state"""
    connected: bool = False
    authenticated: bool = False
    last_ping: float = 0
    reconnect_attempts: int = 0
    last_error: Optional[str] = None

class DerivWebSocketClient:
    """Deriv WebSocket API client with robust connection management"""
    
    def __init__(self, config: APIConfig):
        self.config = config
        self.logger = logging.getLogger('DerivWebSocket')
        self.websocket: Optional[websockets.WebSocketServerProtocol] = None
        self.state = ConnectionState()
        
        # Message handling
        self.message_handlers: Dict[str, Callable] = {}
        self.request_id_counter = 0
        self.pending_requests: Dict[int, asyncio.Future] = {}
        
        # Rate limiting
        self.rate_limiter = RateLimiter(max_calls=30, time_window=60)  # 30 calls per minute
        
        # Connection management
        self.max_reconnect_attempts = 10
        self.reconnect_delay = 5  # seconds
        self.ping_interval = 30  # seconds
        self.heartbeat_task: Optional[asyncio.Task] = None
        
        # Subscribe to required streams
        self.subscriptions = set()
        
    async def connect(self) -> bool:
        """Establish WebSocket connection and authenticate"""
        try:
            self.logger.info("Connecting to Deriv WebSocket...")
            
            # Connect to WebSocket
            self.websocket = await websockets.connect(
                f"{self.config.websocket_url}?app_id={self.config.app_id}",
                ping_interval=None,  # We'll handle pings manually
                ping_timeout=None,
                close_timeout=10
            )
            
            self.state.connected = True
            self.state.reconnect_attempts = 0
            self.logger.info("WebSocket connected successfully")
            
            # Start message listener
            asyncio.create_task(self._message_listener())
            
            # Start heartbeat
            self.heartbeat_task = asyncio.create_task(self._heartbeat())
            
            # Authenticate
            if await self._authenticate():
                self.logger.info("Authentication successful")
                return True
            else:
                self.logger.error("Authentication failed")
                await self.disconnect()
                return False
                
        except Exception as e:
            self.logger.error(f"Connection failed: {e}")
            self.state.last_error = str(e)
            return False
    
    async def _authenticate(self) -> bool:
        """Authenticate with API token"""
        try:
            response = await self.send_request({
                "authorize": self.config.token
            })
            
            if response and not response.get('error'):
                self.state.authenticated = True
                return True
            else:
                error_msg = response.get('error', {}).get('message', 'Unknown error') if response else 'No response'
                self.logger.error(f"Authentication error: {error_msg}")
                return False
                
        except Exception as e:
            self.logger.error(f"Authentication exception: {e}")
            return False
    
    async def disconnect(self):
        """Gracefully disconnect from WebSocket"""
        self.logger.info("Disconnecting from WebSocket...")
        
        self.state.connected = False
        self.state.authenticated = False
        
        # Cancel heartbeat
        if self.heartbeat_task:
            self.heartbeat_task.cancel()
            
        # Close WebSocket
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
            
        # Clear pending requests
        for future in self.pending_requests.values():
            if not future.done():
                future.cancel()
        self.pending_requests.clear()
        
        self.logger.info("WebSocket disconnected")
    
    async def _message_listener(self):
        """Listen for incoming WebSocket messages"""
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    await self._handle_message(data)
                except json.JSONDecodeError as e:
                    self.logger.error(f"Failed to parse message: {e}")
                except Exception as e:
                    self.logger.error(f"Error handling message: {e}")
                    
        except websockets.exceptions.ConnectionClosed:
            self.logger.warning("WebSocket connection closed")
            self.state.connected = False
        except Exception as e:
            self.logger.error(f"Message listener error: {e}")
            self.state.connected = False
    
    async def _handle_message(self, data: Dict[str, Any]):
        """Handle incoming WebSocket message"""
        # Handle request responses
        if 'req_id' in data:
            req_id = data['req_id']
            if req_id in self.pending_requests:
                future = self.pending_requests.pop(req_id)
                if not future.done():
                    future.set_result(data)
                return
        
        # Handle subscriptions and other messages
        msg_type = data.get('msg_type')
        if msg_type in self.message_handlers:
            try:
                await self.message_handlers[msg_type](data)
            except Exception as e:
                self.logger.error(f"Error in message handler for {msg_type}: {e}")
        
        # Log unhandled messages for debugging
        if msg_type not in self.message_handlers and 'req_id' not in data:
            self.logger.debug(f"Unhandled message type: {msg_type}")
    
    async def send_request(self, request: Dict[str, Any], timeout: float = 15.0) -> Optional[Dict[str, Any]]:
        """Send request and wait for response"""
        if not self.state.connected or not self.websocket:
            self.logger.error("Cannot send request: not connected")
            return None
        
        if not self.rate_limiter.can_proceed():
            self.logger.warning("Rate limit exceeded, waiting...")
            await asyncio.sleep(1)
            return None
        
        # Add request ID
        self.request_id_counter += 1
        req_id = self.request_id_counter
        request['req_id'] = req_id
        
        # Create future for response
        future = asyncio.Future()
        self.pending_requests[req_id] = future
        
        try:
            # Send request
            await self.websocket.send(json.dumps(request))
            self.rate_limiter.record_call()
            
            # Wait for response
            response = await asyncio.wait_for(future, timeout=timeout)
            return response
            
        except asyncio.TimeoutError:
            self.logger.error(f"Request {req_id} timed out")
            self.pending_requests.pop(req_id, None)
            return None
        except Exception as e:
            self.logger.error(f"Error sending request: {e}")
            self.pending_requests.pop(req_id, None)
            return None
    
    async def subscribe_ticks(self, symbol: str, callback: Callable[[Dict[str, Any]], Awaitable[None]]) -> bool:
        """Subscribe to tick data for a symbol"""
        try:
            # Register callback
            self.message_handlers['tick'] = callback
            
            # Send subscription request
            response = await self.send_request({
                "ticks": symbol,
                "subscribe": 1
            })
            
            if response and not response.get('error'):
                self.subscriptions.add(f"ticks_{symbol}")
                self.logger.info(f"Successfully subscribed to ticks for {symbol}")
                return True
            else:
                error_msg = response.get('error', {}).get('message', 'Unknown error') if response else 'No response'
                self.logger.error(f"Failed to subscribe to ticks: {error_msg}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error subscribing to ticks: {e}")
            return False
    
    async def buy_contract(self, contract_type: str, duration: int, amount: float, symbol: str) -> Optional[Dict[str, Any]]:
        """Place a buy order for binary options contract"""
        try:
            request = {
                "buy": 1,
                "price": amount,
                "parameters": {
                    "contract_type": contract_type,
                    "symbol": symbol,
                    "duration": duration,
                    "duration_unit": "t",  # ticks
                    "amount": amount,
                    "basis": "stake"
                }
            }
            
            response = await self.send_request(request, timeout=15.0)
            
            if response and not response.get('error'):
                self.logger.info(f"Order placed successfully: {contract_type} on {symbol}")
                return response.get('buy')
            else:
                error_msg = response.get('error', {}).get('message', 'Unknown error') if response else 'No response'
                self.logger.error(f"Failed to place order: {error_msg}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error placing order: {e}")
            return None
    
    async def get_balance(self) -> Optional[float]:
        """Get current account balance"""
        try:
            response = await self.send_request({"balance": 1})
            
            if response and not response.get('error'):
                balance_data = response.get('balance', {})
                return float(balance_data.get('balance', 0))
            else:
                error_msg = response.get('error', {}).get('message', 'Unknown error') if response else 'No response'
                self.logger.error(f"Failed to get balance: {error_msg}")
                return None
                
        except Exception as e:
            self.logger.error(f"Error getting balance: {e}")
            return None
    
    async def _heartbeat(self):
        """Send periodic pings to keep connection alive"""
        while self.state.connected:
            try:
                await asyncio.sleep(self.ping_interval)
                
                if self.state.connected and self.websocket:
                    # Send ping
                    await self.send_request({"ping": 1})
                    self.state.last_ping = get_current_timestamp()
                    
            except Exception as e:
                self.logger.error(f"Heartbeat error: {e}")
                break
    
    async def reconnect(self) -> bool:
        """Attempt to reconnect with exponential backoff"""
        if self.state.reconnect_attempts >= self.max_reconnect_attempts:
            self.logger.error("Max reconnection attempts reached")
            return False
        
        self.state.reconnect_attempts += 1
        delay = min(self.reconnect_delay * (2 ** (self.state.reconnect_attempts - 1)), 300)  # Max 5 minutes
        
        self.logger.info(f"Reconnection attempt {self.state.reconnect_attempts} in {delay} seconds...")
        await asyncio.sleep(delay)
        
        # Disconnect cleanly first
        await self.disconnect()
        
        # Attempt reconnection
        if await self.connect():
            # Restore subscriptions
            await self._restore_subscriptions()
            return True
        
        return False
    
    async def _restore_subscriptions(self):
        """Restore subscriptions after reconnection"""
        for subscription in self.subscriptions.copy():
            if subscription.startswith("ticks_"):
                symbol = subscription.replace("ticks_", "")
                # Re-subscribe (callback should already be registered)
                await self.send_request({
                    "ticks": symbol,
                    "subscribe": 1
                })
    
    def is_connected(self) -> bool:
        """Check if WebSocket is connected and authenticated"""
        return self.state.connected and self.state.authenticated
    
    def get_connection_info(self) -> Dict[str, Any]:
        """Get connection status information"""
        return {
            "connected": self.state.connected,
            "authenticated": self.state.authenticated,
            "last_ping": self.state.last_ping,
            "reconnect_attempts": self.state.reconnect_attempts,
            "last_error": self.state.last_error,
            "subscriptions": list(self.subscriptions)
        }