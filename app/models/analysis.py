from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, field_validator


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AnalysisStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class AnalysisRequest(BaseModel):
    url: str
    mobile: bool = False
    full_page: bool = True
    timeout: Optional[int] = None

    @field_validator("url")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v


class CompareRequest(BaseModel):
    url1: str
    url2: str
    mobile: bool = False
    full_page: bool = True
    timeout: Optional[int] = None

    @field_validator("url1", "url2")
    @classmethod
    def validate_url(cls, v: str) -> str:
        if not v.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return v


class NavigationAnalysis(BaseModel):
    score: float
    has_main_nav: bool = False
    has_breadcrumbs: bool = False
    has_search: bool = False
    link_count: int = 0
    broken_links: List[str] = []
    issues: List[str] = []
    recommendations: List[str] = []


class FormsAnalysis(BaseModel):
    score: float
    form_count: int = 0
    avg_field_count: float = 0.0
    has_validation: bool = False
    has_error_messages: bool = False
    issues: List[str] = []
    recommendations: List[str] = []


class PerformanceAnalysis(BaseModel):
    score: float
    load_time_ms: float = 0.0
    dom_content_loaded_ms: float = 0.0
    first_paint_ms: float = 0.0
    resource_count: int = 0
    page_size_kb: float = 0.0
    issues: List[str] = []
    recommendations: List[str] = []


class AccessibilityAnalysis(BaseModel):
    score: float
    has_skip_links: bool = False
    images_with_alt: int = 0
    images_without_alt: int = 0
    heading_structure_valid: bool = False
    color_contrast_issues: int = 0
    aria_labels_count: int = 0
    issues: List[str] = []
    recommendations: List[str] = []


class MobileUXAnalysis(BaseModel):
    score: float
    has_viewport_meta: bool = False
    is_responsive: bool = False
    touch_targets_adequate: bool = False
    font_size_adequate: bool = False
    issues: List[str] = []
    recommendations: List[str] = []


class ContentAnalysis(BaseModel):
    score: float
    word_count: int = 0
    heading_count: int = 0
    paragraph_count: int = 0
    has_clear_value_proposition: bool = False
    readability_score: float = 0.0
    issues: List[str] = []
    recommendations: List[str] = []


class CTAAnalysis(BaseModel):
    score: float
    cta_count: int = 0
    above_fold_ctas: int = 0
    has_primary_cta: bool = False
    cta_visibility_score: float = 0.0
    issues: List[str] = []
    recommendations: List[str] = []


class AnalysisResult(BaseModel):
    url: str
    overall_score: float
    navigation: NavigationAnalysis
    forms: FormsAnalysis
    performance: PerformanceAnalysis
    accessibility: AccessibilityAnalysis
    mobile_ux: MobileUXAnalysis
    content: ContentAnalysis
    cta: CTAAnalysis
    top_issues: List[str] = []
    top_recommendations: List[str] = []
    analyzed_at: datetime = None  # type: ignore[assignment]

    def model_post_init(self, __context: Any) -> None:
        if self.analyzed_at is None:
            object.__setattr__(self, "analyzed_at", _utcnow())

    model_config = {"arbitrary_types_allowed": True}


class ComparisonMatrix(BaseModel):
    category: str
    site1_score: float
    site2_score: float
    winner: str
    difference: float


class ComparisonResult(BaseModel):
    url1: str
    url2: str
    site1: AnalysisResult
    site2: AnalysisResult
    comparison_matrix: List[ComparisonMatrix] = []
    overall_winner: str
    summary: str
    compared_at: datetime = None  # type: ignore[assignment]

    def model_post_init(self, __context: Any) -> None:
        if self.compared_at is None:
            object.__setattr__(self, "compared_at", _utcnow())

    model_config = {"arbitrary_types_allowed": True}


class AnalysisResponse(BaseModel):
    report_id: str
    status: AnalysisStatus
    result: Optional[AnalysisResult] = None
    error: Optional[str] = None
    created_at: datetime = None  # type: ignore[assignment]

    def model_post_init(self, __context: Any) -> None:
        if self.created_at is None:
            object.__setattr__(self, "created_at", _utcnow())

    model_config = {"arbitrary_types_allowed": True}


class ComparisonResponse(BaseModel):
    report_id: str
    status: AnalysisStatus
    result: Optional[ComparisonResult] = None
    error: Optional[str] = None
    created_at: datetime = None  # type: ignore[assignment]

    def model_post_init(self, __context: Any) -> None:
        if self.created_at is None:
            object.__setattr__(self, "created_at", _utcnow())

    model_config = {"arbitrary_types_allowed": True}
