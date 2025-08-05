import logging
import asyncio
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum
from datetime import datetime, timezone

from src.websocket_client import DerivWebSocketClient
from src.signal_generator import TradingSignal, SignalType
from src.risk_manager import RiskManager, TradeRisk, TradeDecision
from src.utils import get_current_timestamp, save_json_data

class TradeStatus(Enum):
    """Trade status enumeration"""
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    WON = "WON"
    LOST = "LOST"
    CANCELLED = "CANCELLED"
    ERROR = "ERROR"

class ExecutionResult(Enum):
    """Trade execution result"""
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    REJECTED = "REJECTED"
    ERROR = "ERROR"

@dataclass
class Trade:
    """Trade data structure"""
    trade_id: str
    signal: TradingSignal
    contract_type: str  # CALL or PUT
    stake: float
    duration: int
    entry_price: float
    entry_time: float
    status: TradeStatus
    contract_id: Optional[str] = None
    exit_price: Optional[float] = None
    exit_time: Optional[float] = None
    profit_loss: Optional[float] = None
    payout: Optional[float] = None
    barrier: Optional[float] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'trade_id': self.trade_id,
            'signal': self.signal.to_dict(),
            'contract_type': self.contract_type,
            'stake': self.stake,
            'duration': self.duration,
            'entry_price': self.entry_price,
            'entry_time': self.entry_time,
            'status': self.status.value,
            'contract_id': self.contract_id,
            'exit_price': self.exit_price,
            'exit_time': self.exit_time,
            'profit_loss': self.profit_loss,
            'payout': self.payout,
            'barrier': self.barrier
        }

@dataclass
class ExecutionReport:
    """Trade execution report"""
    result: ExecutionResult
    trade: Optional[Trade]
    error_message: Optional[str]
    risk_assessment: Optional[TradeRisk]
    execution_time_ms: float
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'result': self.result.value,
            'trade': self.trade.to_dict() if self.trade else None,
            'error_message': self.error_message,
            'risk_assessment': self.risk_assessment.to_dict() if self.risk_assessment else None,
            'execution_time_ms': self.execution_time_ms
        }

