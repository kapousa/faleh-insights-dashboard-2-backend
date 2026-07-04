import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from routers import payments_router, assessments_router
from src.setup.settings import Settings, settings

# Setup logging to see errors in logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    try:
        logger.info("Starting up: Checking environment variables and connections...")
        # Access settings directly
        if not settings.database_url:
            raise ValueError("DATABASE_URL is missing in settings!")

        logger.info(f"Database URL detected: {settings.database_url[:10]}...")  # Print only prefix for security
        logger.info("Startup complete.")
    except Exception as e:
        logger.error(f"FATAL: Application startup failed: {e}")
        raise e  # This confirms exactly what failed
    yield
    # Shutdown logic
    logger.info("Shutting down...")

app = FastAPI(title="Faleh Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(payments_router)
app.include_router(assessments_router)

@app.get("/")
def read_root():
    import os
    print(f"DATABASE_URL is: {os.getenv('DATABASE_URL')}")  # Check if this is None
    return {"message": "Hello from Faleh Backend"}