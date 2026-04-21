"""Entry point for the Website Analyzer API."""
import uvicorn

from app.config import settings
from app.main import app  # noqa: F401 – imported so uvicorn can resolve the app

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level="info",
    )
