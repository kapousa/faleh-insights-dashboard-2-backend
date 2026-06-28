from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from routers import (
  payments_router)

app = FastAPI(title="Faleh Payments API")

# CORS Middleware should typically be after authentication if you want auth to apply to CORS pre-flight
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # WARNING: For production, narrow this down to specific frontend domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Include Routers ---
app.include_router(payments_router)

@app.get("/")
def read_root():
    return {"message": "Hello World"}
