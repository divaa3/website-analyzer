from __future__ import annotations

import re
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional, Tuple

from app.config import settings
from app.models.analysis import (
    AccessibilityAnalysis,
    AnalysisResult,
    ContentAnalysis,
    CTAAnalysis,
    FormsAnalysis,
    MobileUXAnalysis,
    NavigationAnalysis,
    PerformanceAnalysis,
)
from app.utils.logger import get_logger
from app.utils.metrics import MetricsCollector

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Minimal HTML parsing helpers
# ---------------------------------------------------------------------------


class _TagCounter(HTMLParser):
    """Lightweight HTML parser that counts tags and extracts attributes."""

    def __init__(self) -> None:
        super().__init__()
        self.tags: Dict[str, int] = {}
        self.attrs_by_tag: Dict[str, List[Dict[str, Optional[str]]]] = {}

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        tag = tag.lower()
        self.tags[tag] = self.tags.get(tag, 0) + 1
        self.attrs_by_tag.setdefault(tag, []).append(dict(attrs))

    def count(self, tag: str) -> int:
        return self.tags.get(tag.lower(), 0)

    def attrs_for(self, tag: str) -> List[Dict[str, Optional[str]]]:
        return self.attrs_by_tag.get(tag.lower(), [])


def _parse_html(html: str) -> _TagCounter:
    parser = _TagCounter()
    try:
        parser.feed(html)
    except Exception:
        pass
    return parser


def _has_attr_value(attrs: List[Dict[str, Optional[str]]], key: str, value: str) -> bool:
    return any(value.lower() in (a.get(key) or "").lower() for a in attrs)


class _TextExtractor(HTMLParser):
    """Extracts visible text nodes from HTML."""

    # Tags whose contents should be ignored entirely
    _SKIP_TAGS = frozenset({"script", "style", "head", "noscript", "template"})

    def __init__(self) -> None:
        super().__init__()
        self._parts: List[str] = []
        self._skip_depth: int = 0

    def handle_starttag(self, tag: str, attrs: List[Tuple[str, Optional[str]]]) -> None:
        if tag.lower() in self._SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self._SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            stripped = data.strip()
            if stripped:
                self._parts.append(stripped)

    def get_text(self) -> str:
        return " ".join(self._parts)


def _extract_text(html: str) -> str:
    """Return visible text content from *html* without using regex on tags."""
    extractor = _TextExtractor()
    try:
        extractor.feed(html)
    except Exception:
        pass
    return extractor.get_text()


# ---------------------------------------------------------------------------
# Analyzer service
# ---------------------------------------------------------------------------


