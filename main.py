import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from routers import payments_router, assessments_router

# Setup logging to see errors in logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup logic
    try:
        logger.info("Starting up: Checking environment variables and connections...")
        # Verify critical env var exists
        if not os.getenv("DATABASE_URL"):
            raise ValueError("DATABASE_URL is not set!")
        # Add your database connection test here
        logger.info("Startup complete.")
    except Exception as e:
        logger.error(f"FATAL: Application startup failed: {e}")
        raise e  # This will stop the app and show you the exact error
    yield
    # Shutdown logic
    logger.info("Shutting down...")

app = FastAPI(title="Faleh Payments API", lifespan=lifespan)

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
    return {"message": "Hello World"}