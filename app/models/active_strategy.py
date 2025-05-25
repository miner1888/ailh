from uuid import UUID
from app.core.trading_logic import ValidationState
from typing import Optional, List, Dict # Dict is specified in prompt, but not used in current model
from datetime import datetime
from pydantic import BaseModel, Field

class IndividualPosition(BaseModel):
    """Represents an individual buy order, especially when cover orders are sold separately."""
    entry_price: float = Field(..., description="The price at which this specific position was entered.")
    quantity: float = Field(..., description="The quantity of the asset bought for this position.")
    sell_validation_state: ValidationState = Field(ValidationState.IDLE, description="The validation state for selling this individual position.")
    sell_price_at_cond1_met: Optional[float] = Field(None, description="The market price when the sell condition 1 was met for this individual position.")

    class Config:
        use_enum_values = True

class ActiveStrategyState(BaseModel):
    """Represents the dynamic state of a running trading strategy."""
    strategy_id: UUID = Field(..., description="The ID of the strategy configuration this state belongs to.")
    api_id: UUID = Field(..., description="The API key ID being used by this strategy instance (copied from StrategyConfig).")
    trading_pair: str = Field(..., description="The trading pair for this strategy instance (copied from StrategyConfig).")
    is_running: bool = Field(False, description="True if the strategy is currently active and processing, False otherwise.")
    
    # Position and P&L
    current_position_quantity: float = Field(0.0, description="Total quantity of the asset currently held.")
    average_entry_price: float = Field(0.0, description="The average price at which the current total position was acquired.")
    initial_entry_price: Optional[float] = Field(None, description="Price of the very first buy order in the current cycle/position.")
    last_buy_price: Optional[float] = Field(None, description="Price of the most recent buy order (either initial or a cover buy).")
    total_invested_usdt: float = Field(0.0, description="Current total cost (in USDT) of all assets held for this strategy.")
    realized_pnl_usdt: float = Field(0.0, description="Total profit or loss (in USDT) realized from completed sell trades.")
    unrealized_pnl_usdt: float = Field(0.0, description="Current unrealized profit or loss (in USDT) for the open position, based on current market price.")
    
    # Cover Order Management
    cover_orders_count: int = Field(0, description="Number of cover buy orders executed for the current main position.")
    
    # Validation States for different actions
    buy_validation_state: ValidationState = Field(ValidationState.IDLE, description="Validation state for the initial buy condition.")
    buy_price_at_cond1_met: Optional[float] = Field(None, description="Market price when initial buy condition 1 was met.")
    
    sell_validation_state: ValidationState = Field(ValidationState.IDLE, description="Validation state for the main profit-taking sell condition (used when not selling cover orders individually).")
    sell_price_at_cond1_met: Optional[float] = Field(None, description="Market price when main sell condition 1 was met.")

    cover_validation_state: ValidationState = Field(ValidationState.IDLE, description="Validation state for cover buy conditions.")
    cover_price_at_cond1_met: Optional[float] = Field(None, description="Market price when cover buy condition 1 was met.")
    
    individual_positions: List[IndividualPosition] = Field(default_factory=list, description="List of individual positions, used if 'cover_orders_participate_in_profit_taking' is true.")
    
    # Operational Info
    last_error: Optional[str] = Field(None, description="Stores the message of the last error encountered by the strategy execution loop.")
    next_action_timestamp: Optional[datetime] = Field(None, description="Timestamp for any scheduled future action, e.g., order timeout check (conceptual).")
    current_market_price_for_reference: Optional[float] = Field(None, description="Market price recorded at the start of the strategy or when the initial buy reference point is set.")
    
    class Config:
        use_enum_values = True
        # orm_mode = True # Not strictly needed if not directly converting from DB models using these exact fields.
                         # The process_strategy function returns this model, but builds it manually.
                         # However, if used as a response_model in FastAPI for something that IS from_orm, it would be needed.
                         # For now, let's keep it commented as its primary use is in-memory state.
