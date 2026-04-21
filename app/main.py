from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.dependencies import browser_service as _browser
from app.routes.analysis import router as analysis_router
from app.routes.reports import router as reports_router
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Singleton browser service shared across route handlers (imported from
# dependencies so that routes share the same instance)

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Start / stop the Playwright browser alongside the application."""
    try:
        await _browser.start()
        logger.info("Application startup complete.")
    except Exception as exc:
        logger.warning("Could not start browser (Playwright may not be installed): %s", exc)
    yield
    await _browser.stop()
    logger.info("Application shutdown complete.")


def create_app() -> FastAPI:
    """Factory function that creates and configures the FastAPI application."""
    app = FastAPI(
        title=settings.APP_NAME,
        version=settings.APP_VERSION,
        description=settings.APP_DESCRIPTION,
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.ALLOWED_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers
    app.include_router(analysis_router)
    app.include_router(reports_router)

    @app.get("/health", tags=["health"], summary="Health check")
    async def health() -> JSONResponse:
        return JSONResponse({"status": "ok", "version": settings.APP_VERSION})

    return app


app = create_app()
