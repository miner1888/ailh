import uuid
from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
from sqlalchemy.orm import Session

from app import crud
from app.models import strategy as strategy_schemas # Pydantic schemas
from app.database import get_db
# No longer need to import db_api_keys from api_management for validation,
# as crud functions will handle existence checks using the db session.

router = APIRouter()

# db_strategies: List[StrategyConfig] = [] # Removed in-memory list

@router.post("/", response_model=strategy_schemas.StrategyConfig, status_code=status.HTTP_201_CREATED)
async def create_new_strategy(
    strategy_data: strategy_schemas.StrategyCreate, 
    db: Session = Depends(get_db)
):
    """
    Create a new strategy configuration. 
    Validates that the provided `api_id` exists and is linked to a connected API key before creating the strategy.
    """
    try:
        # The crud function already checks if api_id exists.
        # Additional check for API key connection status can be added here if desired,
        # but currently, strategy creation doesn't depend on live connection status.
        db_strategy = crud.create_strategy_config(db=db, strategy_create=strategy_data)
        return db_strategy # Relies on orm_mode = True in Pydantic model
    except ValueError as e: # Catch ValueError from crud if API key not found
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/", response_model=List[strategy_schemas.StrategyConfig])
async def read_strategies(
    skip: int = 0, 
    limit: int = 100, 
    db: Session = Depends(get_db)
):
    """
    Retrieve a list of all strategy configurations. Supports pagination via `skip` and `limit` parameters.
    """
    db_strategies_list = crud.get_strategy_configs(db, skip=skip, limit=limit)
    return db_strategies_list

@router.get(
    "/{strategy_id}", 
    response_model=strategy_schemas.StrategyConfig,
    summary="Get a specific Strategy Configuration by ID",
    description="Retrieves the complete configuration details for a single trading strategy."
)
async def read_strategy(
    strategy_id: uuid.UUID, 
    db: Session = Depends(get_db)
):
    """
    Retrieve a specific strategy configuration by its ID.
    Returns HTTP 404 if the strategy configuration is not found.
    """
    db_strategy = crud.get_strategy_config(db, strategy_id=strategy_id)
    if db_strategy is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Strategy not found")
    return db_strategy

@router.put("/{strategy_id}", response_model=strategy_schemas.StrategyConfig)
async def update_existing_strategy(
    strategy_id: uuid.UUID, 
    strategy_update: strategy_schemas.StrategyUpdate, 
    db: Session = Depends(get_db)
):
    """
    Update an existing strategy configuration.
    Only provided fields will be updated. If `api_id` is changed, its existence is validated.
    Returns HTTP 404 if the strategy configuration is not found.
    """
    # First, check if the strategy exists
    db_strategy_exists = crud.get_strategy_config(db, strategy_id=strategy_id)
    if db_strategy_exists is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Strategy not found")

    try:
        updated_strategy = crud.update_strategy_config(db=db, strategy_id=strategy_id, strategy_update=strategy_update)
        # crud.update_strategy_config should not return None if the initial check passed, but for safety:
        if updated_strategy is None:
             raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Strategy not found after update attempt")
        return updated_strategy
    except ValueError as e: # Catch ValueError from crud if API key for update not found
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.delete("/{strategy_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_existing_strategy(strategy_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Delete a strategy configuration.
    """
    # Note: crud.delete_strategy_config has a comment about checking active state.
    # This check should ideally happen here in the API layer before calling crud.
    # For now, following the simpler model of direct deletion via crud.
    # from app.core.strategy_runner import active_strategies_store, running_strategy_tasks
    # if strategy_id in active_strategies_store and active_strategies_store[strategy_id].is_running:
    #     raise HTTPException(status_code=400, detail="Strategy is active. Stop it before deleting.")
    # if strategy_id in running_strategy_tasks and not running_strategy_tasks[strategy_id].done():
    #      raise HTTPException(status_code=400, detail="Strategy task is running. Stop it before deleting.")


    success = crud.delete_strategy_config(db, strategy_id=strategy_id)
    if not success:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Strategy not found")
    return # No content for 204
