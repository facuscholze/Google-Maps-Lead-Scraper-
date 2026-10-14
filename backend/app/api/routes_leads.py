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
from app.core.config import settings
from app.core.database import get_db
from app.core.logging import log_event
from app.models.lead import Lead
from app.models.user import User
from app.repositories.audits import AuditRepository
from app.repositories.leads import LeadRepository
from app.repositories.searches import SearchRepository
from app.schemas.api import (
    BulkProposalsResponse,
    ExportToSheetsRequest,
    LeadActivityItem,
    LeadActivityOut,
    LeadDetail,
    LeadListResponse,
    LeadSummary,
    LeadsBulkRequest,
    LeadsBulkResponse,
    ProposalOut,
    SheetsExportResponse,
)
from app.services.emailing.proposal_service import ProposalService
from app.services.google_sheets_service import (
    GoogleSheetsError,
    GoogleSheetsExportService,
    GoogleSheetsNotConfiguredError,
    build_generic_tab_name,
    build_search_tab_name,
)
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


def _build_lead_filters(
    *,
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
    city: str | None = None,
    category: str | None = None,
    tag: str | None = None,
    owner: str | None = None,
    q: str | None = None,
) -> dict[str, Any]:
    """Build the filter dict understood by `LeadRepository._apply_filters`.

    Shared by `GET /leads`, `GET /leads/export` and `POST /leads/export-to-sheets`
    so every entry point filters the population in exactly the same way.
    """
    return {
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
        "city": city,
        "category": category,
        "tag": tag,
        "owner": owner,
        "q": q,
    }


def _select_leads_for_export(
    repo: LeadRepository,
    workspace_id: int,
    *,
    selection: str,
    ids: list[int] | None = None,
    filters: dict[str, Any] | None = None,
    search_id: int | None = None,
    limit: int = 1000,
) -> list[Lead]:
    """Resolve the leads a caller wants exported.

    `selected` honours an explicit id list; the named presets (HOT / WARM /
    READY_TO_CONTACT) narrow the temperature (and, for READY_TO_CONTACT, the
    email confidence); anything else exports the filtered population. Filters
    coming from the query string are always applied on top.
    """
    filters = dict(filters or {})
    if selection == "selected" and ids:
        leads = []
        for lid in ids:
            lead = repo.get_for_workspace(workspace_id, lid)
            if lead is not None:
                leads.append(lead)
        return leads
    if selection == "HOT":
        filters["temperature"] = ["HOT"]
    elif selection == "WARM":
        filters["temperature"] = ["WARM"]
    elif selection == "READY_TO_CONTACT":
        filters["temperature"] = ["HOT", "WARM"]
        filters["email_confidence"] = "HIGH"
    leads, _ = repo.list_for_workspace(
        workspace_id, search_id=search_id, filters=filters, page_size=limit
    )
    return leads


@router.get("", response_model=LeadListResponse)
def list_leads(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    search_id: int | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=500),  # 500 = tope honesto de la vista mapa (D3.5)
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
    city: str | None = None,
    category: str | None = None,
    tag: str | None = None,
    owner: str | None = None,
    sort: str | None = Query(default=None, pattern="^(business_name|category|city|reviews_count|rating|website_score|opportunity_score|lead_score|created_at)$"),
    order: str = Query(default="desc", pattern="^(asc|desc)$"),
    q: str | None = None,
    include_unlinked: bool = False,
) -> LeadListResponse:
    filters = _build_lead_filters(
        temperature=temperature,
        min_lead_score=min_lead_score,
        min_opportunity_score=min_opportunity_score,
        min_website_score=min_website_score,
        min_reviews=min_reviews,
        min_rating=min_rating,
        has_website=has_website,
        has_email=has_email,
        email_confidence=email_confidence,
        recommended_service=recommended_service,
        status=status,
        city=city,
        category=category,
        tag=tag,
        owner=owner,
        q=q,
    )
    items, total = LeadRepository(db).list_for_workspace(
        user.workspace_id, search_id=search_id, page=page, page_size=page_size,
        filters=filters, linked_only=not include_unlinked, sort=sort, order=order,
    )
    return LeadListResponse(
        items=[_lead_summary(l) for l in items], total=total, page=page, page_size=page_size
    )


