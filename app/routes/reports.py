from __future__ import annotations

from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, status

from app.services.report_service import ReportService
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["reports"])

_report_service: ReportService = ReportService()


@router.get(
    "/reports/{report_id}",
    response_model=Dict[str, Any],
    summary="Get a report by ID",
)
async def get_report(report_id: str) -> Dict[str, Any]:
    """Retrieve a previously generated analysis or comparison report."""
    report = _report_service.get_report(report_id)
    if report is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Report '{report_id}' not found.",
        )
    return report


@router.get(
    "/history",
    response_model=List[Dict[str, Any]],
    summary="List recent analysis history",
)
async def get_history(limit: int = 20) -> List[Dict[str, Any]]:
    """Return the most recent analysis reports (newest first)."""
    if limit < 1 or limit > 100:
        raise HTTPException(
            status_code=422,
            detail="'limit' must be between 1 and 100.",
        )
    return _report_service.get_history(limit=limit)
