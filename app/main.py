from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates # Keep this for main's use if any, or frontend_routes will have its own

# Database imports for table creation
from app.database import engine, Base
from app import models_db # Ensure models are imported so Base knows about them

from app.api.api_management import router as api_management_router
from app.api.strategy_management import router as strategy_management_router
from app.api.strategy_runner_api import router as strategy_runner_router
# We will create frontend_routes.py later, but let's prepare its import
from app.api.frontend_routes import router as frontend_router # Uncommented


# Create database tables on startup (for development)
# For production, Alembic should be used.
Base.metadata.create_all(bind=engine)

app = FastAPI()

# Mount static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Initialize Jinja2 templates - this instance will be imported by frontend_routes
templates = Jinja2Templates(directory="app/templates")

# Include the API management router
app.include_router(api_management_router, prefix="/apis", tags=["API Management"])

# Include the Strategy management router
app.include_router(strategy_management_router, prefix="/strategies", tags=["Strategy Management"])

# Include the Strategy runner router
app.include_router(strategy_runner_router, prefix="/control", tags=["Strategy Control"])

# Include the Frontend router (will be uncommented once file exists)
app.include_router(frontend_router) # Uncommented

# The root path "/" will be handled by the frontend router's serve_index_page
# So, the old @app.get("/") can be removed or commented out.
# @app.get("/")
# async def root():
#     return {"message": "Hello World"}

if __name__ == "__main__":
    import uvicorn
    # Ensure the app is run as "app.main:app" for uvicorn, not just "main:app" if main.py is in a subdir
    uvicorn.run("app.main:app", host="0.0.0.0", port=1230, reload=True)
