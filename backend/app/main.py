"""FastAPI application entry point."""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.db.database import init_db, close_db
from app.api.routes import router
from app.workers.job_runner import job_runner
from app.workers.handlers import (
    handle_download,
    handle_analyze,
    handle_thumbnail,
    handle_export,
    handle_export_batch,
    handle_publish,
    handle_upload,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.debug else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    logger.info("Starting AutoClip...")
    
    # Initialize database
    await init_db()
    logger.info("Database initialized")
    
    # Register job handlers
    job_runner.register_handler("download", handle_download)
    job_runner.register_handler("analyze", handle_analyze)
    job_runner.register_handler("thumbnail", handle_thumbnail)
    job_runner.register_handler("export", handle_export)
    job_runner.register_handler("export_batch", handle_export_batch)
    job_runner.register_handler("publish", handle_publish)
    job_runner.register_handler("upload", handle_upload)
    logger.info("Job handlers registered")
    
    yield
    
    # Shutdown
    logger.info("Shutting down AutoClip...")
    await job_runner.shutdown()
    await close_db()
    logger.info("Shutdown complete")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="Local video clip extraction and editing tool",
    version="1.0.0",
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        settings.frontend_url,
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include API routes
app.include_router(router, prefix="/api")

# Serve frontend in production mode
if settings.serve_frontend:
    if settings.frontend_build_dir.exists():
        app.mount("/", StaticFiles(directory=str(settings.frontend_build_dir), html=True), name="frontend")
        logger.info(f"Serving frontend from {settings.frontend_build_dir}")


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "app": settings.app_name,
        "version": "1.0.0",
        "api": "/api",
        "docs": "/docs"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.debug
    )

