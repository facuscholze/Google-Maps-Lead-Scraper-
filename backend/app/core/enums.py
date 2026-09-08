"""Shared status constants and small enums used across the domain.

Statuses are stored as plain strings so models stay portable (SQLite tests,
PostgreSQL production) while keeping an auditable set of allowed values.
"""
from __future__ import annotations

from enum import Enum


class SearchStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class JobType(str, Enum):
    GOOGLE_PLACES = "GOOGLE_PLACES"
    FILTER = "FILTER"
    WEBSITE_CRAWL = "WEBSITE_CRAWL"
    WEBSITE_ANALYSIS = "WEBSITE_ANALYSIS"
    CONTACT_DISCOVERY = "CONTACT_DISCOVERY"
    LEAD_SCORING = "LEAD_SCORING"
    PROPOSAL_GENERATION = "PROPOSAL_GENERATION"
    EMAIL_QUEUE = "EMAIL_QUEUE"


class JobStatus(str, Enum):
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class LeadTemperature(str, Enum):
    HOT = "HOT"
    WARM = "WARM"
    COLD = "COLD"
    LOW = "LOW"


class RecommendedAction(str, Enum):
    CONTACT_NOW = "CONTACT_NOW"
    REVIEW_FIRST = "REVIEW_FIRST"
    LOW_PRIORITY = "LOW_PRIORITY"
    DO_NOT_CONTACT = "DO_NOT_CONTACT"


class Priority(str, Enum):
    P1 = "P1"
    P2 = "P2"
    P3 = "P3"
    P4 = "P4"


class LeadStatus(str, Enum):
    NEW = "NEW"
    CONTACTED = "CONTACTED"
    REPLIED = "REPLIED"
    OPTED_OUT = "OPTED_OUT"
    DO_NOT_CONTACT = "DO_NOT_CONTACT"
    ARCHIVED = "ARCHIVED"


class WebsiteStatus(str, Enum):
    NONE = "NONE"  # no website available
    FOUND = "FOUND"  # website known, not crawled yet
    CRAWLED = "CRAWLED"
    ANALYZED = "ANALYZED"
    ERROR = "ERROR"


class EmailConfidence(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ProposalStatus(str, Enum):
    DRAFT = "DRAFT"
    AI_GENERATED = "AI_GENERATED"
    READY_FOR_REVIEW = "READY_FOR_REVIEW"
    APPROVED = "APPROVED"
    QUEUED = "QUEUED"
    SENT = "SENT"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class EmailStatus(str, Enum):
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    SENT = "SENT"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    DO_NOT_CONTACT = "DO_NOT_CONTACT"


class EmailEventType(str, Enum):
    SENT = "SENT"
    FAILED = "FAILED"
    BOUNCED = "BOUNCED"
    REPLIED = "REPLIED"
    OPTED_OUT = "OPTED_OUT"


class AccountStatus(str, Enum):
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
    ERROR = "ERROR"


class Role(str, Enum):
    OWNER = "OWNER"
    ADMIN = "ADMIN"
    MEMBER = "MEMBER"


class RotationStrategy(str, Enum):
    ROUND_ROBIN = "ROUND_ROBIN"
    LEAST_USED = "LEAST_USED"
    MANUAL = "MANUAL"
