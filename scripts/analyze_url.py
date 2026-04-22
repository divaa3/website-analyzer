#!/usr/bin/env python3
"""Analyze a URL extracted from a GitHub issue body and print Markdown results.

Usage (called by the GitHub Actions workflow):
    ISSUE_BODY="Analyze the UX for https://example.com" python scripts/analyze_url.py
Or directly:
    python scripts/analyze_url.py "https://example.com"
"""
from __future__ import annotations

import asyncio
import os
import re
import sys

# Ensure the repo root is on sys.path so that ``app`` is importable when the
# script is executed directly (e.g. ``python scripts/analyze_url.py``).
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models.analysis import AnalysisResult  # noqa: E402
from app.services.analyzer_service import AnalyzerService  # noqa: E402
from app.services.browser_service import BrowserService  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_URL_RE = re.compile(r"https?://[^\s\"'<>]+")


def extract_url(text: str) -> str | None:
    """Return the first HTTP/HTTPS URL found in *text*, or ``None``."""
    match = _URL_RE.search(text)
    if not match:
        return None
    url = match.group(0).rstrip(".,;:!?)")
    return url


def _score_bar(score: float, width: int = 10) -> str:
    filled = max(0, min(width, round(score)))
    return "█" * filled + "░" * (width - filled)


def format_report(result: AnalysisResult, url: str) -> str:
    """Render *result* as a Markdown string suitable for a GitHub comment."""
    nav = result.navigation
    perf = result.performance
    acc = result.accessibility
    mob = result.mobile_ux
    forms = result.forms
    content = result.content
    cta = result.cta

    def format_boolean(flag: bool) -> str:  # noqa: FBT001
        return "✅" if flag else "❌"

    form_detail = f"{forms.form_count} form(s)"
    if forms.form_count:
        form_detail += f" · {forms.avg_field_count} avg fields · {format_boolean(forms.has_validation)} validation"

    lines: list[str] = [
        "## 📊 UX Analysis Report",
        "",
        f"**URL:** `{url}`",
        "",
        f"### Overall Score: **{result.overall_score:.1f} / 10** `{_score_bar(result.overall_score)}`",
        "",
        "| Dimension | Score | Key Findings |",
        "|-----------|------:|--------------|",
        (
            f"| 🧭 Navigation | {nav.score}/10 | "
            f"{format_boolean(nav.has_main_nav)} `<nav>` · "
            f"{format_boolean(nav.has_breadcrumbs)} breadcrumbs · "
            f"{format_boolean(nav.has_search)} search · "
            f"{nav.link_count} links |"
        ),
        (
            f"| 🚀 Performance | {perf.score}/10 | "
            f"Load: {perf.load_time_ms:.0f} ms · "
            f"Resources: {perf.resource_count} · "
            f"Size: {perf.page_size_kb:.0f} KB |"
        ),
        (
            f"| ♿ Accessibility | {acc.score}/10 | "
            f"{format_boolean(acc.heading_structure_valid)} H1 structure · "
            f"{format_boolean(acc.has_skip_links)} skip link · "
            + (
                f"❌ {acc.images_without_alt} img(s) missing alt"
                if acc.images_without_alt
                else "✅ alt text OK"
            )
            + " |"
        ),
        (
            f"| 📱 Mobile UX | {mob.score}/10 | "
            f"{format_boolean(mob.has_viewport_meta)} viewport · "
            f"{format_boolean(mob.is_responsive)} responsive · "
            f"{format_boolean(mob.font_size_adequate)} font size |"
        ),
        f"| 📝 Forms | {forms.score}/10 | {form_detail} |",
        (
            f"| 📄 Content | {content.score}/10 | "
            f"{content.word_count} words · "
            f"{content.heading_count} headings · "
            f"{format_boolean(content.has_clear_value_proposition)} value prop |"
        ),
        (
            f"| 🎯 CTA | {cta.score}/10 | "
            f"{cta.cta_count} CTA(s) · "
            f"{cta.above_fold_ctas} above fold |"
        ),
        "",
    ]

    if result.top_issues:
        lines += ["### ⚠️ Top Issues", ""]
        for issue in result.top_issues[:5]:
            lines.append(f"- {issue}")
        lines.append("")

    if result.top_recommendations:
        lines += ["### 💡 Top Recommendations", ""]
        for rec in result.top_recommendations[:5]:
            lines.append(f"- {rec}")
        lines.append("")

    lines += [
        "---",
        (
            f"*Analyzed at {result.analyzed_at.strftime('%Y-%m-%d %H:%M UTC')} · "
            "[Website Analyzer](https://github.com/divaa3/website-analyzer)*"
        ),
        (
            "*Note: analysis is performed via a headless browser; "
            "results reflect the page at the time of the request.*"
        ),
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Async core
# ---------------------------------------------------------------------------


async def _run(url: str) -> None:
    service = BrowserService()
    await service.start()
    try:
        page_data = await service.fetch_page_data(url, mobile=False)
    finally:
        await service.stop()

    if page_data.get("error"):
        print(
            f"## ❌ Analysis Failed\n\n"
            f"Could not fetch `{url}`:\n\n"
            f"```\n{page_data['error']}\n```"
        )
        return

    status = page_data.get("status_code", 200)
    if status and status >= 400:
        print(
            f"## ❌ Analysis Failed\n\n"
            f"The page returned HTTP **{status}** for `{url}`."
        )
        return

    analyzer = AnalyzerService()
    result = analyzer.analyze(page_data)
    print(format_report(result, url))


# ---------------------------------------------------------------------------
# Entry-point
# ---------------------------------------------------------------------------


def main() -> None:
    # Accept the URL either from ISSUE_BODY env var (workflow usage) or as a
    # positional CLI argument (direct usage).
    issue_body = os.environ.get("ISSUE_BODY", " ".join(sys.argv[1:]))
    url = extract_url(issue_body)

    if not url:
        print(
            "## ❌ No URL Found\n\n"
            "No valid HTTP/HTTPS URL was detected in the issue body.\n\n"
            "Please include the full URL (starting with `https://`) in the issue."
        )
        return

    asyncio.run(_run(url))


if __name__ == "__main__":
    main()
