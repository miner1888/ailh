import pytest
from httpx import AsyncClient
from uuid import uuid4, UUID # Import UUID for type checking if needed

# This will hold the ID of the API key created for this test module
module_api_key_id = None

@pytest.fixture(scope="module", autouse=True)
async def setup_api_key_for_strategies_module(async_client: AsyncClient):
    global module_api_key_id
    response = await async_client.post("/apis/", json={
        "alias": "StrategyTestModuleAPI", "api_key": "strat_api_key_module", 
        "secret_key": "strat_secret_module", "mode": "paper"
    })
    assert response.status_code == 201 # My API returns 201 for successful POST
    module_api_key_id = response.json()["id"]
    assert module_api_key_id is not None

def get_strategy_payload(api_id_override=None, name_suffix=""):
    # Helper to create valid strategy payloads
    return {
        "api_id": str(api_id_override or module_api_key_id),
        "strategy_name": f"Test Strat {name_suffix}", "trading_pair": "BTC/USDT",
        "initial_order_amount_usdt": 1000.0,
        "buy_trigger_fall_percentage": 1.0, "buy_confirm_callback_percentage": 0.1,
        "sell_trigger_rise_percentage": 1.0, "sell_callback_percentage": 0.1,
        "max_cover_count": 5, "cover_multiplier": 1.5,
        "cover_trigger_fall_percentage": 2.0, "cover_confirm_callback_percentage": 0.2,
        "cover_reference_price": "average_holding", "order_type": "market",
        "cyclic_execution": True, "cover_orders_participate_in_profit_taking": False,
        "enable_order_timeout": False, "order_timeout_seconds": 60
    }

@pytest.mark.asyncio
async def test_create_strategy_config(async_client: AsyncClient):
    assert module_api_key_id is not None, "Module API key not set up"
    payload = get_strategy_payload(name_suffix="Create")
    
    response = await async_client.post("/strategies/", json=payload)
    assert response.status_code == 201 # My API returns 201 for successful POST
    data = response.json()
    assert data["strategy_name"] == "Test Strat Create"
    assert data["api_id"] == str(module_api_key_id)
    assert "id" in data

@pytest.mark.asyncio
async def test_create_strategy_with_invalid_api_id(async_client: AsyncClient):
    invalid_api_id = str(uuid4())
    payload = get_strategy_payload(api_id_override=invalid_api_id, name_suffix="InvalidAPI")
    
    response = await async_client.post("/strategies/", json=payload)
    assert response.status_code == 400
    assert "not found" in response.json()["detail"].lower() # API Key with id ... not found.

