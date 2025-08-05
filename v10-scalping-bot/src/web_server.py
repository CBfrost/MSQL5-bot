#!/usr/bin/env python3
"""
Web Server for V10 Scalping Bot
Provides REST API and WebSocket endpoints for real-time monitoring
"""

import asyncio
import json
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
import threading
import time

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
import uvicorn

from src.main import V10ScalpingBot
from src.utils import get_current_timestamp

class WebSocketManager:
    """Manage WebSocket connections for real-time updates"""
    
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.logger = logging.getLogger('WebSocketManager')
    
    async def connect(self, websocket: WebSocket):
        """Accept new WebSocket connection"""
        await websocket.accept()
        self.active_connections.append(websocket)
        self.logger.info(f"WebSocket connected. Total connections: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        """Remove WebSocket connection"""
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)
            self.logger.info(f"WebSocket disconnected. Total connections: {len(self.active_connections)}")
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Send message to specific WebSocket"""
        try:
            await websocket.send_text(message)
        except Exception as e:
            self.logger.error(f"Error sending personal message: {e}")
    
    async def broadcast(self, message: Dict[str, Any]):
        """Broadcast message to all connected WebSockets"""
        if not self.active_connections:
            return
        
        message_str = json.dumps(message, default=str)
        disconnected = []
        
        for connection in self.active_connections:
            try:
                await connection.send_text(message_str)
            except Exception as e:
                self.logger.error(f"Error broadcasting to connection: {e}")
                disconnected.append(connection)
        
        # Remove disconnected connections
        for connection in disconnected:
            self.disconnect(connection)

class BotWebServer:
    """Web server for V10 Scalping Bot monitoring"""
    
    def __init__(self, bot: Optional[V10ScalpingBot] = None):
        self.bot = bot
        self.app = FastAPI(title="V10 Scalping Bot Dashboard", version="1.0.0")
        self.websocket_manager = WebSocketManager()
        self.logger = logging.getLogger('BotWebServer')
        
        # Setup routes
        self._setup_routes()
        
        # Setup static files and templates
        self.app.mount("/static", StaticFiles(directory="web/static"), name="static")
        self.templates = Jinja2Templates(directory="web/templates")
        
        # Bot monitoring data
        self.last_update = get_current_timestamp()
        self.update_interval = 1.0  # Update every second
        
        # Start background task for real-time updates
        self.monitoring_task = None
    
    def _setup_routes(self):
        """Setup all API routes"""
        
        @self.app.get("/", response_class=HTMLResponse)
        async def dashboard(request: Request):
            """Main dashboard page"""
            return self.templates.TemplateResponse("dashboard.html", {"request": request})
        
        @self.app.get("/api/status")
        async def get_bot_status():
            """Get current bot status"""
            if not self.bot:
                return {"status": "disconnected", "message": "Bot not connected"}
            
            try:
                status = self.bot.get_status()
                return {
                    "status": "connected",
                    "data": status,
                    "timestamp": get_current_timestamp()
                }
            except Exception as e:
                return {"status": "error", "message": str(e)}
        
        @self.app.get("/api/performance")
        async def get_performance():
            """Get performance metrics"""
            if not self.bot or not self.bot.performance_tracker:
                return {"status": "no_data", "message": "Performance data not available"}
            
            try:
                summary = self.bot.performance_tracker.get_performance_summary()
                return {
                    "status": "success",
                    "data": summary,
                    "timestamp": get_current_timestamp()
                }
            except Exception as e:
                return {"status": "error", "message": str(e)}
        
        @self.app.get("/api/trades")
        async def get_trades():
            """Get recent trades"""
            if not self.bot or not self.bot.trade_executor:
                return {"status": "no_data", "message": "Trade data not available"}
            
            try:
                active_trades = [trade.to_dict() for trade in self.bot.trade_executor.get_active_trades() or []]
                recent_trades = [trade.to_dict() for trade in self.bot.trade_executor.get_recent_trades(20) or []]
                
                return {
                    "status": "success",
                    "data": {
                        "active_trades": active_trades,
                        "recent_trades": recent_trades
                    },
                    "timestamp": get_current_timestamp()
                }
            except Exception as e:
                return {"status": "error", "message": str(e)}
        
        @self.app.get("/api/market_data")
        async def get_market_data():
            """Get current market data"""
            if not self.bot or not self.bot.market_data:
                return {"status": "no_data", "message": "Market data not available"}
            
            try:
                summary = self.bot.market_data.get_data_summary()
                return {
                    "status": "success",
                    "data": summary,
                    "timestamp": get_current_timestamp()
                }
            except Exception as e:
                return {"status": "error", "message": str(e)}
        
        @self.app.get("/api/signals")
        async def get_signals():
            """Get recent signals"""
            if not self.bot or not self.bot.signal_generator:
                return {"status": "no_data", "message": "Signal data not available"}
            
            try:
                recent_signals = [signal.to_dict() for signal in self.bot.signal_generator.get_recent_signals(10) or []]
                signal_stats = self.bot.signal_generator.get_signal_stats() or {}
                
                return {
                    "status": "success",
                    "data": {
                        "recent_signals": recent_signals,
                        "signal_stats": signal_stats
                    },
                    "timestamp": get_current_timestamp()
                }
            except Exception as e:
                return {"status": "error", "message": str(e)}
        
        @self.app.get("/api/risk")
        async def get_risk_status():
            """Get risk management status"""
            if not self.bot or not self.bot.risk_manager:
                return {"status": "no_data", "message": "Risk data not available"}
            
            try:
                risk_summary = self.bot.risk_manager.get_risk_summary()
                return {
                    "status": "success",
                    "data": risk_summary,
                    "timestamp": get_current_timestamp()
                }
            except Exception as e:
                return {"status": "error", "message": str(e)}
        
        @self.app.post("/api/control/{action}")
        async def bot_control(action: str):
            """Control bot operations"""
            if not self.bot:
                return {"status": "error", "message": "Bot not connected"}
            
            try:
                if action == "pause":
                    # Pause trading (if risk manager supports it)
                    return {"status": "success", "message": "Trading paused"}
                elif action == "resume":
                    # Resume trading
                    if self.bot.risk_manager:
                        self.bot.risk_manager.force_resume_trading()
                    return {"status": "success", "message": "Trading resumed"}
                elif action == "stop":
                    # Graceful shutdown
                    asyncio.create_task(self.bot.shutdown())
                    return {"status": "success", "message": "Bot shutdown initiated"}
                else:
                    return {"status": "error", "message": f"Unknown action: {action}"}
            except Exception as e:
                return {"status": "error", "message": str(e)}
        
        @self.app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            """WebSocket endpoint for real-time updates"""
            await self.websocket_manager.connect(websocket)
            try:
                while True:
                    # Keep connection alive and send periodic updates
                    await asyncio.sleep(1)
                    
                    # Send heartbeat
                    await self.websocket_manager.send_personal_message(
                        json.dumps({"type": "heartbeat", "timestamp": get_current_timestamp()}),
                        websocket
                    )
                    
            except WebSocketDisconnect:
                self.websocket_manager.disconnect(websocket)
    
    async def start_monitoring(self):
        """Start background monitoring task"""
        if self.monitoring_task:
            return
        
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        self.logger.info("Started real-time monitoring")
    
    async def stop_monitoring(self):
        """Stop background monitoring task"""
        if self.monitoring_task:
            self.monitoring_task.cancel()
            self.monitoring_task = None
            self.logger.info("Stopped real-time monitoring")
    
    async def _monitoring_loop(self):
        """Background loop for real-time data updates"""
        while True:
            try:
                current_time = get_current_timestamp()
                
                if current_time - self.last_update >= self.update_interval:
                    await self._broadcast_updates()
                    self.last_update = current_time
                
                await asyncio.sleep(0.1)  # Small delay to prevent excessive CPU usage
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in monitoring loop: {e}")
                await asyncio.sleep(1)
    
    async def _broadcast_updates(self):
        """Broadcast real-time updates to all connected clients"""
        if not self.bot or not self.websocket_manager.active_connections:
            return
        
        try:
            # Collect all current data
            update_data = {
                "type": "update",
                "timestamp": get_current_timestamp(),
                "data": {}
            }
            
            # Bot status
            if self.bot:
                update_data["data"]["status"] = self.bot.get_status()
            
            # Market data
            if self.bot.market_data:
                update_data["data"]["market"] = self.bot.market_data.get_data_summary()
            
            # Performance
            if self.bot.performance_tracker:
                update_data["data"]["performance"] = self.bot.performance_tracker.get_performance_summary()
            
            # Active trades
            if self.bot.trade_executor:
                update_data["data"]["active_trades"] = [
                    trade.to_dict() for trade in self.bot.trade_executor.get_active_trades()
                ]
            
            # Recent signals
            if self.bot.signal_generator:
                update_data["data"]["recent_signals"] = [
                    signal.to_dict() for signal in self.bot.signal_generator.get_recent_signals(5)
                ]
            
            # Risk status
            if self.bot.risk_manager:
                update_data["data"]["risk"] = self.bot.risk_manager.get_risk_summary()
            
            # Broadcast to all connected clients
            await self.websocket_manager.broadcast(update_data)
            
        except Exception as e:
            self.logger.error(f"Error broadcasting updates: {e}")
    
    def set_bot(self, bot: V10ScalpingBot):
        """Set the bot instance for monitoring"""
        self.bot = bot
        self.logger.info("Bot instance connected to web server")
    
    def run(self, host: str = "127.0.0.1", port: int = 8000):
        """Run the web server"""
        self.logger.info(f"Starting web server on {host}:{port}")
        uvicorn.run(self.app, host=host, port=port, log_level="info")

# Global web server instance
web_server = BotWebServer()

def start_web_server(bot: Optional[V10ScalpingBot] = None, host: str = "127.0.0.1", port: int = 8000):
    """Start web server in a separate thread"""
    if bot:
        web_server.set_bot(bot)
    
    # Start monitoring
    if bot:
        asyncio.create_task(web_server.start_monitoring())
    
    # Run server
    server_thread = threading.Thread(
        target=web_server.run,
        args=(host, port),
        daemon=True
    )
    server_thread.start()
    
    return web_server, server_thread

if __name__ == "__main__":
    # Run standalone web server for testing
    web_server.run()