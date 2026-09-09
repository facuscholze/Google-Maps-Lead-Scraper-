"""Lead endpoints (spec §57, §66): list, detail, re-audit, proposal, export."""
from __future__ import annotations

import csv
import io
import json
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, Response, status
from openpyxl import Workbook
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.repositories.audits import AuditRepository
from app.repositories.leads import LeadRepository
from app.schemas.api import LeadDetail, LeadListResponse, LeadSummary, ProposalOut
from app.services.emailing.proposal_service import ProposalService
from app.services.lead_service import score_lead
from app.services.website_service import WebsiteAnalysisService

router = APIRouter(prefix="/leads", tags=["leads"])

_LEAD_FIELDS = [
    "id", "place_id", "business_name", "category", "primary_type", "address", "city",
    "country", "latitude", "longitude", "phone", "international_phone", "website",
    "email", "email_confidence", "google_maps_url", "rating", "reviews_count",
    "business_status", "website_status", "website_score", "lead_score",
    "opportunity_score", "lead_temperature", "priority", "recommended_service",
    "recommended_action", "status", "confidence",
]


def _lead_summary(lead) -> LeadSummary:
    return LeadSummary.model_validate(lead)


@router.get("", response_model=LeadListResponse)
def list_leads(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    search_id: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=200),
    temperature: str | None = None,
    min_lead_score: int | None = None,
    min_opportunity_score: int | None = None,
    min_website_score: float | None = None,
    min_reviews: int | None = None,
    min_rating: float | None = None,
    has_website: bool | None = None,
    has_email: bool | None = None,
    email_confidence: str | None = None,
    recommended_service: str | None = None,
    status: str | None = None,
    q: str | None = None,
    include_unlinked: bool = False,
) -> LeadListResponse:
    filters: dict[str, Any] = {
        "temperature": temperature.split(",") if temperature else None,
        "min_lead_score": min_lead_score,
        "min_opportunity_score": min_opportunity_score,
        "min_website_score": min_website_score,
        "min_reviews": min_reviews,
        "min_rating": min_rating,
        "has_website": has_website,
        "has_email": has_email,
        "email_confidence": email_confidence,
        "recommended_service": recommended_service,
        "status": status,
        "q": q,
    }
    items, total = LeadRepository(db).list_for_workspace(
        user.workspace_id, search_id=search_id, page=page, page_size=page_size,
        filters=filters, linked_only=not include_unlinked,
    )
    return LeadListResponse(
        items=[_lead_summary(l) for l in items], total=total, page=page, page_size=page_size
    )


@router.get("/export", response_class=Response)
def export_leads(
    fmt: str = Query("csv", pattern="^(csv|xlsx|json)$"),
    selection: str = Query("all", pattern="^(all|selected|HOT|WARM|READY_TO_CONTACT)$"),
    ids: str | None = None,  # comma separated when selection=selected
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    repo = LeadRepository(db)
    if selection == "selected" and ids:
        selected_ids = [int(x) for x in ids.split(",") if x.strip().isdigit()]
        leads = [
            repo.get_for_workspace(user.workspace_id, lid)
            for lid in selected_ids
            if repo.get_for_workspace(user.workspace_id, lid) is not None
        ]
    elif selection == "HOT":
        leads, _ = repo.list_for_workspace(user.workspace_id, filters={"temperature": "HOT"}, page_size=1000)
    elif selection == "WARM":
        leads, _ = repo.list_for_workspace(user.workspace_id, filters={"temperature": "WARM"}, page_size=1000)
    elif selection == "READY_TO_CONTACT":
        leads, _ = repo.list_for_workspace(
            user.workspace_id,
            filters={"temperature": ["HOT", "WARM"], "email_confidence": "HIGH"},
            page_size=1000,
        )
    else:
        leads, _ = repo.list_for_workspace(user.workspace_id, page_size=1000)

    rows = [{f: getattr(l, f, None) for f in _LEAD_FIELDS} for l in leads]
    filename = "avascho_leads"
    if fmt == "json":
        content = json.dumps(rows, ensure_ascii=False, indent=2, default=str)
        return Response(
            content=content,
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename}.json"'},
        )
    if fmt == "xlsx":
        wb = Workbook()
        ws = wb.active
        ws.title = "Leads"
        ws.append(_LEAD_FIELDS)
        for row in rows:
            ws.append([row.get(f) for f in _LEAD_FIELDS])
        buffer = io.BytesIO()
        wb.save(buffer)
        return Response(
            content=buffer.getvalue(),
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            headers={"Content-Disposition": f'attachment; filename="{filename}.xlsx"'},
        )
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=_LEAD_FIELDS)
    writer.writeheader()
    for row in rows:
        writer.writerow({k: ("" if v is None else v) for k, v in row.items()})
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}.csv"'},
    )


@router.get("/{lead_id}", response_model=LeadDetail)
def get_lead(
    lead_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LeadDetail:
    lead = LeadRepository(db).get_for_workspace(user.workspace_id, lead_id)
    if lead is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lead no encontrado")
    return LeadDetail.model_validate(lead)


@router.post("/{lead_id}/audit", response_model=LeadDetail)
def reaudit_lead(
    lead_id: int,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LeadDetail:
    lead = LeadRepository(db).get_for_workspace(user.workspace_id, lead_id)
    if lead is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lead no encontrado")
    if not lead.website:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Este lead no tiene website disponible")

    def _task(lid: int) -> None:
        from app.core.database import SessionLocal

        session = SessionLocal()
        try:
            service = WebsiteAnalysisService(session)
            current = LeadRepository(session).get_for_workspace(user.workspace_id, lid)
            if current is not None:
                service.analyze_lead(current)
                score_lead(session, current)
                session.commit()
        finally:
            session.close()

    background_tasks.add_task(_task, lead.id)
    return LeadDetail.model_validate(lead)


@router.post("/{lead_id}/generate-proposal", response_model=ProposalOut)
def generate_proposal(
    lead_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> ProposalOut:
    """Generate a personalized commercial proposal for the lead (spec §37)."""
    from app.repositories.leads import LeadRepository

    lead = LeadRepository(db).get_for_workspace(user.workspace_id, lead_id)
    if lead is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lead no encontrado")
    try:
        proposal = ProposalService(db).generate(user.workspace_id, lead_id)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    db.commit()
    out = ProposalOut.model_validate(proposal)
    out.lead_name = proposal.lead.business_name if proposal.lead else None
    out.strengths = proposal.strengths_json
    out.opportunities = proposal.opportunities_json
    return out


@router.get("/{lead_id}/audit", response_model=dict)
def get_lead_audit(
    lead_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    lead = LeadRepository(db).get_for_workspace(user.workspace_id, lead_id)
    if lead is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lead no encontrado")
    audit = AuditRepository(db).latest_for_lead(lead_id)
    if audit is None:
        return {"lead_id": lead_id, "audit": None}
    pages = AuditRepository(db).pages_for_audit(audit.id)
    return {
        "lead_id": lead_id,
        "audit": {
            "id": audit.id,
            "url": audit.url,
            "overall_score": audit.overall_score,
            "subscores": audit.subscores,
            "strengths": audit.strengths,
            "weaknesses": audit.weaknesses,
            "opportunities": audit.opportunities,
            "extracted": audit.extracted_data,
            "title": audit.title,
            "services": audit.services,
            "technologies": audit.technologies,
            "model": audit.ai_model,
            "audited_at": audit.audited_at,
        },
        "pages": [
            {"url": p.url, "kind": p.kind, "http_status": p.http_status, "title": p.title}
            for p in pages
        ],
    }
