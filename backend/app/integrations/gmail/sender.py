"""Gmail API message sender + offline mock (spec §43, §85).

Building the raw MIME is provider-agnostic; `send_message` requires a valid
access token. When sending is disabled (mock mode / tests) nothing leaves the
machine — use MockGmailSender instead.
"""
from __future__ import annotations

import base64
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import httpx


def build_raw_message(
    to_email: str,
    from_email: str,
    subject: str,
    body_html: str | None,
    body_plain: str | None,
    reply_to: str | None = None,
) -> str:
    message = MIMEMultipart("alternative")
    message["To"] = to_email
    message["From"] = from_email
    message["Subject"] = subject
    if reply_to:
        message["Reply-To"] = reply_to
    if body_plain:
        message.attach(MIMEText(body_plain, "plain", "utf-8"))
    if body_html:
        message.attach(MIMEText(body_html, "html", "utf-8"))
    return base64.urlsafe_b64encode(message.as_bytes()).decode()


def send_message(access_token: str, raw_message: str, user_id: str = "me") -> dict:
    """Send through the Gmail API (REST). Returns the API response dict."""
    response = httpx.post(
        f"https://gmail.googleapis.com/gmail/v1/users/{user_id}/messages/send",
        headers={
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        },
        json={"raw": raw_message},
        timeout=45,
    )
    if response.status_code != 200:
        raise GmailSendError(f"Gmail send failed ({response.status_code}): {response.text[:300]}")
    return response.json()


class GmailSendError(Exception):
    pass


class MockGmailSender:
    """Deterministic offline sender used when ALLOW_MOCK_EMAIL_SENDING=true and
    no live account is configured. Records sends in memory (tests/demo)."""

    def __init__(self) -> None:
        self.sent: list[dict] = []

    def send(self, to_email: str, from_email: str, subject: str, body_html: str | None,
             body_plain: str | None) -> dict:
        record = {
            "to": to_email,
            "from": from_email,
            "subject": subject,
            "body_html": body_html,
            "body_plain": body_plain,
        }
        self.sent.append(record)
        return {"id": f"mock-{len(self.sent)}", "threadId": f"mock-thread-{len(self.sent)}"}
