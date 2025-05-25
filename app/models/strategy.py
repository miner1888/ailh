import uuid
from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field

class CoverReferencePrice(str, Enum):
    """Determines the reference price used for calculating cover order triggers."""
    AVERAGE_HOLDING = "average_holding"
    LAST_BUY_PRICE = "last_buy_price"
    INITIAL_PRICE = "initial_price"

class OrderType(str, Enum):
    """Specifies the type of order to be placed (conceptual)."""
    MARKET = "market"
    LIMIT = "limit"

class StrategyConfigBase(BaseModel):
    """Base Pydantic model for strategy configuration data."""
    api_id: uuid.UUID = Field(..., description="The ID of the API key to be used for this strategy.")
    strategy_name: str = Field(..., max_length=100, description="A user-defined name for the strategy (e.g., 'SUI Low-Risk Grid').")
    trading_pair: str = Field(..., max_length=20, description="The trading pair for the strategy (e.g., 'SUI/USDT').")
    
    initial_order_amount_usdt: float = Field(..., gt=0, description="The amount in USDT for the initial buy order.")
    
    buy_trigger_fall_percentage: float = Field(
        default=0.0, ge=0, 
        description="Percentage the price must fall from the reference (e.g., strategy start price) to trigger the initial buy condition. 0 means no fall check needed."
    )
    buy_confirm_callback_percentage: float = Field(
        default=0.0, ge=0,
        description="Percentage the price must rise from its lowest point (after buy trigger) to confirm the initial buy. If both buy triggers are 0, buy happens at current market price."
    )
    
    sell_trigger_rise_percentage: float = Field(
        ..., gt=0, 
        description="Percentage the price must rise from the entry price (or average entry price) to trigger the sell condition for profit taking."
    )
    sell_callback_percentage: float = Field(
        default=0.0, ge=0,
        description="Percentage the price must fall from its highest point (after sell trigger) to confirm the sell. 0 means sell immediately after rise trigger."
    )
    
    max_cover_count: int = Field(..., ge=0, description="Maximum number of cover (补仓) orders to place.")
    cover_multiplier: float = Field(
        default=1.0, ge=0,
        description="Multiplier for the amount of subsequent cover orders relative to the initial order amount (e.g., 1.0 means same amount, 2.0 means double)."
    )
    cover_trigger_fall_percentage: float = Field(
        ..., gt=0,
        description="Percentage the price must fall from the cover reference price to trigger a cover buy condition."
    )
    cover_confirm_callback_percentage: float = Field(
        default=0.0, ge=0,
        description="Percentage the price must rise from its lowest point (after cover buy trigger) to confirm the cover buy."
    )
    cover_reference_price: CoverReferencePrice = Field(
        default=CoverReferencePrice.AVERAGE_HOLDING,
        description="The reference price used for calculating cover order triggers ('average_holding', 'last_buy_price', 'initial_price')."
    )
    
    order_type: OrderType = Field(OrderType.MARKET, description="The type of order to place (conceptual, 'market' or 'limit').")
    cyclic_execution: bool = Field(True, description="If true, the strategy will attempt to restart its cycle (e.g., place a new initial buy) after a successful sell.")
    cover_orders_participate_in_profit_taking: bool = Field(
        False, 
        description="If true, cover orders are sold individually for profit based on their own entry price and sell triggers. If false, all holdings (initial + covers) are sold together based on average entry price."
    )
    
    enable_order_timeout: bool = Field(False, description="If true, orders will have a timeout period (conceptual feature).")
    order_timeout_seconds: int = Field(
        default=60, ge=10, 
        description="Duration in seconds after which an unfilled order might be considered timed out (conceptual)."
    )

class StrategyCreate(StrategyConfigBase):
    """Pydantic model for creating a new strategy configuration."""
    pass # All fields inherited from StrategyConfigBase

class StrategyUpdate(BaseModel):
    """Pydantic model for updating an existing strategy configuration. All fields are optional."""
    api_id: Optional[uuid.UUID] = Field(None, description="A new API key ID for the strategy.")
    strategy_name: Optional[str] = Field(None, max_length=100, description="A new user-defined name for the strategy.")
    trading_pair: Optional[str] = Field(None, max_length=20, description="A new trading pair for the strategy.")
    initial_order_amount_usdt: Optional[float] = Field(None, gt=0, description="A new amount in USDT for the initial buy order.")
    
    buy_trigger_fall_percentage: Optional[float] = Field(None, ge=0, description="New buy trigger fall percentage.")
    buy_confirm_callback_percentage: Optional[float] = Field(None, ge=0, description="New buy confirm callback percentage.")
    sell_trigger_rise_percentage: Optional[float] = Field(None, gt=0, description="New sell trigger rise percentage.")
    sell_callback_percentage: Optional[float] = Field(None, ge=0, description="New sell callback percentage.")
    
    max_cover_count: Optional[int] = Field(None, ge=0, description="New maximum number of cover orders.")
    cover_multiplier: Optional[float] = Field(None, ge=0, description="New cover multiplier.")
    cover_trigger_fall_percentage: Optional[float] = Field(None, gt=0, description="New cover trigger fall percentage.")
    cover_confirm_callback_percentage: Optional[float] = Field(None, ge=0, description="New cover confirm callback percentage.")
    cover_reference_price: Optional[CoverReferencePrice] = Field(None, description="New cover reference price.")
    
    order_type: Optional[OrderType] = Field(None, description="New order type.")
    cyclic_execution: Optional[bool] = Field(None, description="Enable/disable cyclic execution.")
    cover_orders_participate_in_profit_taking: Optional[bool] = Field(None, description="Enable/disable individual profit taking for cover orders.")
    enable_order_timeout: Optional[bool] = Field(None, description="Enable/disable order timeout.")
    order_timeout_seconds: Optional[int] = Field(None, ge=10, description="New order timeout duration in seconds.")

class StrategyConfig(StrategyConfigBase): # For responses
    """Pydantic model for representing a strategy configuration in responses."""
    id: uuid.UUID = Field(..., description="The unique identifier of the strategy configuration.")
    
    class Config:
        orm_mode = True
        use_enum_values = True # Ensures enum values are returned as strings in API responses