class AnalyzerService:
    """Evaluates raw page data and produces structured analysis results."""

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def analyze(self, page_data: Dict[str, Any]) -> AnalysisResult:
        """Run all analysis passes on *page_data* and return an AnalysisResult."""
        metrics = MetricsCollector()
        html: str = page_data.get("html", "")
        url: str = page_data.get("url", "")
        perf_raw: Dict[str, Any] = page_data.get("performance", {})
        resource_count: int = page_data.get("resource_count", 0)
        page_size_bytes: int = page_data.get("page_size_bytes", 0)

        with metrics.timer("parse_html"):
            parsed = _parse_html(html)

        with metrics.timer("navigation"):
            navigation = self._analyze_navigation(parsed, html)
        with metrics.timer("forms"):
            forms = self._analyze_forms(parsed)
        with metrics.timer("performance"):
            performance = self._analyze_performance(perf_raw, resource_count, page_size_bytes)
        with metrics.timer("accessibility"):
            accessibility = self._analyze_accessibility(parsed)
        with metrics.timer("mobile_ux"):
            mobile_ux = self._analyze_mobile(parsed, html)
        with metrics.timer("content"):
            content = self._analyze_content(parsed, html)
        with metrics.timer("cta"):
            cta = self._analyze_cta(parsed, html)

        overall = self._compute_overall_score(
            navigation, forms, performance, accessibility, mobile_ux, content, cta
        )

        top_issues = self._top_items(
            [navigation.issues, forms.issues, performance.issues,
             accessibility.issues, mobile_ux.issues, content.issues, cta.issues]
        )
        top_recs = self._top_items(
            [navigation.recommendations, forms.recommendations, performance.recommendations,
             accessibility.recommendations, mobile_ux.recommendations,
             content.recommendations, cta.recommendations]
        )

        logger.debug("Analysis metrics for %s: %s", url, metrics.all())

        return AnalysisResult(
            url=url,
            overall_score=overall,
            navigation=navigation,
            forms=forms,
            performance=performance,
            accessibility=accessibility,
            mobile_ux=mobile_ux,
            content=content,
            cta=cta,
            top_issues=top_issues,
            top_recommendations=top_recs,
        )

    # ------------------------------------------------------------------
    # Navigation
    # ------------------------------------------------------------------

    def _analyze_navigation(self, parsed: _TagCounter, html: str) -> NavigationAnalysis:
        issues: List[str] = []
        recs: List[str] = []

        nav_count = parsed.count("nav")
        has_main_nav = nav_count > 0
        has_breadcrumbs = bool(
            re.search(r'breadcrumb', html, re.IGNORECASE)
        )
        has_search = bool(
            re.search(r'type=["\']search["\']|role=["\']search["\']', html, re.IGNORECASE)
        )
        link_count = parsed.count("a")

        if not has_main_nav:
            issues.append("No semantic <nav> element found.")
            recs.append("Add a <nav> element to improve navigation semantics.")
        if not has_breadcrumbs:
            issues.append("No breadcrumb navigation detected.")
            recs.append("Consider adding breadcrumbs to improve wayfinding.")
        if not has_search:
            issues.append("No search functionality detected.")
            recs.append("Add site search to improve content discoverability.")
        if link_count > 100:
            issues.append(f"Too many links on the page ({link_count}).")
            recs.append("Reduce link count to simplify navigation.")

        score = 10.0
        score -= len(issues) * 1.5
        score = max(0.0, min(10.0, score))

        return NavigationAnalysis(
            score=round(score, 1),
            has_main_nav=has_main_nav,
            has_breadcrumbs=has_breadcrumbs,
            has_search=has_search,
            link_count=link_count,
            issues=issues,
            recommendations=recs,
        )

    # ------------------------------------------------------------------
    # Forms
    # ------------------------------------------------------------------

    def _analyze_forms(self, parsed: _TagCounter) -> FormsAnalysis:
        issues: List[str] = []
        recs: List[str] = []

        form_count = parsed.count("form")
        input_count = parsed.count("input") + parsed.count("textarea") + parsed.count("select")
        avg_fields = round(input_count / form_count, 1) if form_count else 0.0

        input_attrs = parsed.attrs_for("input")
        has_required = any("required" in a for a in input_attrs)
        has_pattern = any(a.get("pattern") for a in input_attrs)
        has_validation = has_required or has_pattern

        # Heuristic: look for error-class patterns in attributes
        all_classes = " ".join(
            (a.get("class") or "") for tag in ("div", "span", "p")
            for a in parsed.attrs_for(tag)
        )
        has_error_messages = bool(re.search(r'error|invalid|alert', all_classes, re.IGNORECASE))

        if form_count == 0:
            pass  # No forms – nothing to flag
        else:
            if avg_fields > 10:
                issues.append(f"Forms have high average field count ({avg_fields}).")
                recs.append("Reduce form fields to decrease abandonment rate.")
            if not has_validation:
                issues.append("Forms appear to lack client-side validation.")
                recs.append("Add required attributes and pattern validation to form fields.")
            if not has_error_messages:
                issues.append("No visible error message containers detected.")
                recs.append("Provide clear, inline error messages for invalid fields.")

        score = 10.0
        score -= len(issues) * 2.0
        score = max(0.0, min(10.0, score))

        return FormsAnalysis(
            score=round(score, 1),
            form_count=form_count,
            avg_field_count=avg_fields,
            has_validation=has_validation,
            has_error_messages=has_error_messages,
            issues=issues,
            recommendations=recs,
        )

    # ------------------------------------------------------------------
    # Performance
    # ------------------------------------------------------------------

    def _analyze_performance(
        self,
        perf_raw: Dict[str, Any],
        resource_count: int,
        page_size_bytes: int,
    ) -> PerformanceAnalysis:
        issues: List[str] = []
        recs: List[str] = []

        load_time = float(perf_raw.get("loadEventEnd", 0))
        dom_loaded = float(perf_raw.get("domContentLoaded", 0))
        first_paint = float(perf_raw.get("firstPaint", 0))
        page_size_kb = page_size_bytes / 1024

        if load_time > settings.ACCEPTABLE_LOAD_TIME_MS:
            issues.append(f"Page load time is slow ({load_time:.0f} ms).")
            recs.append("Optimise assets, enable caching, and consider a CDN.")
        elif load_time > settings.GOOD_LOAD_TIME_MS:
            issues.append(f"Page load time is acceptable but could be improved ({load_time:.0f} ms).")
            recs.append("Profile and eliminate render-blocking resources.")

        if resource_count > 80:
            issues.append(f"High number of HTTP requests ({resource_count}).")
            recs.append("Bundle and minimise static assets.")

        if page_size_kb > 3000:
            issues.append(f"Page size is large ({page_size_kb:.0f} KB).")
            recs.append("Compress images and enable Gzip/Brotli compression.")

        score = 10.0
        score -= len(issues) * 1.5
        score = max(0.0, min(10.0, score))

        return PerformanceAnalysis(
            score=round(score, 1),
            load_time_ms=load_time,
            dom_content_loaded_ms=dom_loaded,
            first_paint_ms=first_paint,
            resource_count=resource_count,
            page_size_kb=round(page_size_kb, 2),
            issues=issues,
            recommendations=recs,
        )

    # ------------------------------------------------------------------
    # Accessibility
    # ------------------------------------------------------------------

    def _analyze_accessibility(self, parsed: _TagCounter) -> AccessibilityAnalysis:
        issues: List[str] = []
        recs: List[str] = []

        # Images
        img_attrs = parsed.attrs_for("img")
        images_with_alt = sum(1 for a in img_attrs if a.get("alt") is not None)
        images_without_alt = len(img_attrs) - images_with_alt

        # Skip links
        anchor_attrs = parsed.attrs_for("a")
        has_skip_links = _has_attr_value(anchor_attrs, "href", "#main") or _has_attr_value(
            anchor_attrs, "class", "skip"
        )

        # Heading structure: h1 should exist
        heading_structure_valid = parsed.count("h1") == 1

        # ARIA labels
        aria_count = sum(
            1 for tag in ("button", "input", "a", "div", "span")
            for a in parsed.attrs_for(tag)
            if a.get("aria-label") or a.get("aria-labelledby")
        )

        if images_without_alt:
            issues.append(f"{images_without_alt} image(s) missing alt text.")
            recs.append("Add descriptive alt text to all images.")
        if not has_skip_links:
            issues.append("No skip navigation link detected.")
            recs.append("Add a 'Skip to main content' link for keyboard users.")
        if not heading_structure_valid:
            issues.append("H1 heading count is not exactly 1.")
            recs.append("Ensure each page has exactly one <h1> element.")

        score = 10.0
        score -= images_without_alt * 0.5
        score -= 1.0 if not has_skip_links else 0
        score -= 1.0 if not heading_structure_valid else 0
        score = max(0.0, min(10.0, score))

        return AccessibilityAnalysis(
            score=round(score, 1),
            has_skip_links=has_skip_links,
            images_with_alt=images_with_alt,
            images_without_alt=images_without_alt,
            heading_structure_valid=heading_structure_valid,
            aria_labels_count=aria_count,
            issues=issues,
            recommendations=recs,
        )

    # ------------------------------------------------------------------
    # Mobile UX
    # ------------------------------------------------------------------

    def _analyze_mobile(self, parsed: _TagCounter, html: str) -> MobileUXAnalysis:
        issues: List[str] = []
        recs: List[str] = []

        meta_attrs = parsed.attrs_for("meta")
        has_viewport = _has_attr_value(meta_attrs, "name", "viewport")

        # Heuristic: check for responsive class patterns
        is_responsive = bool(re.search(r'@media|viewport|responsive|container-fluid', html, re.IGNORECASE))

        # Check for tiny font sizes in inline styles (below 16px)
        tiny_fonts = [
            int(m) for m in re.findall(r'font-size\s*:\s*([0-9]+)px', html) if int(m) < 16
        ]
        font_size_adequate = len(tiny_fonts) == 0

        # Touch target: check buttons/links without a discernible size class
        touch_targets_adequate = parsed.count("button") + parsed.count("a") > 0

        if not has_viewport:
            issues.append("Missing viewport meta tag.")
            recs.append("Add <meta name='viewport' content='width=device-width, initial-scale=1'>.")
        if not is_responsive:
            issues.append("Page may not be fully responsive.")
            recs.append("Use CSS media queries to create a responsive layout.")
        if not font_size_adequate:
            issues.append("Possible tiny font sizes detected via inline styles.")
            recs.append("Ensure base font size is at least 16px on mobile.")

        score = 10.0
        score -= len(issues) * 2.0
        score = max(0.0, min(10.0, score))

        return MobileUXAnalysis(
            score=round(score, 1),
            has_viewport_meta=has_viewport,
            is_responsive=is_responsive,
            touch_targets_adequate=touch_targets_adequate,
            font_size_adequate=font_size_adequate,
            issues=issues,
            recommendations=recs,
        )

    # ------------------------------------------------------------------
    # Content
    # ------------------------------------------------------------------

    def _analyze_content(self, parsed: _TagCounter, html: str) -> ContentAnalysis:
        issues: List[str] = []
        recs: List[str] = []

        # Extract plain text using the HTMLParser to avoid regex ReDoS
        text = _extract_text(html)
        words = text.split()
        word_count = len(words)

        heading_count = sum(parsed.count(f"h{i}") for i in range(1, 7))
        paragraph_count = parsed.count("p")

        # Rudimentary readability: average sentence length
        sentences = re.split(r'[.!?]', text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 0]
        avg_sentence_len = (
            sum(len(s.split()) for s in sentences) / len(sentences) if sentences else 0
        )
        readability_score = max(0.0, min(10.0, 10.0 - (avg_sentence_len - 15) * 0.2))

        # Value proposition heuristic
        has_vp = bool(
            re.search(r'\b(we help|our mission|trusted by|#1|best|leading)\b', html, re.IGNORECASE)
        )

        if word_count < 200:
            issues.append("Very little text content detected.")
            recs.append("Provide meaningful content to help users understand the offering.")
        if heading_count == 0:
            issues.append("No headings found – poor content hierarchy.")
            recs.append("Use headings (H1–H6) to create a clear content structure.")
        if not has_vp:
            issues.append("No clear value proposition detected.")
            recs.append("Add a prominent headline that explains what you offer.")

        score = 10.0
        score -= len(issues) * 1.5
        score = max(0.0, min(10.0, score))

        return ContentAnalysis(
            score=round(score, 1),
            word_count=word_count,
            heading_count=heading_count,
            paragraph_count=paragraph_count,
            has_clear_value_proposition=has_vp,
            readability_score=round(readability_score, 1),
            issues=issues,
            recommendations=recs,
        )

    # ------------------------------------------------------------------
    # CTA
    # ------------------------------------------------------------------

    def _analyze_cta(self, parsed: _TagCounter, html: str) -> CTAAnalysis:
        issues: List[str] = []
        recs: List[str] = []

        button_attrs = parsed.attrs_for("button")
        anchor_attrs = parsed.attrs_for("a")

        # Identify CTAs by common text patterns
        cta_patterns = re.compile(
            r'\b(buy|shop|get started|sign up|try|book|order|subscribe|download|contact|learn more)\b',
            re.IGNORECASE,
        )
        cta_count = len(cta_patterns.findall(html))

        # Also count buttons and links whose class/aria-label indicates a CTA
        cta_button_count = sum(
            1 for btn in button_attrs
            if cta_patterns.search(btn.get("class") or "")
            or cta_patterns.search(btn.get("aria-label") or "")
        )
        cta_link_count = sum(
            1 for anchor in anchor_attrs
            if cta_patterns.search(anchor.get("class") or "")
            or cta_patterns.search(anchor.get("aria-label") or "")
        )
        cta_count = max(cta_count, cta_button_count + cta_link_count)
        has_primary_cta = cta_count > 0

        # Heuristic: CTAs above fold usually appear early in the HTML
        first_2000 = html[:2000]
        above_fold_ctas = len(cta_patterns.findall(first_2000))

        # Visibility score based on presence of prominent button styling hints
        has_prominent_style = bool(
            re.search(r'btn-primary|cta|call-to-action|hero', html, re.IGNORECASE)
        ) or cta_button_count > 0
        visibility_score = 8.0 if has_prominent_style else 5.0

        if not has_primary_cta:
            issues.append("No clear call-to-action detected.")
            recs.append("Add prominent CTAs (e.g., 'Get Started', 'Buy Now').")
        if above_fold_ctas == 0 and has_primary_cta:
            issues.append("CTA may not be visible above the fold.")
            recs.append("Place at least one CTA in the hero/above-fold section.")
        if not has_prominent_style:
            issues.append("CTA buttons may lack visual prominence.")
            recs.append("Use high-contrast button styles to make CTAs stand out.")

        score = 10.0
        score -= len(issues) * 2.0
        score = max(0.0, min(10.0, score))

        return CTAAnalysis(
            score=round(score, 1),
            cta_count=cta_count,
            above_fold_ctas=above_fold_ctas,
            has_primary_cta=has_primary_cta,
            cta_visibility_score=visibility_score,
            issues=issues,
            recommendations=recs,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _compute_overall_score(
        self,
        navigation: NavigationAnalysis,
        forms: FormsAnalysis,
        performance: PerformanceAnalysis,
        accessibility: AccessibilityAnalysis,
        mobile_ux: MobileUXAnalysis,
        content: ContentAnalysis,
        cta: CTAAnalysis,
    ) -> float:
        w = settings.SCORE_WEIGHTS
        weighted = (
            navigation.score * w["navigation"]
            + forms.score * w["forms"]
            + performance.score * w["performance"]
            + accessibility.score * w["accessibility"]
            + mobile_ux.score * w["mobile_ux"]
            + content.score * w["content"]
            + cta.score * w["cta"]
        )
        return round(weighted, 2)

    @staticmethod
    def _top_items(lists: List[List[str]], limit: int = 5) -> List[str]:
        merged: List[str] = []
        for lst in lists:
            merged.extend(lst)
        return merged[:limit]
