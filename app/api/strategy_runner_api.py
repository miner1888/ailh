from uuid import UUID
import asyncio
from fastapi import APIRouter, HTTPException, status, Depends
from typing import Dict, Optional
from sqlalchemy.orm import Session # Added Session

# Removed direct db imports (db_strategies, db_api_keys)
# from app.api.strategy_management import db_strategies, StrategyConfig # Removed
# from app.api.api_management import db_api_keys, ApiKey # Removed

from app import crud # Added crud
from app.database import get_db # Added get_db
from app.models import api_key as api_key_schemas # For ApiKey Pydantic model if needed for status check
from app.models import strategy as strategy_schemas # For StrategyConfig Pydantic model

from app.core.strategy_runner import ( 
    active_strategies_store, 
    strategy_loop, 
    running_strategy_tasks
)
from app.models.active_strategy import ActiveStrategyState
from app.core.mock_price_feed import get_mock_price 
# Re-import test_api_connectivity if it's defined in api_management and needed here
# Or define a similar local utility if direct api_key details are available
from app.api.api_management import test_api_connectivity # Assuming it's safe to import

router = APIRouter()


@router.post(
    "/strategies/{strategy_id}/start", 
    response_model=ActiveStrategyState, 
    status_code=status.HTTP_200_OK,
    summary="Start a Trading Strategy",
    description="Starts (or restarts if already exists but paused) the specified trading strategy. It fetches the strategy configuration, validates the associated API key, and initiates an asynchronous trading loop."
)
async def start_strategy(strategy_id: UUID, db: Session = Depends(get_db)):
    """
    Start a trading strategy by its ID.

    - If the strategy is already running, a 400 error is returned.
    - If the strategy was previously paused, its state is resumed.
    - If starting fresh, a new active state is created.
    - The associated API key must be valid and connected.
    """
    # 1. Fetch StrategyConfig using CRUD
    db_strategy_config = crud.get_strategy_config(db, strategy_id=strategy_id)
    if not db_strategy_config:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Strategy configuration not found.")
    # Convert to Pydantic model for use in the rest of the function, if needed, or pass DB model
    # strategy_loop expects Pydantic StrategyConfig
    strategy_config_pydantic = strategy_schemas.StrategyConfig.from_orm(db_strategy_config)


    # 2. Validate API Key using CRUD
    db_api_key = crud.get_api_key(db, api_key_id=db_strategy_config.api_id)
    if not db_api_key:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"API Key with ID {db_strategy_config.api_id} not found for this strategy.")
    
    # Convert db_api_key to pydantic schema to pass to test_api_connectivity
    temp_api_key_create_schema = api_key_schemas.ApiKeyCreate(
        alias=db_api_key.alias,
        api_key=db_api_key.api_key,
        secret_key="dummy_secret_for_test", # Secret not used directly by test_api_connectivity logic but required by model
        mode=db_api_key.mode 
    )
    api_connection_status = await test_api_connectivity(temp_api_key_create_schema)

    if api_connection_status != "connected":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"API Key '{db_api_key.alias}' is not connected. Current status: {api_connection_status}")

    # 3. Check if already running (via active_state)
    active_state = active_strategies_store.get(strategy_id)
    if active_state and active_state.is_running:
        if strategy_id in running_strategy_tasks and not running_strategy_tasks[strategy_id].done():
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Strategy is already running (task exists).")

    # 4. Cancel existing task if any
    if strategy_id in running_strategy_tasks:
        existing_task = running_strategy_tasks[strategy_id]
        if not existing_task.done():
            existing_task.cancel()
            try:
                await existing_task 
            except asyncio.CancelledError:
                print(f"Existing task for strategy {strategy_id} was cancelled before starting a new one.")
        running_strategy_tasks.pop(strategy_id, None)


    # 5. Create or update ActiveStrategyState
    initial_market_price = await get_mock_price(strategy_config_pydantic.trading_pair) 

    if active_state: 
        active_state.is_running = True
        active_state.last_error = None 
        if active_state.current_position_quantity == 0: 
             active_state.current_market_price_for_reference = initial_market_price
    else: 
        active_state = ActiveStrategyState(
            strategy_id=strategy_id,
            api_id=strategy_config_pydantic.api_id, # Use pydantic model here
            trading_pair=strategy_config_pydantic.trading_pair, # Use pydantic model here
            is_running=True,
            current_market_price_for_reference=initial_market_price
        )
    active_strategies_store[strategy_id] = active_state
    
    # 6. Create and store asyncio task
    # Pass the Pydantic version of strategy_config to the loop
    task = asyncio.create_task(strategy_loop(strategy_id, initial_strategy_config=strategy_config_pydantic))
    running_strategy_tasks[strategy_id] = task
    
    return active_state

@router.post(
    "/strategies/{strategy_id}/stop", 
    response_model=ActiveStrategyState,
    summary="Stop a Trading Strategy",
    description="Stops a currently running trading strategy. The strategy's asynchronous task is cancelled, and its state is marked as not running."
)
async def stop_strategy(strategy_id: UUID): 
    """
    Stop a trading strategy by its ID.

    - If the strategy is not found in the active store, a 404 error is returned.
    - Sets `is_running` to `False` in the active state.
    - Cancels the corresponding asyncio task.
    """
    active_state = active_strategies_store.get(strategy_id)
    if not active_state:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Active strategy not found.")
    
    active_state.is_running = False 
    
    task = running_strategy_tasks.get(strategy_id)
    if task and not task.done():
        task.cancel()
        try:
            await task 
        except asyncio.CancelledError:
            print(f"Strategy task {strategy_id} cancelled successfully via stop.")
    running_strategy_tasks.pop(strategy_id, None)
            
    return active_state

@router.post(
    "/strategies/{strategy_id}/pause", 
    response_model=ActiveStrategyState,
    summary="Pause a Trading Strategy",
    description="Pauses a currently running trading strategy. Similar to stopping, it cancels the task and marks the state as not running. Future enhancements might differentiate pause from stop more significantly."
)
async def pause_strategy(strategy_id: UUID):
    """
    Pause a trading strategy by its ID.
    Currently, this behaves identically to stopping the strategy.
    """
    active_state = active_strategies_store.get(strategy_id)
    if not active_state:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Active strategy not found.")
    
    active_state.is_running = False 
    
    task = running_strategy_tasks.get(strategy_id)
    if task and not task.done():
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            print(f"Strategy task {strategy_id} cancelled successfully via pause.")
    running_strategy_tasks.pop(strategy_id, None)
    return active_state

@router.get(
    "/strategies/{strategy_id}/state", 
    response_model=ActiveStrategyState,
    summary="Get Active Strategy State",
    description="Retrieves the current in-memory state of an active (or previously active but now paused/stopped) trading strategy."
)
async def get_strategy_state(strategy_id: UUID):
    """
    Get the current state of an active strategy by its ID.
    This reflects the in-memory operational state, not the persisted configuration.
    """
    active_state = active_strategies_store.get(strategy_id)
    if not active_state:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Active strategy state not found.")
    return active_state