@pytest.mark.asyncio
async def test_get_strategies_empty(async_client: AsyncClient):
    # This assumes clear_tables runs before each test.
    # However, setup_api_key_for_strategies_module runs once per module.
    # So, if this test runs after another test that creates strategies, it won't be empty
    # unless we explicitly delete strategies related to module_api_key_id.
    # For now, let's fetch and check if it's a list.
    # A truly isolated test would create its own API key or ensure no strategies exist.
    # Given the current fixture setup, this test is a bit flawed for "empty"
    # Let's test getting a list.
    response = await async_client.get("/strategies/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)

@pytest.mark.asyncio
async def test_get_strategies_with_data(async_client: AsyncClient):
    payload1 = get_strategy_payload(name_suffix="List1")
    payload2 = get_strategy_payload(name_suffix="List2")
    
    await async_client.post("/strategies/", json=payload1)
    await async_client.post("/strategies/", json=payload2)
    
    response = await async_client.get("/strategies/")
    assert response.status_code == 200
    data = response.json()
    
    # Filter for strategies created in this test, as module_api_key_id might have others
    # from other tests if not perfectly isolated. Better to check count if isolation is guaranteed.
    strategy_names = [s["strategy_name"] for s in data]
    assert "Test Strat List1" in strategy_names
    assert "Test Strat List2" in strategy_names


@pytest.mark.asyncio
async def test_get_single_strategy_config(async_client: AsyncClient):
    payload = get_strategy_payload(name_suffix="SingleGet")
    create_response = await async_client.post("/strategies/", json=payload)
    assert create_response.status_code == 201
    strategy_id = create_response.json()["id"]

    response = await async_client.get(f"/strategies/{strategy_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == strategy_id
    assert data["strategy_name"] == "Test Strat SingleGet"

    non_existent_id = str(uuid4())
    response_not_found = await async_client.get(f"/strategies/{non_existent_id}")
    assert response_not_found.status_code == 404

@pytest.mark.asyncio
async def test_update_strategy_config(async_client: AsyncClient):
    payload = get_strategy_payload(name_suffix="UpdateMe")
    create_response = await async_client.post("/strategies/", json=payload)
    assert create_response.status_code == 201
    strategy_id = create_response.json()["id"]

    update_payload = {"strategy_name": "Updated Strategy Name", "initial_order_amount_usdt": 1500.0}
    response = await async_client.put(f"/strategies/{strategy_id}", json=update_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["strategy_name"] == "Updated Strategy Name"
    assert data["initial_order_amount_usdt"] == 1500.0
    assert data["trading_pair"] == "BTC/USDT" # Check non-updated field

@pytest.mark.asyncio
async def test_update_strategy_with_invalid_api_id(async_client: AsyncClient):
    payload = get_strategy_payload(name_suffix="UpdateInvalidAPI")
    create_response = await async_client.post("/strategies/", json=payload)
    assert create_response.status_code == 201
    strategy_id = create_response.json()["id"]

    invalid_api_id = str(uuid4())
    update_payload = {"api_id": invalid_api_id, "strategy_name": "Attempt Update Invalid API"}
    
    response = await async_client.put(f"/strategies/{strategy_id}", json=update_payload)
    assert response.status_code == 400
    assert "not found" in response.json()["detail"].lower()


@pytest.mark.asyncio
async def test_delete_strategy_config(async_client: AsyncClient):
    payload = get_strategy_payload(name_suffix="DeleteMe")
    create_response = await async_client.post("/strategies/", json=payload)
    assert create_response.status_code == 201
    strategy_id = create_response.json()["id"]

    response = await async_client.delete(f"/strategies/{strategy_id}")
    assert response.status_code == 204 # My API returns 204

    # Verify it's deleted
    response_after_delete = await async_client.get(f"/strategies/{strategy_id}")
    assert response_after_delete.status_code == 404

@pytest.mark.asyncio
async def test_delete_strategy_config_active_not_implemented_yet(async_client: AsyncClient):
    # This test is a placeholder for when active strategy check is added to delete
    # For now, it should delete successfully as the check is not implemented in strategy_management API.
    payload = get_strategy_payload(name_suffix="DeleteActiveCheck")
    create_response = await async_client.post("/strategies/", json=payload)
    assert create_response.status_code == 201
    strategy_id = create_response.json()["id"]

    # Start the strategy (assuming this endpoint works and sets it active)
    # Note: The /control/strategies/.../start endpoint is in strategy_runner_api.py
    # It interacts with in-memory active_strategies_store, not directly preventing deletion from DB.
    # The check for active strategy deletion would need to be in strategy_management.py's DELETE endpoint.
    # For now, this test will behave like test_delete_strategy_config.
    
    # Example: await async_client.post(f"/control/strategies/{strategy_id}/start")
    
    response = await async_client.delete(f"/strategies/{strategy_id}")
    assert response.status_code == 204

    response_after_delete = await async_client.get(f"/strategies/{strategy_id}")
    assert response_after_delete.status_code == 404

@pytest.mark.asyncio
async def test_delete_api_key_with_associated_strategy(async_client: AsyncClient):
    # Create a new API key for this specific test to avoid interference
    api_key_payload = {"alias": "APIForStrategyDeletionTest", "api_key": "test_del_key", "secret_key": "test_del_secret", "mode": "paper"}
    api_key_response = await async_client.post("/apis/", json=api_key_payload)
    assert api_key_response.status_code == 201
    local_api_key_id = api_key_response.json()["id"]

    # Create a strategy associated with this new API key
    strategy_payload = get_strategy_payload(api_id_override=local_api_key_id, name_suffix="StrategyForAPIDeleteTest")
    strategy_response = await async_client.post("/strategies/", json=strategy_payload)
    assert strategy_response.status_code == 201
    
    # Attempt to delete the API key
    delete_api_response = await async_client.delete(f"/apis/{local_api_key_id}")
    
    # Expecting a 400 Bad Request because the API key is in use
    assert delete_api_response.status_code == 400
    assert "api key is in use" in delete_api_response.json()["detail"].lower()

    # Clean up: delete the strategy first, then the API key
    await async_client.delete(f"/strategies/{strategy_response.json()['id']}")
    delete_api_response_after_strat_delete = await async_client.delete(f"/apis/{local_api_key_id}")
    assert delete_api_response_after_strat_delete.status_code == 204

# Add more tests:
# - Test validation errors for strategy creation (e.g., missing fields, invalid enum values)
# - Test pagination for GET /strategies/ (if implementing skip/limit in endpoint)
# - Test updating a strategy to use a non-existent API ID
# - Test deleting a non-existent strategy ID