@router.get("/export", response_class=Response)
def export_leads(
    fmt: str = Query("csv", pattern="^(csv|xlsx|json)$"),
    selection: str = Query("all", pattern="^(all|selected|HOT|WARM|READY_TO_CONTACT)$"),
    ids: str | None = None,  # comma separated when selection=selected
    search_id: int | None = None,
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
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Export leads as csv / xlsx / json, honouring the active UI filters.

    `selection` keeps working exactly as before; the optional filters narrow the
    exported population the same way `GET /leads` does, so what you see in the
    table is what you download.
    """
    selected_ids = (
        [int(x) for x in ids.split(",") if x.strip().isdigit()] if ids else None
    )
    leads = _select_leads_for_export(
        LeadRepository(db),
        user.workspace_id,
        selection=selection,
        ids=selected_ids,
        filters=_build_lead_filters(
            temperature=temperature,
            min_lead_score=min_lead_score,
            min_opportunity_score=min_opportunity_score,
            min_website_score=min_website_score,
            min_reviews=min_reviews,
            min_rating=min_rating,
            has_website=has_website,
            has_email=has_email,
            email_confidence=email_confidence,
            recommended_service=recommended_service,
            status=status,
            q=q,
        ),
        search_id=search_id,
    )

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


@router.post("/export-to-sheets", response_model=SheetsExportResponse)
def export_leads_to_sheets(
    payload: ExportToSheetsRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> SheetsExportResponse:
    """Append the leads matching the active filters to a Google spreadsheet.

    Uses the service account configured through GOOGLE_SHEETS_*; the key itself
    never leaves the backend.

    A new tab is created per export, named after the search it comes from
    ("<query> - dd-mm-yyyy") so the history stays readable; pass an explicit
    `sheet_name` to append to an existing tab instead.
    """
    if not settings.google_sheets_enabled:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "La integración con Google Sheets no está habilitada. "
            "Seteá GOOGLE_SHEETS_ENABLED=true en el .env del backend.",
        )

    spreadsheet_id = (
        payload.spreadsheet_id or settings.google_sheets_default_spreadsheet_id or ""
    ).strip()
    if not spreadsheet_id:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "No hay spreadsheet configurada. Indicá GOOGLE_SHEETS_DEFAULT_SPREADSHEET_ID "
            "en el .env del backend (o mandá spreadsheet_id en la request).",
        )

    # An explicit sheet_name is honoured as-is; otherwise a new tab is created
    # and named after the search the export comes from.
    explicit_sheet_name = (payload.sheet_name or "").strip()
    search = None
    if payload.search_id is not None:
        search = SearchRepository(db).get_for_workspace(user.workspace_id, payload.search_id)
        if search is None:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                f"La búsqueda {payload.search_id} no existe en este workspace.",
            )

    leads = _select_leads_for_export(
        LeadRepository(db),
        user.workspace_id,
        selection=payload.selection,
        ids=payload.ids,
        filters=_build_lead_filters(
            temperature=payload.temperature,
            min_lead_score=payload.min_lead_score,
            has_email=payload.has_email,
            q=payload.q,
        ),
        search_id=payload.search_id,
    )

    service = GoogleSheetsExportService()
    try:
        if explicit_sheet_name:
            rows_written = service.append_leads(spreadsheet_id, explicit_sheet_name, leads)
            sheet_name, sheet_gid = explicit_sheet_name, None
        else:
            if search is not None:
                base_name = build_search_tab_name(search.query, search.created_at)
            else:
                base_name = build_generic_tab_name(settings.google_sheets_default_sheet_name)
            result = service.append_leads_to_new_tab(spreadsheet_id, base_name, leads)
            rows_written, sheet_name, sheet_gid = (
                result.rows_written,
                result.sheet_name,
                result.sheet_gid,
            )
    except GoogleSheetsNotConfiguredError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
    except GoogleSheetsError as exc:
        # Upstream failure: nothing to do with the caller's request.
        log_event(
            "google_sheets_export_failed",
            workspace_id=user.workspace_id,
            spreadsheet_id=spreadsheet_id,
            sheet_name=explicit_sheet_name or (search.query if search else None),
            leads=len(leads),
        )
        raise HTTPException(status.HTTP_502_BAD_GATEWAY, str(exc)) from exc

    spreadsheet_url = f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"
    if sheet_gid is not None:
        spreadsheet_url = f"{spreadsheet_url}#gid={sheet_gid}"
    return SheetsExportResponse(
        rows_written=rows_written,
        sheet_name=sheet_name,
        spreadsheet_url=spreadsheet_url,
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
            "findings": audit.findings,
            "screenshots": [
                {
                    "index": i,
                    "url": s.get("url"),
                    "kind": s.get("kind"),
                    "width": s.get("width"),
                    "height": s.get("height"),
                    "bytes": s.get("bytes"),
                    "http_status": s.get("http_status"),
                    "captured_at": s.get("captured_at"),
                }
                for i, s in enumerate(audit.screenshots or [])
            ],
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


@router.get("/{lead_id}/audit/screenshots/{index}")
def lead_audit_screenshot(
    lead_id: int,
    index: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Descarga autenticada de una captura de evidencia (F5, D5.4).

    El path físico nunca sale en la API: solo metadatos + este endpoint."""
    from fastapi.responses import FileResponse

    from app.services.screenshot_service import resolve_screenshot_path

    lead = LeadRepository(db).get_for_workspace(user.workspace_id, lead_id)
    if lead is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lead no encontrado")
    audit = AuditRepository(db).latest_for_lead(lead.id)
    shots = (audit.screenshots or []) if audit is not None else []
    if index < 0 or index >= len(shots):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Captura no encontrada")
    path = resolve_screenshot_path(shots[index].get("path") or "")
    if path is None or not path.exists():
        # El archivo se borró fuera de banda: no inventamos nada, avisamos 404.
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Archivo de captura no disponible")
    return FileResponse(path, media_type="image/jpeg", filename=path.name)


# ------------------------------------------------------------- bulk actions --
@router.post("/bulk", response_model=LeadsBulkResponse)
def leads_bulk_action(
    payload: LeadsBulkRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LeadsBulkResponse:
    """Acciones masivas sobre leads seleccionados (Fase 4). Nunca borra datos:
    "archive" mueve a ARCHIVED, "unarchive" devuelve a NEW."""
    from app.core.enums import LeadStatus

    repo = LeadRepository(db)
    updated = 0
    skipped: list[int] = []
    for lead_id in payload.ids:
        lead = repo.get_for_workspace(user.workspace_id, lead_id)
        if lead is None:
            skipped.append(lead_id)
            continue
        if payload.action == "set_status":
            valid = {s.value for s in LeadStatus}
            if payload.status not in valid:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, f"status inválido: {payload.status}")
            lead.status = payload.status  # type: ignore[assignment]
        elif payload.action == "archive":
            lead.status = LeadStatus.ARCHIVED.value
        elif payload.action == "unarchive":
            lead.status = LeadStatus.NEW.value
        elif payload.action in ("add_tag", "remove_tag"):
            tag = (payload.tag or "").strip().lower()
            if not tag:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "tag vacío")
            current = {t for t in (lead.tags or "").split(",") if t}
            if payload.action == "add_tag":
                current.add(tag)
            else:
                current.discard(tag)
            lead.tags = f",{','.join(sorted(current))}," if current else None
        elif payload.action == "assign_owner":
            owner = (payload.owner or "").strip()
            if not owner:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "owner vacío")
            lead.owner_name = owner
        elif payload.action == "clear_owner":
            lead.owner_name = None
        db.add(lead)
        updated += 1
    db.commit()
    log_event("leads_bulk", workspace_id=user.workspace_id, action=payload.action, updated=updated)
    return LeadsBulkResponse(updated=updated, skipped=skipped)


