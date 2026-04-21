"""Shared singleton service instances used across the application.

Importing from this module guarantees that all routes and the lifespan
hook operate on the *same* BrowserService and ReportService objects,
so a report created by the analysis route can be retrieved by the
reports route.
"""
from __future__ import annotations

from app.services.analyzer_service import AnalyzerService
from app.services.browser_service import BrowserService
from app.services.report_service import ReportService

browser_service: BrowserService = BrowserService()
analyzer_service: AnalyzerService = AnalyzerService()
report_service: ReportService = ReportService()
