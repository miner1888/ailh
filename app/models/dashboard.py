from typing import Optional, List
from uuid import UUID
from pydantic import BaseModel, Field
from app.models.strategy import StrategyConfig
from app.models.active_strategy import ActiveStrategyState

class DashboardStrategyData(BaseModel):
    """Aggregated data for a single strategy to be displayed on the dashboard."""
    strategy_config: StrategyConfig = Field(..., description="The configuration of the strategy.")
    active_state: Optional[ActiveStrategyState] = Field(None, description="The current active state of the strategy, if it has been started. Null if never started or in an error state not yet captured in state.")
    current_market_price: Optional[float] = Field(None, description="The current market price for the strategy's trading pair. Null if price feed is unavailable.")
    
    class Config:
        use_enum_values = True # Ensure enums within nested models are also stringified

class DashboardDataResponse(BaseModel):
    """Response model for the dashboard, containing a list of all strategies' data."""
    strategies_data: List[DashboardStrategyData] = Field(..., description="A list of data objects, each representing a strategy and its current state for dashboard display.")
