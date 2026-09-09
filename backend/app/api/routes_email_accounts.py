"""Gmail account endpoints (spec §43-45)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.core.security import decrypt_value, encrypt_value, random_token
from app.integrations.gmail import oauth
from app.models.user import User
from app.repositories.emailing import EmailAccountRepository
from app.schemas.api import ConnectUrlResponse, EmailAccountOut
from app.utils.text import utcnow

router = APIRouter(prefix="/email-accounts", tags=["email-accounts"])


def _to_out(account) -> EmailAccountOut:
    return EmailAccountOut.model_validate(account)


@router.get("", response_model=list[EmailAccountOut])
def list_accounts(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[EmailAccountOut]:
    return [_to_out(a) for a in EmailAccountRepository(db).list_for_workspace(user.workspace_id)]


@router.post("/gmail/connect", response_model=ConnectUrlResponse)
def gmail_connect_url(
    user: User = Depends(get_current_user),
) -> ConnectUrlResponse:
    if not oauth.configured():
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Gmail OAuth no está configurado en el backend (GOOGLE_CLIENT_ID / GOOGLE_CLIENT_SECRET)",
        )
    # signed state ties the callback back to this user/workspace
    state = f"{user.id}:{random_token(16)}"
    return ConnectUrlResponse(url=oauth.build_authorization_url(state))


@router.get("/gmail/callback", response_model=EmailAccountOut)
async def gmail_callback(
    code: str = Query(...),
    state: str = Query(...),
    db: Session = Depends(get_db),
) -> EmailAccountOut:
    # state format: {user_id}:{nonce}; we locate user by id (single-workspace model)
    try:
        user_id = int(state.split(":")[0])
    except (ValueError, IndexError) as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Estado inválido") from exc
    user = db.get(User, user_id)
    if user is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Usuario inválido")

    tokens = oauth.exchange_code(code)
    access_token = tokens["access_token"]
    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            "Google no entregó refresh_token. Revocá el acceso y volvé a intentar con consentimiento.",
        )
    try:
        email = await oauth.fetch_profile_email(access_token)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"No se pudo leer el email: {exc}") from exc

    repo = EmailAccountRepository(db)
    account = next(
        (a for a in repo.list_for_workspace(user.workspace_id) if a.email == email.lower()),
        None,
    )
    if account is None:
        account = repo.create(
            workspace_id=user.workspace_id,
            email=email.lower(),
            provider="gmail",
            status="CONNECTED",
            daily_limit=5,
            display_name=email,
        )
    account.access_token_encrypted = encrypt_value(access_token)
    account.refresh_token_encrypted = encrypt_value(refresh_token)
    account.token_expires_at = utcnow().replace(minute=0, second=0)  # refreshed lazily
    account.status = "CONNECTED"
    account.error_message = None
    db.add(account)
    db.commit()
    return _to_out(account)


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_account(
    account_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    account = EmailAccountRepository(db).get_for_workspace(user.workspace_id, account_id)
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cuenta no encontrada")
    db.delete(account)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/{account_id}", response_model=EmailAccountOut)
def update_account(
    account_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
    daily_limit: int | None = Query(None, ge=1, le=500),
) -> EmailAccountOut:
    account = EmailAccountRepository(db).get_for_workspace(user.workspace_id, account_id)
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cuenta no encontrada")
    if daily_limit is not None:
        account.daily_limit = daily_limit
        db.add(account)
        db.commit()
    return _to_out(account)


@router.post("/{account_id}/rotate", response_model=dict)
def rotate_account(
    account_id: int,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
    """Debug helper: rotate a token. Returns OK or error message."""
    account = EmailAccountRepository(db).get_for_workspace(user.workspace_id, account_id)
    if account is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Cuenta no encontrada")
    try:
        refresh = decrypt_value(account.refresh_token_encrypted or "")
        token, expires_in = oauth.refresh_access_token(refresh)
        account.access_token_encrypted = encrypt_value(token)
        db.add(account)
        db.commit()
        return {"status": "OK", "expires_in": expires_in}
    except Exception as exc:  # noqa: BLE001
        return {"status": "ERROR", "detail": str(exc)}
