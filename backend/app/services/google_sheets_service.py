"""Google Sheets export (service account append).

Replaces the previous n8n workflow (`googleSheets` append node authenticated
with `serviceAccount`): leads are appended straight from the backend using a
service account key that lives in the environment as a **single-line JSON
string**, so no key file ever touches the filesystem.

Security: the key material (`GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON`) and the
resulting credentials are never logged, serialized, or returned by any
endpoint — only counts and error codes are.

The Google client libraries are imported lazily so the rest of the app keeps
booting on images that don't ship them yet.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Iterable, Sequence

from app.core.config import settings
from app.core.logging import log_event
from app.models.lead import Lead

logger = logging.getLogger("avascho.google_sheets")

SHEETS_SCOPES = ("https://www.googleapis.com/auth/spreadsheets",)

# Value written in the `source` column: the Lead model has no equivalent field.
LEAD_SOURCE = "AvaScho"

# Column order is part of the contract with the sheet — do not reorder.
SHEET_COLUMNS: tuple[str, ...] = (
    "business_name",
    "category",
    "address",
    "city",
    "country",
    "phone",
    "website",
    "email",
    "google_maps_url",
    "place_id",
    "rating",
    "reviews_count",
    "latitude",
    "longitude",
    "business_status",
    "source",
)


class GoogleSheetsError(Exception):
    """Any failure while talking to the Google Sheets API."""


class GoogleSheetsNotConfiguredError(GoogleSheetsError):
    """The service account JSON is missing/unusable in the environment."""


class GoogleSheetsExportService:
    """Append leads to a spreadsheet owned/shared with the service account."""

    def __init__(self) -> None:
        # Configured == we have something to authenticate with. The actual
        # credentials are only built (and validated) on first use so that
        # importing this module never raises.
        self._configured = bool(settings.google_sheets_service_account_json.strip())
        self._credentials: Any = None

    # ------------------------------------------------------------- setup -----
    @property
    def is_configured(self) -> bool:
        return self._configured

    def _require_libraries(self) -> None:
        try:
            import googleapiclient  # noqa: F401
            from google.oauth2.service_account import Credentials  # noqa: F401
        except ImportError as exc:  # pragma: no cover - depends on the image
            raise GoogleSheetsNotConfiguredError(
                "Faltan las librerías de Google (google-api-python-client / google-auth). "
                "Instalalas con `pip install -r requirements.txt`."
            ) from exc

    def _get_credentials(self) -> Any:
        """Build service-account credentials from the JSON kept in settings."""
        if not self._configured:
            raise GoogleSheetsNotConfiguredError(
                "GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON está vacío. Pegá el JSON completo "
                "de la service account (una sola línea) en el .env del backend."
            )
        if self._credentials is not None:
            return self._credentials
        self._require_libraries()
        from google.oauth2.service_account import Credentials

        try:
            info = json.loads(settings.google_sheets_service_account_json)
        except (ValueError, TypeError) as exc:
            # Never echo the payload: it contains the private key.
            raise GoogleSheetsNotConfiguredError(
                "GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON no es un JSON válido (debe ser el "
                "archivo de la service account comprimido en una sola línea)."
            ) from exc
        try:
            self._credentials = Credentials.from_service_account_info(
                info, scopes=list(SHEETS_SCOPES)
            )
        except Exception as exc:  # noqa: BLE001 - key unusable, never echoed
            raise GoogleSheetsNotConfiguredError(
                f"No pudimos autenticar la service account ({type(exc).__name__}). Revisá que "
                "GOOGLE_SHEETS_SERVICE_ACCOUNT_JSON sea el JSON completo de la key (con la "
                "private_key intacta y las \\n escapadas)."
            ) from exc
        return self._credentials

    def _client(self) -> Any:
        from googleapiclient.discovery import build

        return build("sheets", "v4", credentials=self._get_credentials())

    # ------------------------------------------------------------- rows ------
    @staticmethod
    def _lead_row(lead: Lead) -> list[Any]:
        """One spreadsheet row, in SHEET_COLUMNS order.

        Missing attributes degrade to an empty cell instead of blowing up, so a
        schema change can't break an export.
        """
        row: list[Any] = []
        for column in SHEET_COLUMNS:
            if column == "source":
                row.append(LEAD_SOURCE)
                continue
            value = getattr(lead, column, None)
            row.append("" if value is None else value)
        return row

    # ------------------------------------------------------------- API -------
    def append_leads(
        self,
        spreadsheet_id: str,
        sheet_name: str,
        leads: Sequence[Lead] | Iterable[Lead],
    ) -> int:
        """Append `leads` to `sheet_name` and return how many rows were written.

        A header row is written first when the sheet is still empty. Nothing is
        sent when `leads` is empty.
        """
        if not spreadsheet_id:
            raise GoogleSheetsError("No se indicó ningún spreadsheet_id.")
        if not sheet_name:
            raise GoogleSheetsError("No se indicó ningún nombre de hoja.")

        lead_list = list(leads)
        if not lead_list:
            log_event(
                "google_sheets_append_skipped",
                spreadsheet_id=spreadsheet_id,
                sheet_name=sheet_name,
                rows=0,
            )
            return 0

        rows = [self._lead_row(lead) for lead in lead_list]
        service = self._client()
        try:
            if self._sheet_is_empty(service, spreadsheet_id, sheet_name):
                rows.insert(0, list(SHEET_COLUMNS))
            service.spreadsheets().values().append(
                spreadsheetId=spreadsheet_id,
                range=f"{sheet_name}!A1",
                valueInputOption="RAW",
                insertDataOption="INSERT_ROWS",
                body={"values": rows},
            ).execute()
        except Exception as exc:  # noqa: BLE001 - translated below
            raise self._translate_error(exc) from exc

        log_event(
            "google_sheets_append_ok",
            spreadsheet_id=spreadsheet_id,
            sheet_name=sheet_name,
            rows=len(lead_list),
        )
        return len(lead_list)

    @staticmethod
    def _sheet_is_empty(service: Any, spreadsheet_id: str, sheet_name: str) -> bool:
        """True when the sheet has no data in its first cell yet."""
        response = (
            service.spreadsheets()
            .values()
            .get(spreadsheetId=spreadsheet_id, range=f"{sheet_name}!A1:A1")
            .execute()
        )
        values = response.get("values") or []
        return not any(any(str(cell).strip() for cell in row) for row in values)

    # ------------------------------------------------------------- errors ----
    @staticmethod
    def _translate_error(exc: Exception) -> GoogleSheetsError:
        """Map a googleapiclient HttpError onto an actionable message.

        The raw response body is never included: it can echo request details and
        we only need the status to explain what went wrong.
        """
        if isinstance(exc, GoogleSheetsError):
            return exc
        status_code = 0
        try:
            from googleapiclient.errors import HttpError
        except ImportError:  # pragma: no cover
            HttpError = None  # type: ignore[assignment]
        if HttpError is not None and isinstance(exc, HttpError):
            raw_status = getattr(getattr(exc, "resp", None), "status", None)
            try:
                status_code = int(raw_status)
            except (TypeError, ValueError):
                status_code = 0
            if status_code == 403:
                return GoogleSheetsError(
                    "Google rechazó el acceso a la spreadsheet (403). Verificá que la hoja "
                    "esté compartida con el client_email de la service account con rol "
                    "Editor y que la API de Google Sheets esté habilitada en el proyecto."
                )
            if status_code == 404:
                return GoogleSheetsError(
                    "No encontramos la spreadsheet o la hoja indicada (404). Revisá "
                    "GOOGLE_SHEETS_DEFAULT_SPREADSHEET_ID y el nombre de la hoja "
                    "(GOOGLE_SHEETS_DEFAULT_SHEET_NAME)."
                )
            return GoogleSheetsError(
                f"Google Sheets devolvió un error inesperado (status {status_code or 'desconocido'})."
            )
        return GoogleSheetsError(
            f"No se pudo escribir en Google Sheets: {type(exc).__name__}: {str(exc)[:200]}"
        )
