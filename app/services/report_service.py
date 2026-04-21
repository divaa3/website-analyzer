from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from app.config import settings
from app.models.analysis import (
    AnalysisResponse,
    AnalysisResult,
    AnalysisStatus,
    ComparisonMatrix,
    ComparisonResponse,
    ComparisonResult,
)
from app.utils.logger import get_logger

logger = get_logger(__name__)


class ReportService:
    """Handles report persistence and retrieval."""

    def __init__(self, reports_dir: Optional[str] = None) -> None:
        self._reports_dir = reports_dir or settings.REPORTS_DIR
        os.makedirs(self._reports_dir, exist_ok=True)
        # In-memory store for fast lookups (report_id -> dict)
        self._store: Dict[str, Dict[str, Any]] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create_analysis_report(self, result: AnalysisResult) -> AnalysisResponse:
        """Persist an analysis result and return the response envelope."""
        report_id = str(uuid.uuid4())
        response = AnalysisResponse(
            report_id=report_id,
            status=AnalysisStatus.COMPLETED,
            result=result,
        )
        self._save(report_id, response.model_dump(mode="json"))
        return response

    def create_comparison_report(self, result: ComparisonResult) -> ComparisonResponse:
        """Persist a comparison result and return the response envelope."""
        report_id = str(uuid.uuid4())
        response = ComparisonResponse(
            report_id=report_id,
            status=AnalysisStatus.COMPLETED,
            result=result,
        )
        self._save(report_id, response.model_dump(mode="json"))
        return response

    def get_report(self, report_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve a report by ID (returns None if not found)."""
        if report_id in self._store:
            return self._store[report_id]
        return self._load(report_id)

    def get_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return the most recent *limit* report summaries."""
        summaries: List[Dict[str, Any]] = []
        for report_id, data in list(self._store.items())[-limit:]:
            summaries.append(
                {
                    "report_id": report_id,
                    "status": data.get("status"),
                    "created_at": data.get("created_at"),
                    "url": (data.get("result") or {}).get("url")
                    or (data.get("result") or {}).get("url1"),
                }
            )
        return list(reversed(summaries))

    # ------------------------------------------------------------------
    # Comparison helper
    # ------------------------------------------------------------------

    @staticmethod
    def build_comparison_matrix(
        site1: AnalysisResult, site2: AnalysisResult
    ) -> List[ComparisonMatrix]:
        categories = [
            ("Navigation", site1.navigation.score, site2.navigation.score),
            ("Forms", site1.forms.score, site2.forms.score),
            ("Performance", site1.performance.score, site2.performance.score),
            ("Accessibility", site1.accessibility.score, site2.accessibility.score),
            ("Mobile UX", site1.mobile_ux.score, site2.mobile_ux.score),
            ("Content", site1.content.score, site2.content.score),
            ("CTA", site1.cta.score, site2.cta.score),
        ]

        matrix: List[ComparisonMatrix] = []
        for category, s1, s2 in categories:
            diff = round(s1 - s2, 2)
            if diff > 0:
                winner = site1.url
            elif diff < 0:
                winner = site2.url
            else:
                winner = "tie"
            matrix.append(
                ComparisonMatrix(
                    category=category,
                    site1_score=s1,
                    site2_score=s2,
                    winner=winner,
                    difference=abs(diff),
                )
            )
        return matrix

    @staticmethod
    def build_summary(site1: AnalysisResult, site2: AnalysisResult) -> Tuple[str, str]:
        """Return (overall_winner, summary_text)."""
        if site1.overall_score > site2.overall_score:
            winner = site1.url
        elif site2.overall_score > site1.overall_score:
            winner = site2.url
        else:
            winner = "tie"

        summary = (
            f"{site1.url} scored {site1.overall_score}/10 overall. "
            f"{site2.url} scored {site2.overall_score}/10 overall. "
            f"{'Neither site outperforms the other.' if winner == 'tie' else f'{winner} is the stronger performer.'}"
        )
        return winner, summary

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _sanitize_report_id(report_id: str) -> str:
        """Return the report_id only if it is a valid UUID string.

        Raises ValueError for invalid/unsafe values to prevent path traversal.
        """
        try:
            return str(uuid.UUID(report_id))
        except ValueError as exc:
            raise ValueError(f"Invalid report ID: {report_id!r}") from exc

    def _save(self, report_id: str, data: Dict[str, Any]) -> None:
        self._store[report_id] = data
        safe_id = self._sanitize_report_id(report_id)
        path = os.path.join(self._reports_dir, f"{safe_id}.json")
        try:
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, default=str)
            logger.info("Report saved: %s", path)
        except OSError as exc:
            logger.warning("Could not persist report to disk: %s", exc)

    def _load(self, report_id: str) -> Optional[Dict[str, Any]]:
        try:
            safe_id = self._sanitize_report_id(report_id)
        except ValueError:
            return None
        path = os.path.join(self._reports_dir, f"{safe_id}.json")
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            self._store[report_id] = data
            return data
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not load report %s: %s", report_id, exc)
            return None
