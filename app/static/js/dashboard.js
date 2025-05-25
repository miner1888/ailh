document.addEventListener('DOMContentLoaded', function() {
    const strategyCardsContainer = document.getElementById('strategy-cards-container');
    const loadingMessage = document.getElementById('loading-strategies');

    async function fetchDashboardData() {
        try {
            const response = await fetch('/ui/dashboard-data');
            if (!response.ok) throw new Error(`HTTP error! status: ${response.status}`);
            const data = await response.json();
            renderStrategyCards(data.strategies_data);
        } catch (error) {
            console.error('Error fetching dashboard data:', error);
            // Keep loading message if it exists, otherwise, set the container's content
            if (loadingMessage) {
                loadingMessage.textContent = 'Error loading strategies.';
            } else {
                strategyCardsContainer.innerHTML = '<p>Could not load strategy data. Please try again later.</p>';
            }
        }
    }

    function renderStrategyCards(strategiesData) {
        strategyCardsContainer.innerHTML = ''; // Clear loading message or old cards

        if (!strategiesData || strategiesData.length === 0) {
            strategyCardsContainer.innerHTML = '<p>No strategies configured yet. <a href="/add-strategy-page">Add a strategy!</a></p>';
            return;
        }

        strategiesData.forEach(item => {
            const config = item.strategy_config;
            const state = item.active_state;
            const currentPrice = item.current_market_price;

            const card = document.createElement('div');
            card.className = 'strategy-card';
            card.dataset.strategyId = config.id;

            let positionInfo = '<p>Position: Not active or no position</p>';
            let pnlInfo = '<p>P&L: -</p>';
            let statusText = state ? (state.is_running ? 'Running' : 'Paused/Stopped') : 'Not Started';
            let runPauseButtonText = state && state.is_running ? 'Pause' : 'Run';

            if (state && state.current_position_quantity > 0 && currentPrice != null) { // Check currentPrice for null/undefined
                const positionValue = state.current_position_quantity * currentPrice;
                const unrealizedPnl = (currentPrice - state.average_entry_price) * state.current_position_quantity;
                // Ensure total_invested_usdt is not zero to avoid division by zero
                const pnlPercentage = state.total_invested_usdt !== 0 ? (unrealizedPnl / state.total_invested_usdt) * 100 : 0;
                
                positionInfo = `
                    <p>Avg. Entry: ${state.average_entry_price != null ? state.average_entry_price.toFixed(4) : 'N/A'}</p>
                    <p>Quantity: ${state.current_position_quantity != null ? state.current_position_quantity.toFixed(4) : 'N/A'}</p>
                    <p>Value: ${positionValue.toFixed(2)} USDT</p>
                `;
                pnlInfo = `
                    <p>Realized P&L: ${state.realized_pnl_usdt != null ? state.realized_pnl_usdt.toFixed(2) : '0.00'} USDT</p>
                    <p>Unrealized P&L: <span class="${unrealizedPnl >= 0 ? 'profit' : 'loss'}">${unrealizedPnl.toFixed(2)} USDT (${pnlPercentage.toFixed(2)}%)</span></p>
                `;
            } else if (state) { // Has state but no position or price unavailable
                 positionInfo = '<p>Position: No current position</p>';
                 pnlInfo = `<p>Realized P&L: ${state.realized_pnl_usdt != null ? state.realized_pnl_usdt.toFixed(2) : '0.00'} USDT</p><p>Unrealized P&L: -</p>`;
            }


            card.innerHTML = `
                <h3>${config.strategy_name}</h3>
                <p>Pair: ${config.trading_pair} | API ID: ${config.api_id.substring(0,8)}...</p> 
                <p>Status: <strong id="status-${config.id}">${statusText}</strong> | Current Price: ${currentPrice != null ? currentPrice.toFixed(4) : 'N/A'}</p>
                ${positionInfo}
                ${pnlInfo}
                <div class="controls">
                    <button class="runPauseBtn" data-id="${config.id}">${runPauseButtonText}</button>
                    <button class="modifyBtn" data-id="${config.id}">Modify</button>
                    <button class="deleteStrategyBtn" data-id="${config.id}">Delete Strategy</button>
                </div>
            `;
            strategyCardsContainer.appendChild(card);
        });

        addEventListenersToControlButtons();
    }

    function addEventListenersToControlButtons() {
        document.querySelectorAll('.runPauseBtn').forEach(button => {
            button.addEventListener('click', async function() {
                const strategyId = this.dataset.id;
                const currentStatusElement = document.getElementById(`status-${strategyId}`);
                // Ensure currentStatusElement is found before accessing its textContent
                const currentStatusText = currentStatusElement ? currentStatusElement.textContent : (this.textContent === 'Pause' ? 'Running' : 'Paused/Stopped');
                const action = (currentStatusText === 'Running') ? 'pause' : 'start';
                
                try {
                    const response = await fetch(`/control/strategies/${strategyId}/${action}`, { method: 'POST' });
                    if (!response.ok) {
                         const error = await response.json();
                         throw new Error(error.detail || `Failed to ${action} strategy`);
                    }
                    // Refresh dashboard to reflect new state
                    fetchDashboardData(); 
                } catch (error) {
                    console.error(`Error ${action}ing strategy:`, error);
                    alert(`Could not ${action} strategy: ${error.message}`);
                }
            });
        });

        document.querySelectorAll('.modifyBtn').forEach(button => {
            button.addEventListener('click', function() {
                const strategyId = this.dataset.id;
                alert('Modify functionality for strategy ID ' + strategyId + ' will be implemented later.');
            });
        });

        document.querySelectorAll('.deleteStrategyBtn').forEach(button => {
            button.addEventListener('click', async function() {
                const strategyId = this.dataset.id;
                if (confirm('Are you sure you want to delete this strategy configuration? This may affect a running strategy.')) { // Updated confirm message slightly
                    try {
                        // Note: Proper implementation should stop the strategy task first if it's running.
                        // This is a simplified frontend action for now as per worker notes.
                        const response = await fetch(`/strategies/${strategyId}`, { method: 'DELETE' });
                        if (!response.ok) {
                            const error = await response.json();
                            throw new Error(error.detail || 'Failed to delete strategy configuration');
                        }
                        fetchDashboardData(); // Refresh dashboard
                    } catch (error) {
                        console.error('Error deleting strategy:', error);
                        alert('Could not delete strategy: ' + error.message);
                    }
                }
            });
        });
    }

    // Initial fetch and periodic refresh
    fetchDashboardData();
    setInterval(fetchDashboardData, 10000); // Refresh every 10 seconds
});
