from enum import Enum
from typing import Optional, Tuple
from app.models.strategy import StrategyConfig

class SignalType(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    COVER = "COVER"

class ValidationState(str, Enum):
    IDLE = "IDLE"
    CONDITION_1_MET = "CONDITION_1_MET"
    # CONDITION_2_MET would imply an action is taken, then state resets to IDLE or a post-action state.
    # For the purpose of these functions, returning a boolean signal is enough.

def check_price_movement(
    current_price: float, 
    reference_price: float, 
    required_percentage_change: float, 
    direction: str
) -> bool:
    """
    Checks if the price has moved by a required percentage in the specified direction.
    'direction' can be "up" (for sell/profit-taking) or "down" (for buy/cover).
    """
    if reference_price <= 0: # Changed to <= to also handle negative reference prices if they could occur
        # Avoid division by zero or nonsensical calculations with non-positive reference.
        # This case might indicate an issue or need specific handling based on context.
        return False 

    actual_percentage_change = (current_price - reference_price) / reference_price * 100

    if direction == "up":
        return actual_percentage_change >= required_percentage_change
    elif direction == "down":
        return actual_percentage_change <= -required_percentage_change
    else:
        raise ValueError("Direction must be 'up' or 'down'")

def check_callback_condition(
    current_price: float, 
    price_at_cond1_met: float, 
    required_callback_percentage: float, 
    initial_trigger_direction: str
) -> bool:
    """
    Checks if the price has "callbacked" by a certain percentage after Condition 1 was met.
    'initial_trigger_direction' is the direction that triggered Condition 1 ("up" or "down").
    """
    if price_at_cond1_met <= 0: # Changed to <= to also handle negative reference prices
        # Avoid division by zero or nonsensical calculations.
        return False

    if initial_trigger_direction == "down": 
        # For a buy trigger (price fell), callback is a price rise from that low point.
        # Example: Price fell to $90 (price_at_cond1_met). Callback is 0.5%.
        # Current price must be >= $90 * (1 + 0.005) = $90.45.
        callback_percentage = (current_price - price_at_cond1_met) / price_at_cond1_met * 100
        return callback_percentage >= required_callback_percentage
    elif initial_trigger_direction == "up": 
        # For a sell trigger (price rose), callback is a price fall from that high point.
        # Example: Price rose to $110 (price_at_cond1_met). Callback is 0.5%.
        # Current price must be <= $110 * (1 - 0.005) = $109.45.
        # The formula (price_at_cond1_met - current_price) correctly captures this drop as a positive percentage.
        callback_percentage = (price_at_cond1_met - current_price) / price_at_cond1_met * 100
        return callback_percentage >= required_callback_percentage
    else:
        raise ValueError("Initial trigger direction must be 'up' or 'down'")

# --- Strategy-Specific Application Helper Functions ---

async def should_initial_buy( # Changed to async
    strategy_config: StrategyConfig, 
    current_price: float, 
    reference_price: float, # e.g., price at strategy start or a defined baseline
    current_validation_state: ValidationState, 
    price_at_cond1_met: Optional[float]
) -> Tuple[ValidationState, Optional[float], bool]: # Return type unchanged
    """
    Determines if an initial buy signal should be generated based on the double condition validation.
    Returns: (new_validation_state, new_price_at_cond1_met, buy_signal)
    """
    signal_generated = False
    new_price_at_cond1_met = price_at_cond1_met

    # Special case for immediate action if both trigger and callback percentages are zero.
    # This means the strategy intends to act as soon as possible without specific price movement conditions.
    # Note: For a buy, this means buying at `reference_price` or current market if no specific `reference_price` is defined yet.
    # For a sell, it means selling at `entry_price`. For cover, at `cover_reference_price_value`.
    # The actual price check (e.g. current_price >= entry_price for sell) is implicitly handled by
    # `check_price_movement` when percentages are zero.
    if strategy_config.buy_trigger_fall_percentage == 0 and strategy_config.buy_confirm_callback_percentage == 0:
        # Check if current price is at or below reference for a buy (0% fall means at or below)
        if check_price_movement(current_price, reference_price, 0, "down"):
            return ValidationState.IDLE, None, True # Signal buy, reset state
        else:
            return ValidationState.IDLE, None, False # Price condition for 0% fall not met

    if current_validation_state == ValidationState.IDLE:
        # Check for Condition 1: Price falls by buy_trigger_fall_percentage from the reference price.
        if check_price_movement(current_price, reference_price, strategy_config.buy_trigger_fall_percentage, "down"):
            # Condition 1 met. Transition to CONDITION_1_MET state.
            # Record the price at which Cond1 was met; this becomes the reference for callback.
            current_validation_state = ValidationState.CONDITION_1_MET
            new_price_at_cond1_met = current_price
    
    if current_validation_state == ValidationState.CONDITION_1_MET:
        if new_price_at_cond1_met is None: 
            # Defensive check: Should not happen if logic flows from IDLE to CONDITION_1_MET correctly.
            # If it does, reset to IDLE to prevent errors.
            return ValidationState.IDLE, None, False 

        # Re-evaluate Condition 1 against the *original reference_price*.
        # If the price has moved such that Condition 1 is no longer satisfied (e.g., price bounced up too high),
        # reset the state to IDLE. price_at_cond1_met is also reset.
        if not check_price_movement(current_price, reference_price, strategy_config.buy_trigger_fall_percentage, "down"):
            current_validation_state = ValidationState.IDLE
            new_price_at_cond1_met = None
        else:
            # Condition 1 is still met. Now check for Condition 2 (Callback).
            # The callback is a price rise from `new_price_at_cond1_met` (the price when Cond1 was first triggered).
            if check_callback_condition(current_price, new_price_at_cond1_met, strategy_config.buy_confirm_callback_percentage, "down"):
                signal_generated = True # Both conditions met, generate signal.
                current_validation_state = ValidationState.IDLE # Reset state after signal.
                new_price_at_cond1_met = None # Reset price_at_cond1_met.
                
    return current_validation_state, new_price_at_cond1_met, signal_generated

async def should_sell_for_profit( # Changed to async
    strategy_config: StrategyConfig, 
    current_price: float, 
    entry_price: float, # The price at which the asset was bought
    current_validation_state: ValidationState, 
    price_at_cond1_met: Optional[float]
) -> Tuple[ValidationState, Optional[float], bool]: # Return type unchanged
    """
    Determines if a sell signal for profit-taking should be generated.
    Returns: (new_validation_state, new_price_at_cond1_met, sell_signal)
    """
    signal_generated = False
    new_price_at_cond1_met = price_at_cond1_met

    # Special case for immediate action if both trigger and callback percentages are zero.
    if strategy_config.sell_trigger_rise_percentage == 0 and strategy_config.sell_callback_percentage == 0:
        # Check if current price is at or above entry price for a sell (0% rise means at or above)
        if check_price_movement(current_price, entry_price, 0, "up"):
            return ValidationState.IDLE, None, True # Signal sell, reset state
        else:
            return ValidationState.IDLE, None, False # Price condition for 0% rise not met

    if current_validation_state == ValidationState.IDLE:
        # Check for Condition 1: Price rises by sell_trigger_rise_percentage from the entry_price.
        if check_price_movement(current_price, entry_price, strategy_config.sell_trigger_rise_percentage, "up"):
            current_validation_state = ValidationState.CONDITION_1_MET
            new_price_at_cond1_met = current_price # Record price when Cond1 met.
            
    if current_validation_state == ValidationState.CONDITION_1_MET:
        if new_price_at_cond1_met is None: # Defensive check.
            return ValidationState.IDLE, None, False

        # Re-evaluate Condition 1 against the *original entry_price*.
        # If price has fallen such that Cond1 is no longer met, reset state.
        if not check_price_movement(current_price, entry_price, strategy_config.sell_trigger_rise_percentage, "up"):
            current_validation_state = ValidationState.IDLE
            new_price_at_cond1_met = None
        else:
            # Condition 1 still met. Check for Condition 2 (Callback).
            # Callback is a price fall from `new_price_at_cond1_met`.
            if check_callback_condition(current_price, new_price_at_cond1_met, strategy_config.sell_callback_percentage, "up"):
                signal_generated = True # Both conditions met.
                current_validation_state = ValidationState.IDLE # Reset state.
                new_price_at_cond1_met = None # Reset.
                
    return current_validation_state, new_price_at_cond1_met, signal_generated

async def should_buy_for_cover( # Changed to async
    strategy_config: StrategyConfig, 
    current_price: float, 
    cover_reference_price_value: float, # Calculated based on strategy's cover_reference_price setting
    current_validation_state: ValidationState, 
    price_at_cond1_met: Optional[float]
) -> Tuple[ValidationState, Optional[float], bool]: # Return type unchanged
    """
    Determines if a buy signal for a cover order should be generated.
    Returns: (new_validation_state, new_price_at_cond1_met, cover_buy_signal)
    """
    signal_generated = False
    new_price_at_cond1_met = price_at_cond1_met

    # Special case for immediate action if both trigger and callback percentages are zero.
    if strategy_config.cover_trigger_fall_percentage == 0 and strategy_config.cover_confirm_callback_percentage == 0:
        # Check if current price is at or below cover reference for a buy (0% fall means at or below)
        if check_price_movement(current_price, cover_reference_price_value, 0, "down"):
            return ValidationState.IDLE, None, True # Signal buy, reset state
        else:
            return ValidationState.IDLE, None, False # Price condition for 0% fall not met

    if current_validation_state == ValidationState.IDLE:
        # Check for Condition 1: Price falls by cover_trigger_fall_percentage from cover_reference_price_value.
        if check_price_movement(current_price, cover_reference_price_value, strategy_config.cover_trigger_fall_percentage, "down"):
            current_validation_state = ValidationState.CONDITION_1_MET
            new_price_at_cond1_met = current_price # Record price.
            
    if current_validation_state == ValidationState.CONDITION_1_MET:
        if new_price_at_cond1_met is None: # Defensive check.
            return ValidationState.IDLE, None, False

        # Re-evaluate Condition 1 against the *original cover_reference_price_value*.
        # If price has bounced up, reset state.
        if not check_price_movement(current_price, cover_reference_price_value, strategy_config.cover_trigger_fall_percentage, "down"):
            current_validation_state = ValidationState.IDLE
            new_price_at_cond1_met = None
        else:
            # Condition 1 still met. Check for Condition 2 (Callback).
            # Callback is a price rise from `new_price_at_cond1_met`.
            if check_callback_condition(current_price, new_price_at_cond1_met, strategy_config.cover_confirm_callback_percentage, "down"):
                signal_generated = True # Both conditions met.
                current_validation_state = ValidationState.IDLE # Reset state.
                new_price_at_cond1_met = None # Reset.
                
    return current_validation_state, new_price_at_cond1_met, signal_generated