class TradeExecutor:
    """Advanced trade execution engine"""
    
    def __init__(self, websocket_client: DerivWebSocketClient, risk_manager: RiskManager):
        self.ws_client = websocket_client
        self.risk_manager = risk_manager
        self.logger = logging.getLogger('TradeExecutor')
        
        # Trade tracking
        self.active_trades: Dict[str, Trade] = {}
        self.completed_trades: List[Trade] = []
        self.trade_counter = 0
        
        # Execution metrics
        self.total_executions = 0
        self.successful_executions = 0
        self.failed_executions = 0
        self.rejected_executions = 0
        
        # Contract monitoring
        self.contract_subscriptions: Dict[str, str] = {}  # contract_id -> trade_id
        
        # Setup contract result handler
        self._setup_contract_handlers()
        
    def _setup_contract_handlers(self):
        """Setup handlers for contract results"""
        # This would be called during WebSocket setup
        # For now, we'll handle it in the main trading loop
        pass
    
    async def execute_trade(self, signal: TradingSignal, current_balance: float) -> ExecutionReport:
        """Execute a trade based on signal and risk assessment"""
        start_time = get_current_timestamp()
        
        try:
            # Step 1: Risk Assessment
            risk_assessment = self.risk_manager.assess_trade_risk(signal, current_balance)
            
            if risk_assessment.decision == TradeDecision.REJECTED:
                self.rejected_executions += 1
                return ExecutionReport(
                    result=ExecutionResult.REJECTED,
                    trade=None,
                    error_message=f"Trade rejected: {', '.join(risk_assessment.rejection_reasons)}",
                    risk_assessment=risk_assessment,
                    execution_time_ms=(get_current_timestamp() - start_time) * 1000
                )
            
            # Step 2: Prepare trade parameters
            stake = risk_assessment.recommended_stake
            contract_type = signal.signal_type.value
            duration = signal.duration
            
            # Step 3: Create trade object
            trade_id = self._generate_trade_id()
            trade = Trade(
                trade_id=trade_id,
                signal=signal,
                contract_type=contract_type,
                stake=stake,
                duration=duration,
                entry_price=signal.entry_price,
                entry_time=get_current_timestamp(),
                status=TradeStatus.PENDING
            )
            
            # Step 4: Execute the trade
            execution_result = await self._place_order(trade)
            
            if execution_result:
                # Trade placed successfully
                trade.status = TradeStatus.ACTIVE
                trade.contract_id = execution_result.get('contract_id')
                trade.payout = execution_result.get('payout')
                trade.barrier = execution_result.get('barrier')
                
                # Add to active trades
                self.active_trades[trade_id] = trade
                
                # Subscribe to contract updates if contract_id available
                if trade.contract_id:
                    self.contract_subscriptions[trade.contract_id] = trade_id
                
                self.successful_executions += 1
                self.total_executions += 1
                
                self.logger.info(
                    f"Trade executed successfully: {trade_id} "
                    f"({contract_type} ${stake} for {duration} ticks)"
                )
                
                # Save trade data
                self._save_trade_data(trade)
                
                return ExecutionReport(
                    result=ExecutionResult.SUCCESS,
                    trade=trade,
                    error_message=None,
                    risk_assessment=risk_assessment,
                    execution_time_ms=(get_current_timestamp() - start_time) * 1000
                )
                
            else:
                # Trade execution failed
                trade.status = TradeStatus.ERROR
                self.failed_executions += 1
                self.total_executions += 1
                
                return ExecutionReport(
                    result=ExecutionResult.FAILED,
                    trade=trade,
                    error_message="Failed to place order with broker",
                    risk_assessment=risk_assessment,
                    execution_time_ms=(get_current_timestamp() - start_time) * 1000
                )
                
        except Exception as e:
            self.logger.error(f"Error executing trade: {e}")
            self.failed_executions += 1
            self.total_executions += 1
            
            return ExecutionReport(
                result=ExecutionResult.ERROR,
                trade=None,
                error_message=f"Execution error: {str(e)}",
                risk_assessment=None,
                execution_time_ms=(get_current_timestamp() - start_time) * 1000
            )
    
    async def _place_order(self, trade: Trade) -> Optional[Dict[str, Any]]:
        """Place order with Deriv API"""
        try:
            # Map signal type to Deriv contract type
            contract_type_mapping = {
                'CALL': 'CALL',
                'PUT': 'PUT'
            }
            
            deriv_contract_type = contract_type_mapping.get(trade.contract_type)
            if not deriv_contract_type:
                self.logger.error(f"Invalid contract type: {trade.contract_type}")
                return None
            
            # Place the order
            result = await self.ws_client.buy_contract(
                contract_type=deriv_contract_type,
                duration=trade.duration,
                amount=trade.stake,
                symbol='1HZ10V'  # V10 1s symbol
            )
            
            if result:
                self.logger.info(f"Order placed successfully: {result}")
                return result
            else:
                self.logger.error("Failed to place order - no result returned")
                return None
                
        except Exception as e:
            self.logger.error(f"Error placing order: {e}")
            return None
    
    async def handle_contract_update(self, contract_data: Dict[str, Any]):
        """Handle contract status updates"""
        try:
            contract_id = contract_data.get('proposal_open_contract', {}).get('contract_id')
            if not contract_id or contract_id not in self.contract_subscriptions:
                return
            
            trade_id = self.contract_subscriptions[contract_id]
            if trade_id not in self.active_trades:
                return
            
            trade = self.active_trades[trade_id]
            contract_info = contract_data.get('proposal_open_contract', {})
            
            # Update trade with current contract information
            current_spot = contract_info.get('current_spot')
            if current_spot:
                trade.exit_price = float(current_spot)
            
            # Check if contract is finished
            is_sold = contract_info.get('is_sold', False)
            if is_sold:
                await self._finalize_trade(trade, contract_info)
                
        except Exception as e:
            self.logger.error(f"Error handling contract update: {e}")
    
    async def _finalize_trade(self, trade: Trade, contract_info: Dict[str, Any]):
        """Finalize a completed trade"""
        try:
            # Update trade with final information
            trade.exit_time = get_current_timestamp()
            trade.exit_price = float(contract_info.get('sell_spot', trade.exit_price))
            
            # Calculate profit/loss
            sell_price = float(contract_info.get('sell_price', 0))
            buy_price = float(contract_info.get('buy_price', trade.stake))
            trade.profit_loss = sell_price - buy_price
            
            # Determine win/loss status
            if trade.profit_loss > 0:
                trade.status = TradeStatus.WON
                was_winner = True
            else:
                trade.status = TradeStatus.LOST
                was_winner = False
            
            # Remove from active trades
            if trade.trade_id in self.active_trades:
                del self.active_trades[trade.trade_id]
            
            # Remove contract subscription
            if trade.contract_id and trade.contract_id in self.contract_subscriptions:
                del self.contract_subscriptions[trade.contract_id]
            
            # Add to completed trades
            self.completed_trades.append(trade)
            
            # Update risk manager with trade result
            self.risk_manager.record_trade_result(trade.profit_loss, was_winner)
            
            # Save updated trade data
            self._save_trade_data(trade)
            
            self.logger.info(
                f"Trade finalized: {trade.trade_id} "
                f"({'WON' if was_winner else 'LOST'} ${trade.profit_loss:.2f})"
            )
            
        except Exception as e:
            self.logger.error(f"Error finalizing trade: {e}")
    
    async def check_expired_trades(self):
        """Check for trades that should have expired"""
        try:
            current_time = get_current_timestamp()
            expired_trades = []
            
            for trade in self.active_trades.values():
                # Calculate expected expiry time (approximate)
                expected_expiry = trade.entry_time + (trade.duration * 1.1)  # Add 10% buffer
                
                if current_time > expected_expiry:
                    expired_trades.append(trade)
            
            # Handle expired trades
            for trade in expired_trades:
                self.logger.warning(f"Trade {trade.trade_id} appears to have expired without update")
                
                # Try to get contract status
                if trade.contract_id:
                    # In a real implementation, you'd query the contract status
                    # For now, we'll mark it as an error
                    trade.status = TradeStatus.ERROR
                    trade.exit_time = current_time
                    
                    # Remove from active trades
                    if trade.trade_id in self.active_trades:
                        del self.active_trades[trade.trade_id]
                    
                    self.completed_trades.append(trade)
                    
        except Exception as e:
            self.logger.error(f"Error checking expired trades: {e}")
    
    def _generate_trade_id(self) -> str:
        """Generate unique trade ID"""
        self.trade_counter += 1
        timestamp = int(get_current_timestamp() * 1000)  # milliseconds
        return f"T{timestamp}_{self.trade_counter:04d}"
    
    def _save_trade_data(self, trade: Trade):
        """Save trade data to file"""
        try:
            # Save individual trade
            filename = f"data/trades/trade_{trade.trade_id}.json"
            save_json_data(trade.to_dict(), filename)
            
            # Update trades summary
            self._update_trades_summary()
            
        except Exception as e:
            self.logger.error(f"Error saving trade data: {e}")
    
    def _update_trades_summary(self):
        """Update trades summary file"""
        try:
            summary = {
                'total_executions': self.total_executions,
                'successful_executions': self.successful_executions,
                'failed_executions': self.failed_executions,
                'rejected_executions': self.rejected_executions,
                'active_trades_count': len(self.active_trades),
                'completed_trades_count': len(self.completed_trades),
                'last_updated': get_current_timestamp()
            }
            
            save_json_data(summary, 'data/execution_summary.json')
            
        except Exception as e:
            self.logger.error(f"Error updating trades summary: {e}")
    
    def get_active_trades(self) -> List[Trade]:
        """Get list of active trades"""
        return list(self.active_trades.values())
    
    def get_recent_trades(self, count: int = 10) -> List[Trade]:
        """Get recent completed trades"""
        return self.completed_trades[-count:] if count <= len(self.completed_trades) else self.completed_trades.copy()
    
    def get_execution_stats(self) -> Dict[str, Any]:
        """Get execution statistics"""
        success_rate = 0.0
        if self.total_executions > 0:
            success_rate = (self.successful_executions / self.total_executions) * 100
        
        # Calculate trade performance from completed trades
        winning_trades = sum(1 for trade in self.completed_trades if trade.status == TradeStatus.WON)
        losing_trades = sum(1 for trade in self.completed_trades if trade.status == TradeStatus.LOST)
        total_completed = len(self.completed_trades)
        
        win_rate = 0.0
        if total_completed > 0:
            win_rate = (winning_trades / total_completed) * 100
        
        total_pnl = sum(trade.profit_loss for trade in self.completed_trades if trade.profit_loss is not None)
        
        return {
            'execution_stats': {
                'total_executions': self.total_executions,
                'successful_executions': self.successful_executions,
                'failed_executions': self.failed_executions,
                'rejected_executions': self.rejected_executions,
                'success_rate_pct': round(success_rate, 2)
            },
            'trade_performance': {
                'total_completed_trades': total_completed,
                'winning_trades': winning_trades,
                'losing_trades': losing_trades,
                'win_rate_pct': round(win_rate, 2),
                'total_pnl': round(total_pnl, 2)
            },
            'current_status': {
                'active_trades': len(self.active_trades),
                'pending_contracts': len(self.contract_subscriptions)
            }
        }
    
    def cancel_all_active_trades(self):
        """Cancel all active trades (emergency function)"""
        try:
            cancelled_count = 0
            for trade in list(self.active_trades.values()):
                trade.status = TradeStatus.CANCELLED
                trade.exit_time = get_current_timestamp()
                
                # Move to completed trades
                if trade.trade_id in self.active_trades:
                    del self.active_trades[trade.trade_id]
                
                self.completed_trades.append(trade)
                cancelled_count += 1
            
            # Clear contract subscriptions
            self.contract_subscriptions.clear()
            
            self.logger.warning(f"Cancelled {cancelled_count} active trades")
            
        except Exception as e:
            self.logger.error(f"Error cancelling active trades: {e}")
    
    def get_trade_by_id(self, trade_id: str) -> Optional[Trade]:
        """Get trade by ID from active or completed trades"""
        # Check active trades first
        if trade_id in self.active_trades:
            return self.active_trades[trade_id]
        
        # Check completed trades
        for trade in self.completed_trades:
            if trade.trade_id == trade_id:
                return trade
        
        return None
    
    def cleanup_old_trades(self, max_completed_trades: int = 1000):
        """Clean up old completed trades to prevent memory issues"""
        if len(self.completed_trades) > max_completed_trades:
            # Keep only the most recent trades
            self.completed_trades = self.completed_trades[-max_completed_trades:]
            self.logger.info(f"Cleaned up old trades, keeping {max_completed_trades} most recent")
    
    async def shutdown(self):
        """Graceful shutdown of trade executor"""
        try:
            self.logger.info("Shutting down trade executor...")
            
            # Cancel any active trades
            if self.active_trades:
                self.logger.warning(f"Cancelling {len(self.active_trades)} active trades during shutdown")
                self.cancel_all_active_trades()
            
            # Save final summary
            self._update_trades_summary()
            
            self.logger.info("Trade executor shutdown complete")
            
        except Exception as e:
            self.logger.error(f"Error during trade executor shutdown: {e}")