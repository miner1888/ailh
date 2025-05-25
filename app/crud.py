from typing import List, Optional, Type
from uuid import UUID
from sqlalchemy.orm import Session

from app import models_db # SQLAlchemy models
from app.models import api_key as api_key_schemas # Pydantic schemas
from app.models import strategy as strategy_schemas # Pydantic schemas

# API Key CRUD
def create_api_key(db: Session, api_key_create: api_key_schemas.ApiKeyCreate) -> models_db.ApiKeyDB:
    db_api_key = models_db.ApiKeyDB(**api_key_create.dict())
    db.add(db_api_key)
    db.commit()
    db.refresh(db_api_key)
    return db_api_key

def get_api_key(db: Session, api_key_id: UUID) -> Optional[models_db.ApiKeyDB]:
    return db.query(models_db.ApiKeyDB).filter(models_db.ApiKeyDB.id == api_key_id).first()

def get_api_keys(db: Session, skip: int = 0, limit: int = 100) -> List[models_db.ApiKeyDB]:
    return db.query(models_db.ApiKeyDB).offset(skip).limit(limit).all()

def update_api_key(db: Session, api_key_id: UUID, api_key_update: api_key_schemas.ApiKeyUpdate) -> Optional[models_db.ApiKeyDB]:
    db_api_key = get_api_key(db, api_key_id)
    if db_api_key:
        update_data = api_key_update.dict(exclude_unset=True)
        for key, value in update_data.items():
            setattr(db_api_key, key, value)
        db.commit()
        db.refresh(db_api_key)
    return db_api_key

def delete_api_key(db: Session, api_key_id: UUID) -> bool:
    db_api_key = get_api_key(db, api_key_id)
    if db_api_key:
        # Before deleting an API key, consider strategies that might be using it.
        # Option 1: Disallow deletion if in use (check strategies_configs table).
        # Option 2: Set api_id in related strategies to NULL (if schema allows).
        # Option 3: Delete related strategies (cascade delete - define in SQLAlchemy model relationship).
        # For now, simple delete. Add cascading delete in model later if needed.
        
        # Example check (add this if you want to prevent deletion if used):
        # related_strategies = db.query(models_db.StrategyConfigDB).filter(models_db.StrategyConfigDB.api_id == api_key_id).count()
        # if related_strategies > 0:
        #     raise ValueError("API key is in use by strategies and cannot be deleted.") # This should be caught in API layer
        db.delete(db_api_key)
        db.commit()
        return True
    return False

# Strategy Config CRUD
def create_strategy_config(db: Session, strategy_create: strategy_schemas.StrategyCreate) -> models_db.StrategyConfigDB:
    # Ensure the api_id exists
    api_key = get_api_key(db, strategy_create.api_id)
    if not api_key:
        raise ValueError(f"API Key with id {strategy_create.api_id} not found.")
        
    db_strategy_config = models_db.StrategyConfigDB(**strategy_create.dict())
    db.add(db_strategy_config)
    db.commit()
    db.refresh(db_strategy_config)
    return db_strategy_config

def get_strategy_config(db: Session, strategy_id: UUID) -> Optional[models_db.StrategyConfigDB]:
    return db.query(models_db.StrategyConfigDB).filter(models_db.StrategyConfigDB.id == strategy_id).first()

def get_strategy_configs(db: Session, skip: int = 0, limit: int = 100) -> List[models_db.StrategyConfigDB]:
    return db.query(models_db.StrategyConfigDB).offset(skip).limit(limit).all()

def update_strategy_config(db: Session, strategy_id: UUID, strategy_update: strategy_schemas.StrategyUpdate) -> Optional[models_db.StrategyConfigDB]:
    db_strategy_config = get_strategy_config(db, strategy_id)
    if db_strategy_config:
        update_data = strategy_update.dict(exclude_unset=True)
        if "api_id" in update_data and update_data["api_id"] is not None: # Validate new api_id if provided and not None
            api_key = get_api_key(db, update_data["api_id"])
            if not api_key:
                raise ValueError(f"API Key with id {update_data['api_id']} not found.")
        
        for key, value in update_data.items():
            setattr(db_strategy_config, key, value)
        db.commit()
        db.refresh(db_strategy_config)
    return db_strategy_config

def delete_strategy_config(db: Session, strategy_id: UUID) -> bool:
    db_strategy_config = get_strategy_config(db, strategy_id)
    if db_strategy_config:
        # Consider if strategy is active and stop it first
        # from app.core.strategy_runner import active_strategies_store # Avoid circular import if possible
        # active_strategy_state = active_strategies_store.get(strategy_id)
        # if active_strategy_state and active_strategy_state.is_running:
        #    raise ValueError("Strategy is active. Stop it before deleting configuration.")
        db.delete(db_strategy_config)
        db.commit()
        return True
    return False
