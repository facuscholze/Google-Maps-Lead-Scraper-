"""API request/response schemas (Pydantic)."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


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
class GeoRect(BaseModel):
    """Axis-aligned bounds. Coordinates: [lat, lng] pairs."""
    sw: list[float] = Field(min_length=2, max_length=2)
    ne: list[float] = Field(min_length=2, max_length=2)

    @model_validator(mode="after")
    def _check_order(self) -> "GeoRect":
        if not (-90 <= self.sw[0] < self.ne[0] <= 90 and -180 <= self.sw[1] < self.ne[1] <= 180):
            raise ValueError("rect inválido: se espera sw al sudoeste de ne")
        return self


class GeoCircle(BaseModel):
    center: list[float] = Field(min_length=2, max_length=2)
    radius_km: float = Field(gt=0, le=200)

    @model_validator(mode="after")
    def _check_center(self) -> "GeoCircle":
        lat, lng = self.center
        if not (-90 <= lat <= 90 and -180 <= lng <= 180):
            raise ValueError("center fuera de rango")
        return self


class GeoPolygon(BaseModel):
    points: list[list[float]] = Field(min_length=3, max_length=128)

    @model_validator(mode="after")
    def _check_points(self) -> "GeoPolygon":
        for p in self.points:
            if len(p) != 2 or not (-90 <= p[0] <= 90 and -180 <= p[1] <= 180):
                raise ValueError("punto de polígono fuera de rango")
        return self


class GeoArea(BaseModel):
    """Exactamente una forma: rect | circle | polygon."""
    rect: GeoRect | None = None
    circle: GeoCircle | None = None
    polygon: GeoPolygon | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> "GeoArea":
        n = sum(x is not None for x in (self.rect, self.circle, self.polygon))
        if n != 1:
            raise ValueError("geo debe tener exactamente una forma (rect, circle o polygon)")
        return self

    def to_spec(self) -> dict[str, Any]:
        """Formato que entiende ``geo_grid.cells_from_geo``."""
        if self.rect is not None:
            return {"type": "rect", "sw": list(self.rect.sw), "ne": list(self.rect.ne)}
        if self.circle is not None:
            return {
                "type": "circle",
                "center": list(self.circle.center),
                "radius_m": self.circle.radius_km * 1000.0,
            }
        return {"type": "polygon", "points": [list(p) for p in self.polygon.points]}  # type: ignore[union-attr]


class SearchCreate(BaseModel):
    category: str = Field(min_length=2, max_length=255)
    location: str | None = Field(default=None, max_length=255)
    geo: GeoArea | None = None
    budget_cap_usd: float | None = Field(default=None, gt=0, le=10000)
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
    mode: Literal["text", "grid"]
    max_results: int
    min_reviews: int
    max_reviews: int | None
    min_rating: float
    estimated_api_calls: int
    estimated_api_calls_max: int = 0
    estimated_cost_usd: float = 0.0
    estimated_cost_max_usd: float = 0.0
    grid_cells: int = 0
    budget_cap_usd: float | None = None
    warnings: list[str] = Field(default_factory=list)
    disclaimer: str = (
        "Esta búsqueda puede generar múltiples solicitudes a la API de Google Places. "
        "El uso de la API no es necesariamente gratuito."
    )


class SearchOut(ORMModel):
    mode: str
    geo_json: dict[str, Any] | None = None
    budget_cap_usd: float | None = None
    estimated_api_calls: int
    estimated_cost_usd: float | None = None  # NULL in rows predating the estimator
    api_calls: int
    api_cost_usd: float
    budget_exhausted: bool
    grid_total_cells: int
    grid_done_cells: int
    grid_capped_cells: int
    deduped_count: int
    cancel_requested: bool
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
    # Coords needed by the Leads map view (F3) — cheap to send, no privacy concern
    # (public business locations from Places).
    latitude: float | None = None
    longitude: float | None = None
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
    # Fase 4: etiquetas (sin padding, ej ["frio","recontacto"]) + responsable
    tags: list[str] = Field(default_factory=list)
    owner_name: str | None = None

    @field_validator("tags", mode="before")
    @classmethod
    def _unpad_tags(cls, v: Any) -> list[str]:
        # ORM stores ",frio,recontacto," (padded CSV for LIKE filtering).
        if isinstance(v, str):
            return [t for t in (part.strip() for part in v.split(",")) if t]
        return v if isinstance(v, list) else []


class LeadViewIn(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    config: dict[str, Any] = Field(default_factory=dict)


class LeadViewOut(ORMModel):
    id: int
    name: str
    config_json: dict[str, Any]
    created_at: datetime
    updated_at: datetime


LeadsBulkAction = Literal[
    "set_status", "archive", "unarchive", "add_tag", "remove_tag",
    "assign_owner", "clear_owner",
]


class LeadsBulkRequest(BaseModel):
    ids: list[int] = Field(min_length=1, max_length=1000)
    action: LeadsBulkAction
    status: str | None = None
    tag: str | None = Field(default=None, max_length=60)
    owner: str | None = Field(default=None, max_length=120)


class LeadsBulkResponse(BaseModel):
    updated: int
    skipped: list[int] = Field(default_factory=list)


class BulkProposalsResponse(BaseModel):
    created: list[int] = Field(default_factory=list)   # lead_ids
    skipped: list[dict[str, Any]] = Field(default_factory=list)  # {lead_id, reason}


class LeadActivityItem(BaseModel):
    ts: datetime
    kind: str  # created|audited|proposal|email
    label: str
    detail: str | None = None


class LeadActivityOut(BaseModel):
    items: list[LeadActivityItem]


# ------------------------------------------------------------- scoring (F6) --
class ScoringWeightsIn(BaseModel):
    reputation: float | None = Field(default=None, ge=0, le=3)
    reviews: float | None = Field(default=None, ge=0, le=3)
    website_presence: float | None = Field(default=None, ge=0, le=3)
    website_quality: float | None = Field(default=None, ge=0, le=3)
    opportunities: float | None = Field(default=None, ge=0, le=3)
    phone: float | None = Field(default=None, ge=0, le=3)
    email: float | None = Field(default=None, ge=0, le=3)


class ScoringConfigIn(BaseModel):
    weights: ScoringWeightsIn | None = None
    hot_min: int | None = Field(default=None, ge=1, le=99)
    warm_min: int | None = Field(default=None, ge=1, le=99)
    cold_min: int | None = Field(default=None, ge=1, le=99)


class ScoringConfigOut(BaseModel):
    id: int | None = None  # None = defaults (sin fila persistida)
    weights: dict[str, float]
    hot_min: int = 80
    warm_min: int = 60
    cold_min: int = 40
    is_default: bool = False
    updated_at: datetime | None = None


class LeadsRescoreRequest(BaseModel):
    ids: list[int] | None = Field(default=None, max_length=500)


class LeadsRescoreResponse(BaseModel):
    rescored: int
    skipped: list[int] = Field(default_factory=list)


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
    # Name of the tab that received the rows (None when nothing was written).
    sheet_name: str | None = None
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
    # F7/D7.3: razonamiento + evidence_ledger (procedencia Places/audit)
    ai_reasoning: dict[str, Any] | None = None
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
class EmailEventOut(ORMModel):
    """F10: timeline del correo (queue, envíos, reintentos, baja, fallos)."""
    event_type: str
    detail: str | None = None
    occurred_at: datetime


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
    # F10: nº de intentos de envío (reintentos transitorios = attempts > 1)
    attempts: int = 0
    created_at: datetime


class EmailDetailOut(EmailOut):
    """Detalle con el historial de eventos ordenado cronológicamente (F10)."""
    events: list[EmailEventOut] = []


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
