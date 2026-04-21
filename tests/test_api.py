"""Integration tests for the FastAPI application."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_PAGE_DATA = {
    "url": "https://example.com",
    "html": """<!DOCTYPE html>
<html>
<head>
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Example</title>
</head>
<body>
  <nav><a href="/">Home</a></nav>
  <h1>Welcome – Trusted by thousands</h1>
  <p>We help you accomplish great things.</p>
  <button class="btn-primary">Get Started</button>
  <img src="img.jpg" alt="Example image">
</body>
</html>""",
    "performance": {
        "loadEventEnd": 1200,
        "domContentLoaded": 700,
        "firstPaint": 300,
        "firstContentfulPaint": 350,
        "transferSize": 204800,
    },
    "resource_count": 15,
    "page_size_bytes": 204800,
    "status_code": 200,
    "error": None,
}


@pytest.fixture()
def client() -> TestClient:
    """Return a synchronous test client (no browser startup needed)."""
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------


def test_health_check(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert "version" in data


# ---------------------------------------------------------------------------
# POST /api/analyze
# ---------------------------------------------------------------------------


class TestAnalyzeEndpoint:
    def test_analyze_success(self, client: TestClient) -> None:
        with patch(
            "app.routes.analysis._browser_service.fetch_page_data",
            new=AsyncMock(return_value=SAMPLE_PAGE_DATA),
        ):
            resp = client.post("/api/analyze", json={"url": "https://example.com"})

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert "report_id" in data
        result = data["result"]
        assert result["url"] == "https://example.com"
        assert 0 <= result["overall_score"] <= 10

    def test_analyze_invalid_url(self, client: TestClient) -> None:
        resp = client.post("/api/analyze", json={"url": "not-a-url"})
        assert resp.status_code == 422

    def test_analyze_missing_url(self, client: TestClient) -> None:
        resp = client.post("/api/analyze", json={})
        assert resp.status_code == 422

    def test_analyze_mobile_mode(self, client: TestClient) -> None:
        with patch(
            "app.routes.analysis._browser_service.fetch_page_data",
            new=AsyncMock(return_value=SAMPLE_PAGE_DATA),
        ) as mock_fetch:
            resp = client.post(
                "/api/analyze",
                json={"url": "https://example.com", "mobile": True},
            )
        assert resp.status_code == 200
        mock_fetch.assert_called_once_with(
            url="https://example.com", mobile=True, timeout=None
        )

    def test_analyze_browser_error(self, client: TestClient) -> None:
        with patch(
            "app.routes.analysis._browser_service.fetch_page_data",
            new=AsyncMock(side_effect=RuntimeError("browser crashed")),
        ):
            resp = client.post("/api/analyze", json={"url": "https://example.com"})
        assert resp.status_code == 502


# ---------------------------------------------------------------------------
# POST /api/compare
# ---------------------------------------------------------------------------


class TestCompareEndpoint:
    def test_compare_success(self, client: TestClient) -> None:
        page2 = dict(SAMPLE_PAGE_DATA, url="https://other.com")
        with patch(
            "app.routes.analysis._browser_service.fetch_page_data",
            new=AsyncMock(side_effect=[SAMPLE_PAGE_DATA, page2]),
        ):
            resp = client.post(
                "/api/compare",
                json={"url1": "https://example.com", "url2": "https://other.com"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "completed"
        assert "report_id" in data
        result = data["result"]
        assert result["url1"] == "https://example.com"
        assert result["url2"] == "https://other.com"
        assert "comparison_matrix" in result
        assert len(result["comparison_matrix"]) == 7
        assert "overall_winner" in result

    def test_compare_invalid_urls(self, client: TestClient) -> None:
        resp = client.post(
            "/api/compare",
            json={"url1": "bad-url", "url2": "also-bad"},
        )
        assert resp.status_code == 422

    def test_compare_missing_url2(self, client: TestClient) -> None:
        resp = client.post("/api/compare", json={"url1": "https://example.com"})
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/reports/{report_id}
# ---------------------------------------------------------------------------


class TestReportsEndpoint:
    def test_get_report_not_found(self, client: TestClient) -> None:
        resp = client.get("/api/reports/nonexistent-id")
        assert resp.status_code == 404

    def test_get_report_after_analyze(self, client: TestClient) -> None:
        with patch(
            "app.routes.analysis._browser_service.fetch_page_data",
            new=AsyncMock(return_value=SAMPLE_PAGE_DATA),
        ):
            analyze_resp = client.post(
                "/api/analyze", json={"url": "https://example.com"}
            )
        assert analyze_resp.status_code == 200
        report_id = analyze_resp.json()["report_id"]

        # Both routes now share the same ReportService singleton via
        # app.dependencies, so the report must be retrievable.
        get_resp = client.get(f"/api/reports/{report_id}")
        assert get_resp.status_code == 200
        assert get_resp.json()["report_id"] == report_id


# ---------------------------------------------------------------------------
# GET /api/history
# ---------------------------------------------------------------------------


class TestHistoryEndpoint:
    def test_history_returns_list(self, client: TestClient) -> None:
        resp = client.get("/api/history")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_history_invalid_limit(self, client: TestClient) -> None:
        resp = client.get("/api/history?limit=0")
        assert resp.status_code == 422

    def test_history_limit_too_large(self, client: TestClient) -> None:
        resp = client.get("/api/history?limit=200")
        assert resp.status_code == 422
