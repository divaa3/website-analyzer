"""Unit tests for AnalyzerService."""
from __future__ import annotations

import pytest

from app.services.analyzer_service import AnalyzerService

SAMPLE_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Sample Page</title>
</head>
<body>
  <a class="skip-link" href="#main">Skip to main content</a>
  <nav>
    <a href="/">Home</a>
    <a href="/about">About</a>
    <a href="/contact">Contact</a>
  </nav>
  <main id="main">
    <h1>Welcome to Sample Site</h1>
    <p>We help you do amazing things. Trusted by thousands of customers.</p>
    <p>Lorem ipsum dolor sit amet, consectetur adipiscing elit. Sed do eiusmod
    tempor incididunt ut labore et dolore magna aliqua.</p>
    <button class="btn-primary">Get Started</button>
    <form>
      <input type="text" name="name" required placeholder="Your name">
      <input type="email" name="email" required placeholder="Email">
      <button type="submit">Subscribe</button>
    </form>
    <img src="hero.jpg" alt="Hero image">
    <img src="logo.png" alt="Company logo">
  </main>
</body>
</html>"""

MINIMAL_HTML = "<html><body><p>Hello</p></body></html>"

EMPTY_PAGE_DATA = {
    "url": "https://example.com",
    "html": MINIMAL_HTML,
    "performance": {},
    "resource_count": 0,
    "page_size_bytes": 0,
}

RICH_PAGE_DATA = {
    "url": "https://sample.com",
    "html": SAMPLE_HTML,
    "performance": {
        "loadEventEnd": 1500,
        "domContentLoaded": 800,
        "firstPaint": 400,
        "firstContentfulPaint": 450,
        "transferSize": 512000,
    },
    "resource_count": 30,
    "page_size_bytes": 512000,
}


@pytest.fixture()
def analyzer() -> AnalyzerService:
    return AnalyzerService()


class TestNavigationAnalysis:
    def test_no_nav_element(self, analyzer: AnalyzerService) -> None:
        result = analyzer.analyze(EMPTY_PAGE_DATA)
        assert not result.navigation.has_main_nav
        assert result.navigation.score < 10.0
        assert len(result.navigation.issues) > 0

    def test_has_nav_element(self, analyzer: AnalyzerService) -> None:
        result = analyzer.analyze(RICH_PAGE_DATA)
        assert result.navigation.has_main_nav
        assert result.navigation.link_count >= 3


class TestFormsAnalysis:
    def test_no_forms(self, analyzer: AnalyzerService) -> None:
        result = analyzer.analyze(EMPTY_PAGE_DATA)
        assert result.forms.form_count == 0
        assert result.forms.score == 10.0  # nothing to penalise

    def test_form_with_validation(self, analyzer: AnalyzerService) -> None:
        result = analyzer.analyze(RICH_PAGE_DATA)
        assert result.forms.form_count == 1
        assert result.forms.has_validation


class TestPerformanceAnalysis:
    def test_fast_page(self, analyzer: AnalyzerService) -> None:
        result = analyzer.analyze(RICH_PAGE_DATA)
        # 1500 ms is under GOOD_LOAD_TIME_MS (2000 ms) so no load-time issue
        assert result.performance.load_time_ms == 1500.0

    def test_slow_page(self, analyzer: AnalyzerService) -> None:
        data = dict(RICH_PAGE_DATA)
        data["performance"] = {"loadEventEnd": 5000}
        result = analyzer.analyze(data)
        assert result.performance.score < 10.0
        assert any("slow" in i.lower() for i in result.performance.issues)


class TestAccessibilityAnalysis:
    def test_missing_alt_text(self, analyzer: AnalyzerService) -> None:
        html = '<html><body><img src="img.jpg"><h1>Title</h1></body></html>'
        result = analyzer.analyze({"url": "https://x.com", "html": html, "performance": {}, "resource_count": 0, "page_size_bytes": 0})
        assert result.accessibility.images_without_alt == 1
        assert result.accessibility.score < 10.0

    def test_all_images_have_alt(self, analyzer: AnalyzerService) -> None:
        result = analyzer.analyze(RICH_PAGE_DATA)
        assert result.accessibility.images_without_alt == 0

    def test_skip_link_detected(self, analyzer: AnalyzerService) -> None:
        result = analyzer.analyze(RICH_PAGE_DATA)
        assert result.accessibility.has_skip_links

    def test_heading_structure_valid(self, analyzer: AnalyzerService) -> None:
        result = analyzer.analyze(RICH_PAGE_DATA)
        assert result.accessibility.heading_structure_valid


class TestMobileUXAnalysis:
    def test_viewport_meta_present(self, analyzer: AnalyzerService) -> None:
        result = analyzer.analyze(RICH_PAGE_DATA)
        assert result.mobile_ux.has_viewport_meta

    def test_missing_viewport_meta(self, analyzer: AnalyzerService) -> None:
        result = analyzer.analyze(EMPTY_PAGE_DATA)
        assert not result.mobile_ux.has_viewport_meta
        assert result.mobile_ux.score < 10.0


class TestContentAnalysis:
    def test_sparse_content(self, analyzer: AnalyzerService) -> None:
        result = analyzer.analyze(EMPTY_PAGE_DATA)
        assert result.content.word_count < 200
        assert any("text content" in i.lower() for i in result.content.issues)

    def test_rich_content(self, analyzer: AnalyzerService) -> None:
        result = analyzer.analyze(RICH_PAGE_DATA)
        assert result.content.heading_count >= 1
        assert result.content.has_clear_value_proposition


class TestCTAAnalysis:
    def test_no_cta(self, analyzer: AnalyzerService) -> None:
        result = analyzer.analyze(EMPTY_PAGE_DATA)
        assert not result.cta.has_primary_cta
        assert result.cta.score < 10.0

    def test_cta_present(self, analyzer: AnalyzerService) -> None:
        result = analyzer.analyze(RICH_PAGE_DATA)
        assert result.cta.has_primary_cta
        assert result.cta.cta_count > 0


class TestOverallScore:
    def test_overall_score_in_range(self, analyzer: AnalyzerService) -> None:
        result = analyzer.analyze(RICH_PAGE_DATA)
        assert 0.0 <= result.overall_score <= 10.0

    def test_top_issues_populated(self, analyzer: AnalyzerService) -> None:
        result = analyzer.analyze(EMPTY_PAGE_DATA)
        # Minimal page should surface several issues
        assert len(result.top_issues) > 0
