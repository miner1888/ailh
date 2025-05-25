import uuid
import random # Retain for test_api_connectivity
from fastapi import APIRouter, HTTPException, status, Depends
from typing import List
from sqlalchemy.orm import Session

from app import crud
from app.models import api_key as api_key_schemas # Renamed for clarity
from app.database import get_db
from app import models_db # Added for explicit DB model access if needed, e.g. for delete check

router = APIRouter()

# This mock function remains as it doesn't interact with the DB directly for its core logic
async def test_api_connectivity(api_key_data: api_key_schemas.ApiKeyCreate) -> str:
    """
    Simulates testing API connectivity.
    """
    # Simulate based on some dummy check
    if "error" in api_key_data.api_key.lower() or "bad" in api_key_data.secret_key.lower():
        return random.choice(["error: invalid credentials", "error: network issue"])
    return "connected"

@router.post(
    "/", 
    response_model=api_key_schemas.ApiKey, 
    status_code=status.HTTP_201_CREATED,
    summary="Create a new API Key",
    description="Adds a new API key to the system. The `connection_status` is tested upon creation."
)
async def create_new_api_key(api_key_in: api_key_schemas.ApiKeyCreate, db: Session = Depends(get_db)):
    """
    Create a new API key.

    - **alias**: A user-defined alias for the key (e.g., "My Binance Paper Account").
    - **api_key**: The actual API key string provided by the exchange.
    - **secret_key**: The secret associated with the API key.
    - **mode**: Trading mode, either 'paper' or 'live'.
    """
    db_api_key = crud.create_api_key(db=db, api_key_create=api_key_in)
    response_data = api_key_schemas.ApiKey.from_orm(db_api_key)
    response_data.connection_status = await test_api_connectivity(api_key_in)
    return response_data

@router.get("/", response_model=List[api_key_schemas.ApiKey])
async def read_api_keys(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    db_api_keys = crud.get_api_keys(db, skip=skip, limit=limit)
    response_list = []
    for db_key in db_api_keys:
        pydantic_key = api_key_schemas.ApiKey.from_orm(db_key)
        # For GET multiple, we'll set a default status. Frontend can test individually if needed.
        # Or, if performance allows, test each one:
        temp_api_key_create = api_key_schemas.ApiKeyCreate(
             alias=db_key.alias, api_key=db_key.api_key, secret_key="dummy", mode=db_key.mode
        )
        pydantic_key.connection_status = await test_api_connectivity(temp_api_key_create)
        response_list.append(pydantic_key)
    return response_list

@router.get(
    "/{api_id}", 
    response_model=api_key_schemas.ApiKey,
    summary="Get a specific API Key by ID",
    description="Retrieves details for a single API key, including its dynamic `connection_status`."
)
async def read_api_key(api_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Retrieve a specific API key by its ID.
    The `connection_status` is tested dynamically upon retrieval.
    """
    db_api_key = crud.get_api_key(db, api_key_id=api_id)
    if db_api_key is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API Key not found")
    
    response_data = api_key_schemas.ApiKey.from_orm(db_api_key)
    temp_api_key_create = api_key_schemas.ApiKeyCreate(
        alias=db_api_key.alias, api_key=db_api_key.api_key, secret_key="dummy", mode=db_api_key.mode
    )
    response_data.connection_status = await test_api_connectivity(temp_api_key_create)
    return response_data

@router.put(
    "/{api_id}", 
    response_model=api_key_schemas.ApiKey,
    summary="Update an existing API Key",
    description="Updates specified fields of an existing API key. If `api_key`, `secret_key`, or `mode` are changed, `connection_status` is re-tested."
)
async def update_existing_api_key(api_id: uuid.UUID, api_key_update: api_key_schemas.ApiKeyUpdate, db: Session = Depends(get_db)):
    """
    Update an existing API key.
    Only provided fields will be updated.
    If `secret_key` is provided, it will be updated.
    The `connection_status` will be re-tested if relevant fields change.
    """
    db_api_key_exists = crud.get_api_key(db, api_key_id=api_id)
    if db_api_key_exists is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API Key not found")

    updated_db_key = crud.update_api_key(db=db, api_key_id=api_id, api_key_update=api_key_update)
    # crud.update_api_key should not return None if the key exists, but for safety:
    if updated_db_key is None: 
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API Key not found after update attempt")

    response_data = api_key_schemas.ApiKey.from_orm(updated_db_key)
    
    # Prepare data for test_api_connectivity using updated or existing values
    test_data_payload = api_key_schemas.ApiKeyCreate(
        alias=updated_db_key.alias,
        api_key=updated_db_key.api_key,
        # Use the new secret if provided in the update, otherwise a dummy value as it's not returned from DB
        secret_key=api_key_update.secret_key if api_key_update.secret_key else "dummy",
        mode=updated_db_key.mode
    )
    response_data.connection_status = await test_api_connectivity(test_data_payload)
    return response_data

@router.delete(
    "/{api_id}", 
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete an API Key",
    description="Deletes an API key if it is not currently associated with any strategy configurations."
)
async def delete_existing_api_key(api_id: uuid.UUID, db: Session = Depends(get_db)):
    """
    Delete an API key.
    The API key cannot be deleted if it is currently in use by any strategy configurations.
    Returns HTTP 204 No Content on successful deletion.
    """
    # Check if the API key is used by any strategy config
    related_strategies_count = db.query(models_db.StrategyConfigDB).filter(models_db.StrategyConfigDB.api_id == api_id).count()
    if related_strategies_count > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="API key is in use by one or more strategies and cannot be deleted. Please delete or update the strategies first."
        )
    
    try:
        success = crud.delete_api_key(db, api_key_id=api_id)
        if not success: # Should be caught by crud if not found, but for safety
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="API Key not found")
    except ValueError as e: # Catch specific error from CRUD (e.g., if key is in use by a check within crud)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    # No content response for 204, so no explicit return value here.
    # If you wanted to return a message, you'd change status_code and add response_model.
    # For 204, FastAPI handles sending no content.
