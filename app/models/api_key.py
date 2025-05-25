import uuid
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

class ApiMode(str, Enum):
    """Trading mode for an API key."""
    PAPER = "paper"
    LIVE = "live"

class ApiKeyBase(BaseModel):
    """Base Pydantic model for API key data."""
    alias: str = Field(..., description="A user-friendly name for the API key (e.g., 'My Binance Paper Account').")
    api_key: str = Field(..., description="The API key string provided by the exchange.")
    mode: ApiMode = Field(ApiMode.PAPER, description="The trading mode: 'paper' for simulated trading, 'live' for real trading.")

class ApiKeyCreate(ApiKeyBase):
    """Pydantic model for creating a new API key."""
    secret_key: str = Field(..., description="The secret key associated with the API key. This is required for creation.")

class ApiKeyUpdate(BaseModel):
    """Pydantic model for updating an existing API key. All fields are optional."""
    alias: Optional[str] = Field(None, description="A new user-friendly name for the API key.")
    api_key: Optional[str] = Field(None, description="A new API key string. Provide only if changing.")
    secret_key: Optional[str] = Field(None, description="A new secret key. Provide only if changing. Will be stored securely (conceptual).")
    mode: Optional[ApiMode] = Field(None, description="A new trading mode for the API key.")

class ApiKey(ApiKeyBase): # For responses
    """Pydantic model for representing an API key in responses."""
    id: uuid.UUID = Field(..., description="The unique identifier of the API key.")
    # secret_key is NOT included in responses for security reasons.
    connection_status: str = Field("unknown", description="The current connection status of the API key (e.g., 'connected', 'disconnected', 'error'). This is a transient status updated dynamically.")
    
    class Config:
        orm_mode = True
        use_enum_values = True # Ensures enum values are returned as strings in API responses
