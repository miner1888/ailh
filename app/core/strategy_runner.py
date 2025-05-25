from uuid import UUID
import asyncio 
from typing import Dict, Optional, List
from app.models.strategy import StrategyConfig, CoverReferencePrice 
from app.models.active_strategy import ActiveStrategyState, IndividualPosition
# Import db_strategies is removed as strategy_config is passed to strategy_loop directly
# from app.api.strategy_management import db_strategies 
from app.core.mock_price_feed import get_mock_price 
from app.core.trading_logic import (
    should_initial_buy, 
    should_sell_for_profit, 
    should_buy_for_cover, 
    ValidationState
)

active_strategies_store: Dict[UUID, ActiveStrategyState] = {}
running_strategy_tasks: Dict[UUID, asyncio.Task] = {} 

async def strategy_loop(strategy_id: UUID, initial_strategy_config: StrategyConfig, polling_interval: int = 5):
    """
    Main loop for a single running strategy.
    It periodically fetches the current market price, processes the strategy logic,
    and manages the strategy's active state.
    `initial_strategy_config` is passed to avoid repeated database lookups for static configuration
    and to ensure the loop runs with the configuration that was active at the start of this run.
    """
    print(f"Strategy loop started for {strategy_id} with config {initial_strategy_config.strategy_name}")
    active_state_in_loop = active_strategies_store.get(strategy_id) # Get initial state for the loop

    try:
        while True:
            # Use the initial strategy_config for the duration of this loop run.
            # A more complex system might handle dynamic config updates by fetching config from DB here.
            strategy_config = initial_strategy_config 

            # Re-fetch active_state in each iteration to ensure it has the latest updates
            # especially if external actions (like manual stop) could modify it.
            active_state_in_loop = active_strategies_store.get(strategy_id)

            if not active_state_in_loop or not strategy_config or not active_state_in_loop.is_running:
                stop_reason = []
                if not active_state_in_loop: stop_reason.append("state missing")
                if not strategy_config: stop_reason.append("config missing") # Should not happen if passed correctly
                if active_state_in_loop and not active_state_in_loop.is_running: stop_reason.append("is_running flag is false")
                print(f"Strategy {strategy_id} stopping loop. Reason(s): {', '.join(stop_reason)}.")
                
                if active_state_in_loop: 
                    active_state_in_loop.is_running = False # Ensure it's marked as not running
                break # Exit loop

            try:
                # Fetch the current market price for the strategy's trading pair.
                current_market_price = await get_mock_price(active_state_in_loop.trading_pair)
            except Exception as price_error: 
                # Handle errors during price fetching (e.g., network issues, mock feed error).
                active_state_in_loop.last_error = f"Price fetch error: {str(price_error)}"
                print(f"Strategy {strategy_id}: Could not fetch price for {active_state_in_loop.trading_pair}. Error: {price_error}")
                # In a production system, log this to a persistent logging service.
                await asyncio.sleep(polling_interval) # Wait before retrying the loop.
                continue # Skip this processing iteration and try again.

            # Set the initial market price reference if it's the first run for a position and not yet set.
            if active_state_in_loop.current_market_price_for_reference is None and active_state_in_loop.current_position_quantity == 0:
                active_state_in_loop.current_market_price_for_reference = current_market_price
            
            # Process the core trading logic for the current state and market price.
            updated_state = await process_strategy(strategy_config, active_state_in_loop, current_market_price)
            active_strategies_store[strategy_id] = updated_state # Store the updated state.

        except asyncio.CancelledError:
            # Handle task cancellation, typically initiated by a stop/pause command.
            print(f"Strategy {strategy_id} loop explicitly cancelled.")
            if active_state_in_loop: 
                active_state_in_loop.is_running = False 
                active_state_in_loop.last_error = "Strategy loop cancelled."
            break 
        except Exception as e: 
            # Catch any other unexpected errors within the loop's main try block.
            print(f"ERROR in strategy loop for {strategy_id}: {e}")
            if active_state_in_loop: 
                active_state_in_loop.last_error = f"Critical loop error: {str(e)}"
                active_state_in_loop.is_running = False # Stop strategy on critical error.
            break 
        
        # Wait for the defined polling interval before the next iteration.
        await asyncio.sleep(polling_interval) 
    finally: 
        # This block executes when the loop terminates, either normally, by cancellation, or due to an error.
        print(f"Strategy {strategy_id} loop finished or exited. Cleaning up task.")
        # Ensure the strategy state is marked as not running.
        final_state_check = active_strategies_store.get(strategy_id)
        if final_state_check: 
            final_state_check.is_running = False
        # Remove the task from the set of running tasks.
        running_strategy_tasks.pop(strategy_id, None) 


