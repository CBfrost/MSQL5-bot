// V10 Scalping Bot Dashboard JavaScript

class BotDashboard {
    constructor() {
        this.ws = null;
        this.isConnected = false;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 5;
        this.reconnectDelay = 5000; // 5 seconds
        
        // Charts
        this.balanceChart = null;
        this.rsiChart = null;
        
        // Data storage
        this.balanceHistory = [];
        this.rsiHistory = [];
        this.maxDataPoints = 50;
        
        // Initialize dashboard
        this.init();
    }
    
    init() {
        console.log('Initializing V10 Scalping Bot Dashboard...');
        
        // Initialize charts
        this.initCharts();
        
        // Connect to WebSocket
        this.connectWebSocket();
        
        // Load initial data
        this.loadInitialData();
        
        // Setup periodic data refresh
        setInterval(() => this.refreshData(), 5000); // Refresh every 5 seconds
        
        console.log('Dashboard initialized');
    }
    
    connectWebSocket() {
        const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${protocol}//${window.location.host}/ws`;
        
        try {
            this.ws = new WebSocket(wsUrl);
            
            this.ws.onopen = () => {
                console.log('WebSocket connected');
                this.isConnected = true;
                this.reconnectAttempts = 0;
                this.updateConnectionStatus(true);
            };
            
            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    this.handleWebSocketMessage(data);
                } catch (error) {
                    console.error('Error parsing WebSocket message:', error);
                }
            };
            