@router.post("/bulk-proposals", response_model=BulkProposalsResponse)
def leads_bulk_proposals(
    payload: LeadsBulkRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BulkProposalsResponse:
    """Genera propuestas para varios leads. Respeta el guardrail: solo las crea
    en READY_FOR_REVIEW — enviar sigue requiriendo aprobación humana."""
    service = ProposalService(db)
    repo = LeadRepository(db)
    created: list[int] = []
    skipped: list[dict[str, Any]] = []
    for lead_id in payload.ids:
        lead = repo.get_for_workspace(user.workspace_id, lead_id)
        if lead is None:
            skipped.append({"lead_id": lead_id, "reason": "no encontrado"})
            continue
        try:
            service.generate(user.workspace_id, lead_id)
            created.append(lead_id)
        except Exception as exc:  # noqa: BLE001
            skipped.append({"lead_id": lead_id, "reason": str(exc)[:200]})
    db.commit()
    log_event("leads_bulk_proposals", workspace_id=user.workspace_id,
              created=len(created), skipped=len(skipped))
    return BulkProposalsResponse(created=created, skipped=skipped)


# ------------------------------------------------------------- activity ------
@router.get("/{lead_id}/activity", response_model=LeadActivityOut)
def lead_activity(
    lead_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> LeadActivityOut:
    """Timeline de evidencias reales del lead: creado, auditorías, propuestas y
    eventos de email — nada sintético."""
    from sqlalchemy import select

    from app.models.emailing import Email, EmailEvent, Proposal
    from app.models.website import WebsiteAudit

    lead = LeadRepository(db).get_for_workspace(user.workspace_id, lead_id)
    if lead is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Lead no encontrado")

    items: list[LeadActivityItem] = [
        LeadActivityItem(ts=lead.created_at, kind="created", label="Lead creado desde Google Places"),
    ]
    for audit in db.scalars(
        select(WebsiteAudit)
        .where(WebsiteAudit.lead_id == lead_id)
        .order_by(WebsiteAudit.created_at.desc())
    ).all():
        items.append(LeadActivityItem(
            ts=audit.created_at, kind="audited",
            label=f"Website auditado · score {audit.overall_score}/10",
            detail=audit.url,
        ))
    for proposal in db.scalars(
        select(Proposal).where(Proposal.lead_id == lead_id).order_by(Proposal.updated_at.desc())
    ).all():
        items.append(LeadActivityItem(
            ts=proposal.updated_at, kind="proposal",
            label=f"Propuesta · {proposal.status}",
            detail=proposal.subject,
        ))
    for event in db.scalars(
        select(EmailEvent)
        .join(Email, EmailEvent.email_id == Email.id)
        .where(Email.lead_id == lead_id)
        .order_by(EmailEvent.occurred_at.desc())
    ).all():
        items.append(LeadActivityItem(
            ts=event.occurred_at, kind="email",
            label=f"Email · {event.event_type}",
            detail=(event.detail or "")[:160] or None,
        ))
    items.sort(key=lambda i: i.ts or lead.created_at, reverse=True)
    return LeadActivityOut(items=items)