async def process_strategy(
    strategy_config: StrategyConfig, 
    active_state: ActiveStrategyState, 
    current_market_price: float
) -> ActiveStrategyState: 
    """
    Processes the core trading logic for a single strategy based on its current state and the latest market price.
    This function determines if any buy, sell, or cover actions should be taken according to the strategy's configuration.
    It updates the `active_state` object with new position details, P&L, and validation states.

    Note on Real-World Order Handling (Conceptual):
    In a live trading system, actions like "buy" or "sell" would involve:
    1.  Placing an order with an exchange via an API.
    2.  Handling potential errors from the exchange (e.g., insufficient funds, invalid parameters, network issues).
    3.  If `enable_order_timeout` is true for the strategy:
        - Store the pending order details (ID, type, timestamp, timeout_at) in `active_state` (e.g. `active_state.pending_order`).
        - Set `active_state.next_action_timestamp` for the timeout check.
        - The function might return, and subsequent calls to `process_strategy` or a dedicated order-checking function
          would monitor the status of this pending order (filled, partially filled, expired, etc.).
    4.  If order execution is immediate (e.g., market order simulation) or timeout is disabled:
        - Update `active_state` with actual fill price and quantity from the exchange response.
    For this simulation, we assume immediate fills at `current_market_price`.
    """

    if not active_state.is_running: # If strategy is paused or stopped, do not process.
        return active_state

    # Update Unrealized P&L: Calculated each tick based on current market price vs. average entry price.
    if active_state.current_position_quantity > 0 and active_state.average_entry_price > 0:
        active_state.unrealized_pnl_usdt = (current_market_price - active_state.average_entry_price) * active_state.current_position_quantity
    else:
        active_state.unrealized_pnl_usdt = 0.0

    # --- Initial Buy Logic ---
    # Handles the first buy order if no position is currently held.
    if active_state.current_position_quantity == 0: 
        # `current_market_price_for_reference` is the baseline for initial buy trigger (e.g., price must fall X% from this).
        reference_price = active_state.current_market_price_for_reference if active_state.current_market_price_for_reference is not None else current_market_price
        
        new_buy_state, new_buy_price_at_cond1, buy_signal = await should_initial_buy( 
            strategy_config=strategy_config,
            current_price=current_market_price,
            reference_price=reference_price,
            current_validation_state=active_state.buy_validation_state,
            price_at_cond1_met=active_state.buy_price_at_cond1_met
        )
        active_state.buy_validation_state = new_buy_state
        active_state.buy_price_at_cond1_met = new_buy_price_at_cond1

        if buy_signal:
            # --- Conceptual Real Order Placement & Timeout Handling (Initial Buy) ---
            # (See general note at the beginning of this function regarding order handling)
            # --- End Conceptual ---

            # Update state assuming immediate fill at current_market_price for simulation.
            active_state.initial_entry_price = current_market_price
            active_state.last_buy_price = current_market_price
            active_state.average_entry_price = current_market_price
            
            if current_market_price > 0:
                active_state.current_position_quantity = strategy_config.initial_order_amount_usdt / current_market_price
            else: 
                active_state.current_position_quantity = 0
                error_message = "Initial buy failed: Market price is zero or invalid."
                active_state.last_error = error_message
                print(f"Strategy {active_state.strategy_id}: {error_message}")
                return active_state # Stop further processing for this tick if buy fails critically
            
            active_state.last_error = None # Clear last error on successful action

            active_state.total_invested_usdt = strategy_config.initial_order_amount_usdt
            
            if strategy_config.cover_orders_participate_in_profit_taking:
                # If cover orders are sold individually, track this initial buy as a distinct position.
                active_state.individual_positions = [
                    IndividualPosition( 
                        entry_price=current_market_price,
                        quantity=active_state.current_position_quantity
                    )
                ]
            else:
                active_state.individual_positions = [] 

            # Reset validation states for the next cycle of operations.
            active_state.buy_validation_state = ValidationState.IDLE 
            active_state.buy_price_at_cond1_met = None
            active_state.sell_validation_state = ValidationState.IDLE
            active_state.sell_price_at_cond1_met = None
            active_state.cover_validation_state = ValidationState.IDLE
            active_state.cover_price_at_cond1_met = None
            active_state.cover_orders_count = 0 # Reset cover count for the new position.

    # --- Sell Logic (Profit Taking) ---
    # Handles selling the position for profit if a position is currently held.
    elif active_state.current_position_quantity > 0: 
        if not strategy_config.cover_orders_participate_in_profit_taking:
            # Scenario 1: Aggregated sell. The entire position (initial + all covers) is sold together.
            # Sell decisions are based on the average_entry_price of the whole position.
            new_sell_state, new_sell_price_at_cond1, sell_signal = await should_sell_for_profit( 
                strategy_config=strategy_config,
                current_price=current_market_price,
                entry_price=active_state.average_entry_price, 
                current_validation_state=active_state.sell_validation_state,
                price_at_cond1_met=active_state.sell_price_at_cond1_met
            )
            active_state.sell_validation_state = new_sell_state
            active_state.sell_price_at_cond1_met = new_sell_price_at_cond1

            if sell_signal:
                # --- Conceptual Real Order Placement & Timeout Handling (Aggregated Sell) ---
                # (See general note at the beginning of this function regarding order handling)
                # --- End Conceptual ---
                active_state.last_error = None 

                profit = (current_market_price - active_state.average_entry_price) * active_state.current_position_quantity
                active_state.realized_pnl_usdt += profit
                
                # Reset position details after successful sell.
                active_state.current_position_quantity = 0.0
                active_state.average_entry_price = 0.0
                active_state.total_invested_usdt = 0.0
                active_state.cover_orders_count = 0
                active_state.initial_entry_price = None
                active_state.last_buy_price = None
                active_state.individual_positions = [] 
                active_state.unrealized_pnl_usdt = 0.0

                active_state.sell_validation_state = ValidationState.IDLE
                active_state.sell_price_at_cond1_met = None
                # Reset buy/cover validation states for the next cycle if the strategy is cyclic.
                active_state.buy_validation_state = ValidationState.IDLE 
                active_state.buy_price_at_cond1_met = None
                active_state.cover_validation_state = ValidationState.IDLE
                active_state.cover_price_at_cond1_met = None

                if not strategy_config.cyclic_execution:
                    active_state.is_running = False # Stop strategy if not cyclic.
        
        else: 
            # Scenario 2: Individual position selling. Each buy (initial or cover) is tracked
            # and sold separately based on its own entry price and the strategy's sell conditions.
            positions_to_remove: List[IndividualPosition] = []
            temp_individual_positions = active_state.individual_positions[:] 

            for i, pos in enumerate(temp_individual_positions):
                original_pos_index = -1
                for idx_orig, p_orig in enumerate(active_state.individual_positions):
                    if p_orig.entry_price == pos.entry_price and p_orig.quantity == pos.quantity: 
                        original_pos_index = idx_orig
                        break
                
                if original_pos_index == -1: continue 

                new_pos_sell_state, new_pos_sell_price_at_cond1, sell_signal = await should_sell_for_profit( 
                    strategy_config=strategy_config, 
                    current_price=current_market_price,
                    entry_price=active_state.individual_positions[original_pos_index].entry_price,
                    current_validation_state=active_state.individual_positions[original_pos_index].sell_validation_state,
                    price_at_cond1_met=active_state.individual_positions[original_pos_index].sell_price_at_cond1_met
                )
                active_state.individual_positions[original_pos_index].sell_validation_state = new_pos_sell_state
                active_state.individual_positions[original_pos_index].sell_price_at_cond1_met = new_pos_sell_price_at_cond1

                if sell_signal:
                    # --- Conceptual Real Order Placement & Timeout Handling (Individual Sell) ---
                    # (See general note at the beginning of this function regarding order handling)
                    # --- End Conceptual ---
                    active_state.last_error = None 

                    profit = (current_market_price - active_state.individual_positions[original_pos_index].entry_price) * active_state.individual_positions[original_pos_index].quantity
                    active_state.realized_pnl_usdt += profit
                    
                    active_state.current_position_quantity -= active_state.individual_positions[original_pos_index].quantity
                    active_state.total_invested_usdt -= (active_state.individual_positions[original_pos_index].entry_price * active_state.individual_positions[original_pos_index].quantity)
                    positions_to_remove.append(active_state.individual_positions[original_pos_index]) 
            
            if positions_to_remove:
                active_state.individual_positions = [p for p in active_state.individual_positions if p not in positions_to_remove]

                if active_state.current_position_quantity > 0.0000001: 
                    active_state.average_entry_price = active_state.total_invested_usdt / active_state.current_position_quantity
                else: 
                    active_state.current_position_quantity = 0.0
                    active_state.average_entry_price = 0.0
                    active_state.total_invested_usdt = 0.0
                    active_state.unrealized_pnl_usdt = 0.0
                    active_state.initial_entry_price = None 
                    active_state.last_buy_price = None
                    active_state.cover_orders_count = 0 
                    
                    active_state.buy_validation_state = ValidationState.IDLE
                    active_state.buy_price_at_cond1_met = None
                    active_state.cover_validation_state = ValidationState.IDLE
                    active_state.cover_price_at_cond1_met = None

                    if not strategy_config.cyclic_execution:
                        active_state.is_running = False
            
            if active_state.current_position_quantity == 0 and not strategy_config.cyclic_execution:
                 active_state.is_running = False


    # --- Cover Buy Logic ---
    # Handles placing cover buy orders (DCA - Dollar Cost Averaging) if conditions are met.
    if active_state.current_position_quantity > 0 and \
       active_state.cover_orders_count < strategy_config.max_cover_count: # Check if max cover orders not reached.
        
        ref_price_for_cover: Optional[float] = None
        # Determine the reference price for cover buy based on strategy configuration.
        if strategy_config.cover_reference_price == CoverReferencePrice.AVERAGE_HOLDING:
            ref_price_for_cover = active_state.average_entry_price
        elif strategy_config.cover_reference_price == CoverReferencePrice.LAST_BUY_PRICE:
            ref_price_for_cover = active_state.last_buy_price
        elif strategy_config.cover_reference_price == CoverReferencePrice.INITIAL_PRICE:
            ref_price_for_cover = active_state.initial_entry_price
        
        if ref_price_for_cover is not None and ref_price_for_cover > 0: # Ensure reference price is valid.
            new_cover_state, new_cover_price_at_cond1, cover_signal = await should_buy_for_cover( 
                strategy_config=strategy_config,
                current_price=current_market_price,
                cover_reference_price_value=ref_price_for_cover,
                current_validation_state=active_state.cover_validation_state,
                price_at_cond1_met=active_state.cover_price_at_cond1_met
            )
            active_state.cover_validation_state = new_cover_state
            active_state.cover_price_at_cond1_met = new_cover_price_at_cond1

            if cover_signal:
                # --- Conceptual Real Order Placement & Timeout Handling (Cover Buy) ---
                # (See general note at the beginning of this function regarding order handling)
                # --- End Conceptual ---

                # Calculate cover order amount. It can increase with each cover based on the multiplier.
                cover_amount_usdt = strategy_config.initial_order_amount_usdt * (strategy_config.cover_multiplier ** active_state.cover_orders_count)

                if current_market_price > 0:
                    cover_quantity = cover_amount_usdt / current_market_price
                else: 
                    cover_quantity = 0
                    error_message = "Cover buy failed: Market price is zero or invalid."
                    active_state.last_error = error_message
                    print(f"Strategy {active_state.strategy_id}: {error_message}")
                    return active_state # Stop further processing for this tick

                active_state.last_error = None # Clear last error on successful action

                if cover_quantity > 0: 
                    new_total_invested = active_state.total_invested_usdt + cover_amount_usdt
                    new_total_quantity = active_state.current_position_quantity + cover_quantity
                    
                    active_state.average_entry_price = new_total_invested / new_total_quantity if new_total_quantity > 0 else 0
                    active_state.last_buy_price = current_market_price
                    active_state.current_position_quantity = new_total_quantity
                    active_state.total_invested_usdt = new_total_invested
                    active_state.cover_orders_count += 1
                    
                    if strategy_config.cover_orders_participate_in_profit_taking:
                        active_state.individual_positions.append(
                            IndividualPosition(
                                entry_price=current_market_price,
                                quantity=cover_quantity
                            )
                        )
                    
                    active_state.cover_validation_state = ValidationState.IDLE
                    active_state.cover_price_at_cond1_met = None
                    # After a cover buy, the conditions for selling the aggregated position might change.
                    # Reset the main sell validation state if not selling positions individually.
                    if not strategy_config.cover_orders_participate_in_profit_taking:
                        active_state.sell_validation_state = ValidationState.IDLE
                        active_state.sell_price_at_cond1_met = None
    return active_state