            this.ws.onclose = () => {
                console.log('WebSocket disconnected');
                this.isConnected = false;
                this.updateConnectionStatus(false);
                this.attemptReconnect();
            };
            
            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.isConnected = false;
                this.updateConnectionStatus(false);
            };
            
        } catch (error) {
            console.error('Error creating WebSocket connection:', error);
            this.updateConnectionStatus(false);
        }
    }
    
    attemptReconnect() {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
            this.reconnectAttempts++;
            console.log(`Attempting to reconnect... (${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
            
            setTimeout(() => {
                this.connectWebSocket();
            }, this.reconnectDelay);
        } else {
            console.error('Max reconnection attempts reached');
        }
    }
    
    handleWebSocketMessage(data) {
        if (data.type === 'update' && data.data) {
            this.updateDashboard(data.data);
        } else if (data.type === 'heartbeat') {
            // Handle heartbeat
            console.log('Heartbeat received');
        }
    }
    
    updateConnectionStatus(connected) {
        const statusIcon = document.getElementById('connection-status');
        const statusText = document.getElementById('connection-text');
        
        if (connected) {
            statusIcon.className = 'fas fa-circle text-success me-2 connected';
            statusText.textContent = 'Connected';
        } else {
            statusIcon.className = 'fas fa-circle text-danger me-2';
            statusText.textContent = 'Disconnected';
        }
    }
    
    async loadInitialData() {
        try {
            // Load all initial data in parallel
            const [statusRes, performanceRes, tradesRes, marketRes, signalsRes, riskRes] = await Promise.all([
                fetch('/api/status'),
                fetch('/api/performance'),
                fetch('/api/trades'),
                fetch('/api/market_data'),
                fetch('/api/signals'),
                fetch('/api/risk')
            ]);
            
            const data = {
                status: await statusRes.json(),
                performance: await performanceRes.json(),
                trades: await tradesRes.json(),
                market: await marketRes.json(),
                signals: await signalsRes.json(),
                risk: await riskRes.json()
            };
            
            this.updateDashboard(data);
            
        } catch (error) {
            console.error('Error loading initial data:', error);
        }
    }
    
    async refreshData() {
        if (!this.isConnected) {
            await this.loadInitialData();
        }
    }
    
    updateDashboard(data) {
        try {
            // Update status
            if (data.status && data.status.status === 'connected') {
                this.updateBotStatus(data.status.data);
            }
            
            // Update performance
            if (data.performance && data.performance.status === 'success') {
                this.updatePerformance(data.performance.data);
            }
            
            // Update trades
            if (data.trades && data.trades.status === 'success') {
                this.updateTrades(data.trades.data);
            }
            
            // Update market data
            if (data.market && data.market.status === 'success') {
                this.updateMarketData(data.market.data);
            }
            
            // Update signals
            if (data.signals && data.signals.status === 'success') {
                this.updateSignals(data.signals.data);
            }
            
            // Update risk
            if (data.risk && data.risk.status === 'success') {
                this.updateRisk(data.risk.data);
            }
            
        } catch (error) {
            console.error('Error updating dashboard:', error);
        }
    }
    
    updateBotStatus(status) {
        const botStatusEl = document.getElementById('bot-status');
        const runtimeEl = document.getElementById('bot-runtime');
        
        if (status.running) {
            botStatusEl.textContent = 'Running';
            botStatusEl.className = 'mb-0 text-success';
        } else {
            botStatusEl.textContent = 'Stopped';
            botStatusEl.className = 'mb-0 text-danger';
        }
        
        const runtime = Math.floor(status.runtime_seconds || 0);
        const hours = Math.floor(runtime / 3600);
        const minutes = Math.floor((runtime % 3600) / 60);
        const seconds = runtime % 60;
        
        runtimeEl.textContent = `Runtime: ${hours}h ${minutes}m ${seconds}s`;
    }
    
    updatePerformance(performance) {
        // Update balance card
        const balanceEl = document.getElementById('current-balance');
        const balanceChangeEl = document.getElementById('balance-change');
        const winRateEl = document.getElementById('win-rate');
        const totalTradesEl = document.getElementById('total-trades');
        
        if (performance.balance_info) {
            balanceEl.textContent = `$${performance.balance_info.current_balance.toFixed(2)}`;
            balanceChangeEl.textContent = `ROI: ${performance.balance_info.roi_percent.toFixed(2)}%`;
            
            // Update balance chart
            this.updateBalanceChart(performance.balance_info.current_balance);
        }
        
        if (performance.performance_metrics) {
            winRateEl.textContent = `${performance.performance_metrics.win_rate.toFixed(1)}%`;
            totalTradesEl.textContent = `${performance.performance_metrics.total_trades} trades`;
        }
    }
    
    updateMarketData(market) {
        const rsiEl = document.getElementById('current-rsi');
        const rsiSignalEl = document.getElementById('rsi-signal');
        
        if (market.rsi !== undefined) {
            rsiEl.textContent = market.rsi.toFixed(1);
            
            // Update RSI signal and color
            let signalText = 'Neutral';
            let signalClass = 'rsi-neutral';
            
            if (market.rsi > 70) {
                signalText = market.rsi > 85 ? 'Strong Sell' : 'Overbought';
                signalClass = 'rsi-overbought';
            } else if (market.rsi < 30) {
                signalText = market.rsi < 15 ? 'Strong Buy' : 'Oversold';
                signalClass = 'rsi-oversold';
            }
            
            rsiSignalEl.textContent = signalText;
            rsiEl.className = `mb-0 ${signalClass}`;
            
            // Update RSI chart
            this.updateRSIChart(market.rsi);
        }
    }
    
    updateTrades(trades) {
        // Update active trades count
        const activeCountEl = document.getElementById('active-trades-count');
        const activeTableEl = document.getElementById('active-trades-table');
        
        if (trades.active_trades) {
            activeCountEl.textContent = trades.active_trades.length;
            
            if (trades.active_trades.length === 0) {
                activeTableEl.innerHTML = '<tr><td colspan="6" class="text-center text-muted">No active trades</td></tr>';
            } else {
                activeTableEl.innerHTML = trades.active_trades.map(trade => `
                    <tr>
                        <td>${trade.trade_id.substring(0, 8)}</td>
                        <td><span class="signal-${trade.contract_type.toLowerCase()}">${trade.contract_type}</span></td>
                        <td>$${trade.stake.toFixed(2)}</td>
                        <td>${trade.duration}t</td>
                        <td>${trade.entry_price.toFixed(5)}</td>
                        <td><span class="trade-active">${trade.status}</span></td>
                    </tr>
                `).join('');
            }
        }
        
        // Update recent trades
        const recentTableEl = document.getElementById('recent-trades-table');
        if (trades.recent_trades) {
            if (trades.recent_trades.length === 0) {
                recentTableEl.innerHTML = '<tr><td colspan="10" class="text-center text-muted">No completed trades yet</td></tr>';
            } else {
                recentTableEl.innerHTML = trades.recent_trades.slice(0, 10).map(trade => {
                    const exitTime = trade.exit_time ? new Date(trade.exit_time * 1000).toLocaleTimeString() : '-';
                    const exitPrice = trade.exit_price ? trade.exit_price.toFixed(5) : '-';
                    const pnl = trade.profit_loss !== null ? `$${trade.profit_loss.toFixed(2)}` : '-';
                    const statusClass = trade.status === 'WON' ? 'trade-won' : 'trade-lost';
                    
                    return `
                        <tr>
                            <td>${exitTime}</td>
                            <td>${trade.trade_id.substring(0, 8)}</td>
                            <td><span class="signal-${trade.contract_type.toLowerCase()}">${trade.contract_type}</span></td>
                            <td>$${trade.stake.toFixed(2)}</td>
                            <td>${trade.duration}t</td>
                            <td>${trade.entry_price.toFixed(5)}</td>
                            <td>${exitPrice}</td>
                            <td>${pnl}</td>
                            <td><span class="${statusClass}">${trade.status}</span></td>
                            <td>${trade.signal.strategy}</td>
                        </tr>
                    `;
                }).join('');
            }
        }
    }
    
    updateSignals(signals) {
        const signalsCountEl = document.getElementById('signals-count');
        const signalsTableEl = document.getElementById('signals-table');
        
        if (signals.recent_signals) {
            signalsCountEl.textContent = signals.recent_signals.length;
            
            if (signals.recent_signals.length === 0) {
                signalsTableEl.innerHTML = '<tr><td colspan="5" class="text-center text-muted">No signals yet</td></tr>';
            } else {
                signalsTableEl.innerHTML = signals.recent_signals.slice(0, 10).map(signal => {
                    const time = new Date(signal.timestamp * 1000).toLocaleTimeString();
                    const signalClass = signal.signal_type === 'CALL' ? 'signal-call' : 'signal-put';
                    
                    return `
                        <tr>
                            <td>${time}</td>
                            <td><span class="${signalClass}">${signal.signal_type}</span></td>
                            <td>${(signal.confidence * 100).toFixed(1)}%</td>
                            <td>${signal.strategy}</td>
                            <td>${signal.rsi_value.toFixed(1)}</td>
                        </tr>
                    `;
                }).join('');
            }
        }
    }
    
    updateRisk(risk) {
        // Update trading status
        const tradingStatusEl = document.getElementById('trading-status');
        const riskLevelEl = document.getElementById('risk-level');
        
        if (risk.trading_status) {
            if (risk.trading_status === 'ACTIVE') {
                tradingStatusEl.textContent = 'Active';
                tradingStatusEl.className = 'badge bg-success';
            } else {
                tradingStatusEl.textContent = 'Paused';
                tradingStatusEl.className = 'badge bg-warning';
            }
        }
        
        // Update risk progress bars
        if (risk.performance) {
            this.updateProgressBar('daily-pnl', Math.abs(risk.performance.daily_pnl), 1.50, 
                `$${risk.performance.daily_pnl.toFixed(2)} / $1.50 limit`);
        }
        
        if (risk.risk_metrics) {
            this.updateProgressBar('consecutive-losses', risk.risk_metrics.consecutive_losses, 5,
                `${risk.risk_metrics.consecutive_losses} / 5 limit`);
            
            this.updateProgressBar('drawdown', risk.risk_metrics.current_drawdown_pct, 40,
                `${risk.risk_metrics.current_drawdown_pct.toFixed(1)}% / 40% limit`);
            
            this.updateProgressBar('hourly-trades', risk.risk_metrics.hourly_trade_count, 15,
                `${risk.risk_metrics.hourly_trade_count} / 15 limit`);
        }
    }
    
    updateProgressBar(id, value, max, text) {
        const bar = document.getElementById(`${id}-bar`);
        const textEl = document.getElementById(`${id}-text`);
        
        const percentage = Math.min((value / max) * 100, 100);
        bar.style.width = `${percentage}%`;
        
        // Update color based on percentage
        bar.className = 'progress-bar';
        if (percentage > 80) {
            bar.classList.add('bg-danger');
        } else if (percentage > 60) {
            bar.classList.add('bg-warning');
        } else {
            bar.classList.add('bg-success');
        }
        
        textEl.textContent = text;
    }
    
    initCharts() {
        // Balance Chart
        const balanceCtx = document.getElementById('balanceChart').getContext('2d');
        this.balanceChart = new Chart(balanceCtx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Balance',
                    data: [],
                    borderColor: '#0dcaf0',
                    backgroundColor: 'rgba(13, 202, 240, 0.1)',
                    borderWidth: 2,
                    fill: true,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        labels: {
                            color: '#fff'
                        }
                    }
                },
                scales: {
                    x: {
                        ticks: { color: '#fff' },
                        grid: { color: 'rgba(255, 255, 255, 0.1)' }
                    },
                    y: {
                        ticks: { color: '#fff' },
                        grid: { color: 'rgba(255, 255, 255, 0.1)' }
                    }
                }
            }
        });
        
        // RSI Chart
        const rsiCtx = document.getElementById('rsiChart').getContext('2d');
        this.rsiChart = new Chart(rsiCtx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'RSI',
                    data: [],
                    borderColor: '#ffc107',
                    backgroundColor: 'rgba(255, 193, 7, 0.1)',
                    borderWidth: 2,
                    fill: false,
                    tension: 0.4
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        labels: {
                            color: '#fff'
                        }
                    }
                },
                scales: {
                    x: {
                        ticks: { color: '#fff' },
                        grid: { color: 'rgba(255, 255, 255, 0.1)' }
                    },
                    y: {
                        min: 0,
                        max: 100,
                        ticks: { color: '#fff' },
                        grid: { color: 'rgba(255, 255, 255, 0.1)' }
                    }
                },
                annotation: {
                    annotations: {
                        overbought: {
                            type: 'line',
                            yMin: 70,
                            yMax: 70,
                            borderColor: 'rgba(220, 53, 69, 0.8)',
                            borderWidth: 1,
                            borderDash: [5, 5]
                        },
                        oversold: {
                            type: 'line',
                            yMin: 30,
                            yMax: 30,
                            borderColor: 'rgba(25, 135, 84, 0.8)',
                            borderWidth: 1,
                            borderDash: [5, 5]
                        }
                    }
                }
            }
        });
    }
    
    updateBalanceChart(balance) {
        const now = new Date().toLocaleTimeString();
        
        this.balanceHistory.push({ time: now, value: balance });
        if (this.balanceHistory.length > this.maxDataPoints) {
            this.balanceHistory.shift();
        }
        
        this.balanceChart.data.labels = this.balanceHistory.map(d => d.time);
        this.balanceChart.data.datasets[0].data = this.balanceHistory.map(d => d.value);
        this.balanceChart.update('none');
    }
    
    updateRSIChart(rsi) {
        const now = new Date().toLocaleTimeString();
        
        this.rsiHistory.push({ time: now, value: rsi });
        if (this.rsiHistory.length > this.maxDataPoints) {
            this.rsiHistory.shift();
        }
        
        this.rsiChart.data.labels = this.rsiHistory.map(d => d.time);
        this.rsiChart.data.datasets[0].data = this.rsiHistory.map(d => d.value);
        this.rsiChart.update('none');
    }
}

// Bot control functions
async function controlBot(action) {
    try {
        const response = await fetch(`/api/control/${action}`, {
            method: 'POST'
        });
        
        const result = await response.json();
        
        if (result.status === 'success') {
            showNotification(`Success: ${result.message}`, 'success');
        } else {
            showNotification(`Error: ${result.message}`, 'error');
        }
        
    } catch (error) {
        console.error('Error controlling bot:', error);
        showNotification('Error communicating with bot', 'error');
    }
}

function showNotification(message, type = 'info') {
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `alert alert-${type === 'success' ? 'success' : type === 'error' ? 'danger' : 'info'} alert-dismissible fade show position-fixed`;
    notification.style.cssText = 'top: 20px; right: 20px; z-index: 9999; min-width: 300px;';
    notification.innerHTML = `
        ${message}
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    document.body.appendChild(notification);
    
    // Auto remove after 5 seconds
    setTimeout(() => {
        if (notification.parentNode) {
            notification.parentNode.removeChild(notification);
        }
    }, 5000);
}

// Initialize dashboard when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new BotDashboard();
});

// Handle page visibility change
document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
        console.log('Page hidden - reducing update frequency');
    } else {
        console.log('Page visible - resuming normal updates');
        if (window.dashboard) {
            window.dashboard.refreshData();
        }
    }
});