"""Centralized application configuration.

All settings are loaded once from the environment / .env file and exposed
through the `settings` singleton. No module should read os.environ directly.
"""
from __future__ import annotations

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # --- App -----------------------------------------------------------------
    app_name: str = "AvaScho Lead Intelligence"
    app_env: str = "development"  # development | test | production
    api_prefix: str = "/api"
    log_level: str = "INFO"
    default_timezone: str = "America/Argentina/Buenos_Aires"

    # --- Outbound proposal identity -------------------------------------------
    proposal_brand: str = "Innblock"
    proposal_contact_email: str = ""
    proposal_contact_url: str = "https://web-estudio-alpha.vercel.app/es/#contacto"
    proposal_website_url: str = "https://web-estudio-alpha.vercel.app/es/"

    # --- Database / queue ------------------------------------------------------
    database_url: str = "postgresql+psycopg2://avascho:avascho@localhost:5432/avascho"
    redis_url: str = "redis://localhost:6379/0"
    execution_mode: str = "inline"  # inline | celery

    # --- Google Places ----------------------------------------------------------
    google_maps_api_key: str = ""
    search_provider: str = "auto"  # auto | google | mock
    max_results_per_search: int = 100
    google_request_timeout: float = 20.0
    # Price list check 2026-10-14 — Text Search Enterprise, USD per 1.000 calls.
    # Override it if Google updates the pricing list (never hardcode in code).
    # https://developers.google.com/maps/billing-and-pricing/pricing#places-pricing
    places_price_per_1k_usd: float = 35.0

    # --- Grid sweep (area searches) ------------------------------------------------
    grid_cell_km: float = 1.5        # edge of each sweep cell
    grid_max_cells: int = 120        # hard ceiling of cells per search (cost brake)
    grid_subdivide: bool = True      # subdivide cells that hit the 60-result cap
    grid_max_subdivision_depth: int = 2

    # --- Crawler ---------------------------------------------------------------
    max_pages_per_domain: int = 10
    max_page_size_bytes: int = 2_000_000
    http_timeout_seconds: float = 15.0
    max_redirects: int = 3
    max_retries: int = 3
    crawl_delay_seconds: float = 0.4

    # --- AI ----------------------------------------------------------------------
    ai_provider: str = "rule_based"  # rule_based | openai_compatible | mock
    ai_api_key: str = ""
    ai_base_url: str = "https://api.openai.com/v1"
    ai_model: str = "gpt-4o-mini"
    ai_max_retries: int = 2

    # --- Auth / security ----------------------------------------------------------
    secret_key: str = "change-me"
    access_token_expire_minutes: int = 60 * 12
    encryption_key: str = ""  # Fernet key for OAuth tokens
    cors_origins: str = "http://localhost:3000"
    frontend_url: str = "http://localhost:3000"

    # --- Demo seed ---------------------------------------------------------------
    auto_create_demo_user: bool = True
    demo_email: str = "demo@avascho.com"
    demo_password: str = "demo-avascho-2026"
    demo_workspace: str = "AvaScho"

    # --- Gmail OAuth ---------------------------------------------------------------
    google_client_id: str = ""
    google_client_secret: str = ""
    google_oauth_redirect_uri: str = (
        "http://localhost:8000/api/email-accounts/gmail/callback"
    )

    # --- Google Sheets export ---------------------------------------------------------
    # Leads can be appended to a spreadsheet with a service account. The key is
    # stored as a single-line JSON string (never as a file path) and is never
    # logged or returned by any endpoint.
    google_sheets_enabled: bool = False
    google_sheets_service_account_json: str = ""
    google_sheets_default_spreadsheet_id: str = ""
    google_sheets_default_sheet_name: str = "Leads"

    # --- Email limits ---------------------------------------------------------------
    daily_email_limit: int = 5
    min_send_delay_seconds: int = 90
    max_send_delay_seconds: int = 420
    allowed_hours_start: int = 9
    allowed_hours_end: int = 19
    # Proxies whose X-Forwarded-For we trust for rate limiting / logs.
    trusted_proxies: str = "127.0.0.1,::1"

    working_days: str = "1,2,3,4,5"  # ISO weekdays: 1=lunes … 7=domingo
    allow_mock_email_sending: bool = True
    # Inline email queue scheduler (dev/demo without celery). Sends pending mail
    # every `queue_scheduler_interval_seconds`. Off for tests / explicit deploys.
    queue_scheduler_enabled: bool = True
    queue_scheduler_interval_seconds: int = 45

    # --- Filters defaults -------------------------------------------------------------
    default_max_results: int = 100

    @field_validator("working_days")
    @classmethod
    def _parse_working_days(cls, v: str) -> str:
        days = [int(x.strip()) for x in v.split(",") if x.strip()]
        if not days or any(d < 1 or d > 7 for d in days):
            raise ValueError("working_days must contain ISO weekday numbers 1-7 (1=Mon, 7=Sun)")
        return ",".join(str(d) for d in days)

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def trusted_proxy_set(self) -> set[str]:
        """Peers from whom we trust X-Forwarded-For (Nginx/Next rewrites)."""
        return {o.strip() for o in self.trusted_proxies.split(",") if o.strip()}

    @property
    def working_day_set(self) -> set[int]:
        return {int(x) for x in self.working_days.split(",")}

    @property
    def is_production(self) -> bool:
        return self.app_env == "production"

    @property
    def google_places_enabled(self) -> bool:
        return bool(self.google_maps_api_key)

    def working_hours_ok(self, hour_utc: int, tz_offsets_hint: int = 0) -> bool:
        """Whether `hour` (UTC) falls inside the configured window.

        The API stores UTC; senders are configured with a timezone. We accept
        a naive check performed by the scheduler against the configured tz.
        """
        local = (hour_utc + tz_offsets_hint) % 24
        return self.allowed_hours_start <= local < self.allowed_hours_end


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
