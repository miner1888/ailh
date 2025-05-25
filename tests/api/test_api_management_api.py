import pytest
from httpx import AsyncClient
from uuid import uuid4

# Note: `pytest.api_key_id` is not ideal for passing state between tests.
# Tests should be independent. For dependent tests (e.g., get/update/delete created item),
# it's better to do the creation within the test or use a more specific fixture.
# For this exercise, we'll follow the prompt's pattern but acknowledge this.

@pytest.mark.asyncio
async def test_create_api_key(async_client: AsyncClient):
    response = await async_client.post("/apis/", json={
        "alias": "Test API", "api_key": "testkey123", "secret_key": "secret123", "mode": "paper"
    })
    assert response.status_code == 201 # Changed to 201 as per typical REST for create
    data = response.json()
    assert data["alias"] == "Test API"
    assert "id" in data
    assert data["connection_status"] == "connected" # Mocked status
    # Store for other tests if needed, but ideally, tests are isolated
    # pytest.api_key_id = data["id"] 

@pytest.mark.asyncio
async def test_get_api_keys_empty(async_client: AsyncClient):
    # This test assumes 'clear_tables' fixture runs before it.
    response = await async_client.get("/apis/")
    assert response.status_code == 200
    assert response.json() == []
        
@pytest.mark.asyncio
async def test_get_api_keys_with_data(async_client: AsyncClient):
    # Create some API keys
    key1_payload = {"alias": "Test API 1", "api_key": "key1", "secret_key": "sec1", "mode": "paper"}
    key2_payload = {"alias": "Test API 2", "api_key": "key2", "secret_key": "sec2", "mode": "live"}
    
    await async_client.post("/apis/", json=key1_payload)
    await async_client.post("/apis/", json=key2_payload)
    
    response = await async_client.get("/apis/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    # Order might not be guaranteed, so check for presence or sort before asserting
    aliases = sorted([item["alias"] for item in data])
    assert aliases == ["Test API 1", "Test API 2"]


@pytest.mark.asyncio
async def test_get_single_api_key(async_client: AsyncClient):
    create_response = await async_client.post("/apis/", json={
        "alias": "Specific API", "api_key": "specific_key", "secret_key": "specific_secret", "mode": "live"
    })
    assert create_response.status_code == 201
    api_id = create_response.json()["id"]

    response = await async_client.get(f"/apis/{api_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == api_id
    assert data["alias"] == "Specific API"

    non_existent_id = str(uuid4()) # Ensure it's a string for URL
    response_not_found = await async_client.get(f"/apis/{non_existent_id}")
    assert response_not_found.status_code == 404

@pytest.mark.asyncio
async def test_update_api_key(async_client: AsyncClient):
    create_response = await async_client.post("/apis/", json={
        "alias": "Update Me", "api_key": "update_key", "secret_key": "update_secret", "mode": "paper"
    })
    assert create_response.status_code == 201
    api_id = create_response.json()["id"]

    update_payload = {"alias": "Updated Alias", "mode": "live"}
    response = await async_client.put(f"/apis/{api_id}", json=update_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["alias"] == "Updated Alias"
    assert data["mode"] == "live"
    assert data["api_key"] == "update_key" # Check non-updated field

@pytest.mark.asyncio
async def test_delete_api_key(async_client: AsyncClient):
    create_response = await async_client.post("/apis/", json={
        "alias": "Delete Me", "api_key": "delete_key", "secret_key": "delete_secret", "mode": "paper"
    })
    assert create_response.status_code == 201
    api_id = create_response.json()["id"]

    response = await async_client.delete(f"/apis/{api_id}")
    assert response.status_code == 204 # Changed to 204 as per typical REST for delete with no content

    # Verify it's deleted
    response_after_delete = await async_client.get(f"/apis/{api_id}")
    assert response_after_delete.status_code == 404
