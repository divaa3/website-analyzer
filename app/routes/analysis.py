from __future__ import annotations

from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, status

from app.dependencies import analyzer_service as _analyzer_service
from app.dependencies import browser_service as _browser_service
from app.dependencies import report_service as _report_service
from app.models.analysis import (
    AnalysisRequest,
    AnalysisResponse,
    CompareRequest,
    ComparisonResponse,
    ComparisonResult,
)
from app.services.analyzer_service import AnalyzerService
from app.services.browser_service import BrowserService
from app.services.report_service import ReportService
from app.utils.logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api", tags=["analysis"])


def get_browser() -> BrowserService:
    return _browser_service


def get_analyzer() -> AnalyzerService:
    return _analyzer_service


def get_report() -> ReportService:
    return _report_service


@router.post(
    "/analyze",
    response_model=AnalysisResponse,
    status_code=status.HTTP_200_OK,
    summary="Analyze a single website",
)
async def analyze_website(
    request: AnalysisRequest,
    browser: BrowserService = Depends(get_browser),
    analyzer: AnalyzerService = Depends(get_analyzer),
    report: ReportService = Depends(get_report),
) -> AnalysisResponse:
    """
    Perform a comprehensive UX/CX analysis of a single website.

    Returns a detailed report covering navigation, performance,
    accessibility, mobile UX, content quality, and CTA effectiveness.
    """
    logger.info("Analyze request: url=%s mobile=%s", request.url, request.mobile)

    try:
        page_data = await browser.fetch_page_data(
            url=request.url,
            mobile=request.mobile,
            timeout=request.timeout,
        )
    except Exception as exc:
        logger.error("Browser error for %s: %s", request.url, exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch the page: {exc}",
        ) from exc

    if page_data.get("error"):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch the page: {page_data['error']}",
        )

    result = analyzer.analyze(page_data)
    response = report.create_analysis_report(result)
    return response


@router.post(
    "/compare",
    response_model=ComparisonResponse,
    status_code=status.HTTP_200_OK,
    summary="Compare two websites",
)
async def compare_websites(
    request: CompareRequest,
    browser: BrowserService = Depends(get_browser),
    analyzer: AnalyzerService = Depends(get_analyzer),
    report: ReportService = Depends(get_report),
) -> ComparisonResponse:
    """
    Perform a side-by-side UX/CX comparison of two websites.

    Returns a comparison matrix highlighting the stronger performer
    across all evaluation dimensions.
    """
    logger.info("Compare request: url1=%s url2=%s", request.url1, request.url2)

    errors: Dict[str, str] = {}

    try:
        page_data1 = await browser.fetch_page_data(
            url=request.url1,
            mobile=request.mobile,
            timeout=request.timeout,
        )
    except Exception as exc:
        logger.error("Browser error for %s: %s", request.url1, exc)
        errors["url1"] = str(exc)
        page_data1 = {"url": request.url1, "html": "", "performance": {}, "resource_count": 0, "page_size_bytes": 0}

    try:
        page_data2 = await browser.fetch_page_data(
            url=request.url2,
            mobile=request.mobile,
            timeout=request.timeout,
        )
    except Exception as exc:
        logger.error("Browser error for %s: %s", request.url2, exc)
        errors["url2"] = str(exc)
        page_data2 = {"url": request.url2, "html": "", "performance": {}, "resource_count": 0, "page_size_bytes": 0}

    if errors:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Failed to fetch pages: {errors}",
        )

    result1 = analyzer.analyze(page_data1)
    result2 = analyzer.analyze(page_data2)

    matrix = ReportService.build_comparison_matrix(result1, result2)
    winner, summary = ReportService.build_summary(result1, result2)

    comparison = ComparisonResult(
        url1=request.url1,
        url2=request.url2,
        site1=result1,
        site2=result2,
        comparison_matrix=matrix,
        overall_winner=winner,
        summary=summary,
    )
    response = report.create_comparison_report(comparison)
    return response
