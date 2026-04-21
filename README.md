# Website Analyzer

> AI-powered website analyzer that compares websites and identifies customer journey flaws.

[![CI](https://github.com/divaa3/website-analyzer/actions/workflows/ci.yml/badge.svg)](https://github.com/divaa3/website-analyzer/actions/workflows/ci.yml)

## Overview

Website Analyzer is a **FastAPI-based REST API** that uses Playwright browser automation to perform comprehensive UX/CX analysis of websites. It supports:

- **Single website analysis** – evaluate navigation, performance, accessibility, mobile UX, content quality and CTA effectiveness.
- **Side-by-side comparison** – compare two websites with a detailed scoring matrix.

## Project Structure

```
website-analyzer/
├── app/
│   ├── main.py              # FastAPI app factory
│   ├── config.py            # Settings
│   ├── models/
│   │   └── analysis.py      # Pydantic models
│   ├── services/
│   │   ├── browser_service.py   # Playwright browser wrapper
│   │   ├── analyzer_service.py  # Analysis engine
│   │   └── report_service.py    # Report persistence
│   ├── routes/
│   │   ├── analysis.py      # /api/analyze, /api/compare
│   │   └── reports.py       # /api/reports, /api/history
│   └── utils/
│       ├── logger.py
│       └── metrics.py
├── tests/
│   ├── test_analyzer.py     # Unit tests for the analysis engine
│   └── test_api.py          # Integration tests for the API
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── main.py                  # CLI entry point
└── .github/workflows/ci.yml
```

## Quick Start

### Local (without Docker)

```bash
# Clone the repository
git clone https://github.com/divaa3/website-analyzer.git
cd website-analyzer

# Install Python dependencies
pip install -r requirements.txt

# Install Playwright browser
playwright install chromium

# Run the API server
python main.py
# → http://localhost:8000
```

### Docker

```bash
docker-compose up --build
# → http://localhost:8000
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/health` | Health check |
| `POST` | `/api/analyze` | Analyze a single website |
| `POST` | `/api/compare` | Compare two websites |
| `GET` | `/api/reports/{report_id}` | Retrieve a report by ID |
| `GET` | `/api/history` | List recent analyses |

Interactive API docs are available at **`/docs`** (Swagger UI) and **`/redoc`**.

## Usage Examples

### Analyze a single website

```bash
curl -X POST http://localhost:8000/api/analyze \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com", "mobile": false}'
```

<details>
<summary>Sample response</summary>

```json
{
  "report_id": "550e8400-e29b-41d4-a716-446655440000",
  "status": "completed",
  "result": {
    "url": "https://example.com",
    "overall_score": 7.45,
    "navigation": {
      "score": 8.5,
      "has_main_nav": true,
      "issues": [],
      "recommendations": ["Consider adding breadcrumbs to improve wayfinding."]
    },
    "performance": {
      "score": 8.5,
      "load_time_ms": 1200,
      "issues": []
    },
    "accessibility": {
      "score": 9.0,
      "images_without_alt": 0,
      "issues": []
    },
    "mobile_ux": { "score": 8.5, "has_viewport_meta": true },
    "content": { "score": 7.0, "word_count": 420 },
    "cta": { "score": 8.0, "cta_count": 3 },
    "top_issues": ["No breadcrumb navigation detected."],
    "top_recommendations": ["Add breadcrumbs to improve wayfinding."]
  }
}
```
</details>

### Compare two websites

```bash
curl -X POST http://localhost:8000/api/compare \
  -H "Content-Type: application/json" \
  -d '{"url1": "https://site-a.com", "url2": "https://site-b.com"}'
```

<details>
<summary>Sample response</summary>

```json
{
  "report_id": "...",
  "status": "completed",
  "result": {
    "url1": "https://site-a.com",
    "url2": "https://site-b.com",
    "comparison_matrix": [
      {"category": "Navigation", "site1_score": 8.5, "site2_score": 7.0, "winner": "https://site-a.com", "difference": 1.5},
      {"category": "Performance", "site1_score": 6.5, "site2_score": 9.0, "winner": "https://site-b.com", "difference": 2.5}
    ],
    "overall_winner": "https://site-b.com",
    "summary": "site-a.com scored 7.45/10. site-b.com scored 8.10/10. site-b.com is the stronger performer."
  }
}
```
</details>

## Analysis Dimensions

| Dimension | Weight | What is evaluated |
|-----------|--------|-------------------|
| Performance | 20 % | Load time, resource count, page size |
| Accessibility | 20 % | Alt text, skip links, heading structure, ARIA |
| Navigation | 15 % | `<nav>` element, breadcrumbs, search, link count |
| Forms | 15 % | Field count, validation, error messages |
| Mobile UX | 15 % | Viewport meta, responsive design, font sizes |
| Content | 10 % | Word count, headings, value proposition |
| CTA | 5 % | CTA count, above-fold presence, visual prominence |

## Configuration

All settings can be overridden via environment variables:

| Variable | Default | Description |
|----------|---------|-------------|
| `HOST` | `0.0.0.0` | Bind address |
| `PORT` | `8000` | Listen port |
| `DEBUG` | `false` | Enable hot-reload |
| `BROWSER_TIMEOUT` | `30000` | Playwright timeout (ms) |
| `REPORTS_DIR` | `reports` | Directory for saved reports |
| `MAX_HISTORY_ITEMS` | `100` | In-memory history cap |

## Running Tests

```bash
pytest tests/ -v
```

## License

MIT
