# app/main.py
from fastapi import FastAPI
from contextlib import asynccontextmanager
from app.api.v1.router import router as v1_router
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware
from app.config.config import settings # Import settings

@asynccontextmanager
async def lifespan(app: FastAPI):
    print("🚀 Running migrations before starting server...")
    # run_migrations_sync()  # ✅ await async migration
    print("✅ Migrations done, server starting...")
    yield  # hand over control to FastAPI
    print("🛑 Server shutting down...")


# Create the FastAPI application instance with the lifespan manager
app = FastAPI(
    title="MyApp API",
    lifespan=lifespan, # Attach the lifespan context manager,
    # docs_url=None
)

# Add Session Middleware (needed for auth)
# MAKE SURE to set a strong, random SECRET_KEY in your .env file
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.SECRET_KEY
)

# Enable CORS for all origins and all routes
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],       # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],       # Allow all methods (GET, POST, etc)
    allow_headers=["*"],       # Allow all headers
)

# Include the main API router into the main application
app.include_router(v1_router, prefix="/api/v1")

@app.get("/", tags=["Root"])
async def read_root():
    return {"message": "Welcome to MyApp API!"}