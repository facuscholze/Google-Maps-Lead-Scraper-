"""API request/response schemas (Pydantic)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ------------------------------------------------------------------- auth -----
class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict[str, Any]


# ---------------------------------------------------------------- searches ----
class SearchCreate(BaseModel):
    category: str = Field(min_length=2, max_length=255)
    location: str | None = Field(default=None, max_length=255)
    max_results: int = Field(default=100, ge=1, le=500)
    min_reviews: int = Field(default=0, ge=0)
    max_reviews: int | None = Field(default=None, ge=1)
    min_rating: float = Field(default=0.0, ge=0, le=5)
    only_with_website: bool = False
    only_with_phone: bool = False
    try_find_email: bool = True


class SearchPreview(BaseModel):
    query: str
    location: str | None
    max_results: int
    min_reviews: int
    max_reviews: int | None
    min_rating: float
    estimated_api_calls: int
    disclaimer: str = (
        "Esta búsqueda puede generar múltiples solicitudes a la API de Google Places. "
        "El uso de la API no es necesariamente gratuito."
    )


class SearchOut(ORMModel):
    id: int
    query: str
    location: str | None = None
    category: str | None = None
    max_results: int
    min_reviews: int
    max_reviews: int | None = None
    min_rating: float
    only_with_website: bool
    only_with_phone: bool
    try_find_email: bool
    status: str
    results_total: int
    results_qualified: int
    websites_analyzed: int
    emails_found: int
    hot_count: int
    warm_count: int
    cold_count: int
    google_pages: int
    error_message: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    duration_seconds: float | None = None


# ------------------------------------------------------------------- leads ----
class LeadSummary(ORMModel):
    id: int
    place_id: str
    business_name: str
    category: str | None = None
    city: str | None = None
    country: str | None = None
    website: str | None = None
    phone: str | None = None
    email: str | None = None
    email_confidence: str | None = None
    rating: float | None = None
    reviews_count: int
    website_status: str
    website_score: float | None = None
    lead_score: int | None = None
    opportunity_score: int | None = None
    lead_temperature: str | None = None
    priority: str | None = None
    recommended_service: str | None = None
    recommended_action: str | None = None
    status: str
    confidence: float | None = None


class LeadDetail(LeadSummary):
    primary_type: str | None = None
    address: str | None = None
    latitude: float | None = None
    longitude: float | None = None
    international_phone: str | None = None
    email_source_url: str | None = None
    google_maps_url: str | None = None
    business_status: str | None = None
    why_this_lead: str | None = None
    why_now: str | None = None
    score_breakdown: dict[str, Any] | None = None
    website_strengths: list[Any] | None = None
    website_weaknesses: list[Any] | None = None
    detected_opportunities: list[Any] | None = None
    contact_channels: dict[str, Any] | None = None
    created_at: datetime
    updated_at: datetime


class LeadListResponse(BaseModel):
    items: list[LeadSummary]
    total: int
    page: int
    page_size: int


class ExportToSheetsRequest(BaseModel):
    """Body of `POST /leads/export-to-sheets`.

    Filters mirror the ones the leads table uses so the sheet receives exactly
    what the user is looking at. Missing spreadsheet/sheet fall back to the
    configured defaults.
    """

    spreadsheet_id: str | None = None
    sheet_name: str | None = None
    selection: Literal["all", "selected", "HOT", "WARM", "READY_TO_CONTACT"] = "all"
    ids: list[int] | None = None
    search_id: int | None = None
    temperature: str | None = None
    q: str | None = None
    has_email: bool | None = None
    min_lead_score: int | None = None


class SheetsExportResponse(BaseModel):
    rows_written: int
    spreadsheet_url: str


# ---------------------------------------------------------------- proposals ---
class ProposalOut(ORMModel):
    id: int
    lead_id: int
    lead_name: str | None = None
    status: str
    subject: str | None = None
    opening: str | None = None
    personalized_observation: str | None = None
    strengths: list[Any] | None = None
    opportunities: list[Any] | None = None
    recommended_solution: str | None = None
    call_to_action: str | None = None
    signature: str | None = None
    body_html: str | None = None
    body_plain: str | None = None
    ai_model: str | None = None
    version: int
    approved_at: datetime | None = None
    created_at: datetime
    updated_at: datetime


class ProposalUpdate(BaseModel):
    subject: str | None = None
    opening: str | None = None
    personalized_observation: str | None = None
    strengths: list[Any] | None = None
    opportunities: list[Any] | None = None
    recommended_solution: str | None = None
    call_to_action: str | None = None
    signature: str | None = None
    body_html: str | None = None
    body_plain: str | None = None


class SendRequest(BaseModel):
    account_id: int | None = None
    strategy: Literal["ROUND_ROBIN", "LEAST_USED", "MANUAL"] = "ROUND_ROBIN"
    scheduled_at: datetime | None = None
    send_now: bool = False


# ----------------------------------------------------------- email accounts ---
class EmailAccountOut(ORMModel):
    id: int
    email: str
    provider: str
    status: str
    daily_limit: int
    sent_today: int
    sent_date: str | None = None
    last_sent_at: datetime | None = None
    display_name: str | None = None
    error_message: str | None = None
    created_at: datetime


class ConnectUrlResponse(BaseModel):
    url: str


# -------------------------------------------------------------------- emails ---
class EmailOut(ORMModel):
    id: int
    lead_id: int
    proposal_id: int | None = None
    gmail_account_id: int | None = None
    to_email: str
    from_email: str | None = None
    subject: str | None = None
    status: str
    scheduled_at: datetime | None = None
    sent_at: datetime | None = None
    error: str | None = None
    message_id: str | None = None
    created_at: datetime


# --------------------------------------------------------------------- jobs ----
class JobOut(ORMModel):
    id: int
    search_id: int | None = None
    job_type: str
    status: str
    progress: int
    current_step: str | None = None
    total: int
    done: int
    error_message: str | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime


# --------------------------------------------------------------- dashboard ----
class DashboardOut(BaseModel):
    cards: dict[str, int]
    averages: dict[str, float | None]
    funnel: dict[str, int]
    recent_searches: list[dict[str, Any]]
    top_leads: list[dict[str, Any]]
    review_queue: list[dict[str, Any]]
    health: dict[str, Any]


class SearchStatusOut(BaseModel):
    search: SearchOut
    jobs: list[JobOut]
    running: bool


# -------------------------------------------------------------- suppression ---
class SuppressionIn(BaseModel):
    email: str
    reason: str = "MANUAL"
    note: str | None = None


class SuppressionImport(BaseModel):
    emails: list[str]
    reason: str = "IMPORT"


class SuppressionOut(ORMModel):
    id: int
    email: str
    reason: str
    note: str | None = None
    active: bool
    created_at: datetime


# ------------------------------------------------------------------ presets ----
class PresetCreate(BaseModel):
    name: str
    config: dict[str, Any]


class PresetOut(ORMModel):
    id: int
    name: str
    config: dict[str, Any]
    created_at: datetime
