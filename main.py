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


import traceback # Add this import at the top

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        # ... your startup code ...
        logger.info("Startup complete.")
    except Exception as e:
        # This will output the full technical trace of the crash
        logger.error("FATAL: Application startup failed!")
        logger.error(traceback.format_exc())
        raise e
    yield
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