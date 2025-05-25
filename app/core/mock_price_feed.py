import random
import asyncio
from typing import Dict

mock_prices: Dict[str, float] = {
    "SUI/USDT": 1.5,
    "BTC/USDT": 60000.0,
    "ETH/USDT": 4000.0,
}

async def get_mock_price(trading_pair: str) -> float:
    """
    Simulates fetching a mock price for a given trading pair.
    """
    if trading_pair not in mock_prices:
        # Initialize with a default price if not found, or handle as an error
        # For now, let's initialize to a common low value like $1 for unknown pairs
        mock_prices[trading_pair] = 1.0 
        # Alternatively, could raise ValueError(f"Trading pair {trading_pair} not found in mock prices")

    # Simulate a small price change
    # Adjust the multiplier (e.g., 0.005 for 0.5% max change per tick) for volatility
    # Current price for the pair
    price = mock_prices[trading_pair]
    
    # Prevent extreme volatility for very low prices
    if price < 1: 
        change_percentage_cap = 0.05 # Max 5% change if price is < $1
    elif price < 10:
        change_percentage_cap = 0.02 # Max 2% change if price is < $10
    else:
        change_percentage_cap = 0.005 # Max 0.5% for others

    change = random.uniform(-change_percentage_cap, change_percentage_cap) * price
    
    new_price = price + change
    
    # Ensure price doesn't go below a certain threshold (e.g., 0.01)
    mock_prices[trading_pair] = max(0.01, new_price)
    
    await asyncio.sleep(0.1)  # Simulate a small delay in fetching price
    
    return mock_prices[trading_pair]
