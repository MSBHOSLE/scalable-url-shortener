from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.v1.endpoints.redirects import router as redirect_router
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging import logger, setup_logging
from app.db.session import init_db
from app.services.cache_service import cache_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup actions
    setup_logging()
    logger.info("Initializing Scalable URL Shortener service...")

    # Initialize Database schema
    try:
        await init_db()
        logger.info("Database initialized successfully.")
    except Exception as e:
        logger.error(f"Error initializing database: {e}")

    # Connect to Redis
    await cache_service.connect()

    yield

    # Shutdown actions
    logger.info("Shutting down Scalable URL Shortener...")
    await cache_service.disconnect()


app = FastAPI(
    title=settings.APP_NAME,
    description="High-throughput URL shortening service utilizing Base62 encoding, Read-Through caching, and click analytics.",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API v1 routes
app.include_router(api_router, prefix="/api/v1")

# Root Short URL Redirection route
app.include_router(redirect_router)


@app.get("/", tags=["Root"])
async def root():
    return {
        "service": settings.APP_NAME,
        "version": "1.0.0",
        "documentation": "/docs",
        "status": "operational",
    }
