from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi import Depends # Added Depends
from sqlalchemy.orm import Session # Added Session
from app.main import templates # Import templates from main.py

from app.models.dashboard import DashboardStrategyData, DashboardDataResponse
# from app.api.strategy_management import db_strategies # Removed direct import
from app import crud # Added crud import
from app.database import get_db # Added get_db import
from app.core.strategy_runner import active_strategies_store # Direct import (remains in-memory)
from app.core.mock_price_feed import get_mock_price # Direct import
from uuid import UUID


router = APIRouter(
    tags=["Frontend UI Service"], # Updated tag
    include_in_schema=False # Keep these internal UI routes out of the main API docs
)

@router.get(
    "/ui/dashboard-data", 
    response_model=DashboardDataResponse,
    summary="Get Aggregated Dashboard Data (UI)",
    description="Internal endpoint to fetch all necessary data for rendering the main dashboard UI, including strategy configurations, their active states, and current market prices."
)
async def get_dashboard_data(db: Session = Depends(get_db)):
    """
    Fetches and aggregates data for all strategies to be displayed on the dashboard.
    This includes:
    - All strategy configurations from the database.
    - Their corresponding active states (if any) from the in-memory store.
    - Current mock market prices for each relevant trading pair.
    """
    response_data = []
    unique_pairs = set()

    # Collect all unique trading pairs first
    all_strategy_configs = crud.get_strategy_configs(db) # Use crud
    for config in all_strategy_configs:
        unique_pairs.add(config.trading_pair)
    
    # Get current prices for all unique pairs
    current_prices_map = {}
    for pair in unique_pairs:
        try:
            current_prices_map[pair] = await get_mock_price(pair)
        except Exception: # Handle if a pair in config is not in mock_prices
            current_prices_map[pair] = None

    for config in all_strategy_configs: # Use fetched configs
        state = active_strategies_store.get(config.id) # active_strategies_store is still in-memory
        price = current_prices_map.get(config.trading_pair)
        
        response_data.append(
            DashboardStrategyData(
                strategy_config=config,
                active_state=state,
                current_market_price=price
            )
        )
    return DashboardDataResponse(strategies_data=response_data)

@router.get(
    "/", 
    response_class=HTMLResponse, 
    name="serve_index",
    summary="Serve Index/Dashboard Page (UI)",
    description="Serves the main HTML page for the trading dashboard."
)
async def serve_index_page(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@router.get(
    "/api-management-page", 
    response_class=HTMLResponse, 
    name="serve_api_management_page",
    summary="Serve API Key Management Page (UI)",
    description="Serves the HTML page for managing API keys."
)
async def serve_api_management_actual_page(request: Request):
    return templates.TemplateResponse("api_management.html", {"request": request})

@router.get(
    "/add-strategy-page", 
    response_class=HTMLResponse, 
    name="serve_add_strategy_page",
    summary="Serve Add Strategy Page (UI)",
    description="Serves the HTML page for creating new trading strategy configurations."
)
async def serve_add_strategy_actual_page(request: Request): 
    return templates.TemplateResponse("add_strategy.html", {"request": request})
