import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
# from fastapi.testclient import TestClient # Not used for async tests here
from httpx import AsyncClient 

from app.main import app # Main FastAPI app
from app.database import Base, get_db 
# Import your DB models if needed directly in conftest, but usually not required here
# from app.models_db import ApiKeyDB, StrategyConfigDB 

SQLALCHEMY_DATABASE_URL_TEST = "sqlite:///./test.db" 

engine_test = create_engine(
    SQLALCHEMY_DATABASE_URL_TEST, connect_args={"check_same_thread": False}
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine_test)

# Override get_db dependency for tests
def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db

@pytest.fixture(scope="session", autouse=True)
def setup_db():
    # Create tables once per session
    Base.metadata.create_all(bind=engine_test)
    yield
    # Optional: Clean up the test database file after tests run
    import os
    if os.path.exists("./test.db"):
        os.remove("./test.db")

@pytest.fixture(scope="function", autouse=True)
def clear_tables(request): # Added request to conditionally skip for non-async tests if needed
    # Clear data from tables before each test function
    # This ensures test isolation
    # Need to handle how this interacts if some tests are session-scoped and others function-scoped
    # For now, assuming all relevant tests are function-scoped or module-scoped using async_client
    
    # Check if the test is an async test using the async_client fixture
    # This is a bit of a workaround. A better way might be custom markers or specific fixtures for DB clearing.
    is_async_test = "async_client" in request.fixturenames
    
    if is_async_test: # Only clear for tests that are likely to use the DB via API
        connection = engine_test.connect()
        transaction = connection.begin()
        for table in reversed(Base.metadata.sorted_tables):
            connection.execute(table.delete())
        transaction.commit()
        connection.close()
    yield # Test runs here


@pytest.fixture(scope="module")
async def async_client():
    # Ensure the app's dependency overrides are set before the client is created
    # This is usually fine as app is imported and modified at module level.
    app.dependency_overrides[get_db] = override_get_db
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client
