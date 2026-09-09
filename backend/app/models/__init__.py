"""Model registry so Alembic autogenerate / metadata.create_all see every table."""
from app.models.base import Base  # noqa: F401
from app.models.emailing import (  # noqa: F401
    Email,
    EmailAccount,
    EmailEvent,
    Proposal,
    SuppressionEntry,
)
from app.models.jobs import Job  # noqa: F401
from app.models.lead import Lead  # noqa: F401
from app.models.search import Search, SearchLead, SearchPreset  # noqa: F401
from app.models.user import User, Workspace  # noqa: F401
from app.models.website import WebsiteAudit, WebsitePage  # noqa: F401

__all__ = [
    "Base",
    "User",
    "Workspace",
    "Search",
    "SearchLead",
    "SearchPreset",
    "Lead",
    "WebsiteAudit",
    "WebsitePage",
    "Proposal",
    "EmailAccount",
    "Email",
    "EmailEvent",
    "SuppressionEntry",
    "Job",
]
