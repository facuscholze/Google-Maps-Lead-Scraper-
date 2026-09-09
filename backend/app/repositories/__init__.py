"""Repository layer."""
from app.repositories.audits import AuditRepository  # noqa: F401
from app.repositories.emailing import (  # noqa: F401
    EmailAccountRepository,
    EmailRepository,
    ProposalRepository,
    SuppressionRepository,
    mark_lead_suppressed,
)
from app.repositories.jobs import JobRepository  # noqa: F401
from app.repositories.leads import LeadRepository  # noqa: F401
from app.repositories.searches import SearchRepository  # noqa: F401
from app.repositories.users import UserRepository, WorkspaceRepository  # noqa: F401
