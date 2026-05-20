"""
sheets_logger.py (BONUS)
Appends lead data to a Google Sheet as a live leads tracker.
Requires: GOOGLE_SERVICE_ACCOUNT_FILE, GOOGLE_SHEETS_SPREADSHEET_ID in settings.
"""
from datetime import datetime
from django.conf import settings

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SHEET_RANGE = "Leads!A:H"
HEADER_ROW  = ["Timestamp", "Name", "Email", "Company", "Industry",
               "Role", "Team Size", "Report Status", "Drive URL"]


def _get_service():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    sa_file = settings.GOOGLE_SERVICE_ACCOUNT_FILE
    if not sa_file:
        raise ValueError("GOOGLE_SERVICE_ACCOUNT_FILE not configured")

    creds = service_account.Credentials.from_service_account_file(sa_file, scopes=SCOPES)
    return build("sheets", "v4", credentials=creds)


def _ensure_header(service, spreadsheet_id: str):
    """Write header row if sheet is empty."""
    result = (
        service.spreadsheets()
        .values()
        .get(spreadsheetId=spreadsheet_id, range="Leads!A1:A1")
        .execute()
    )
    if not result.get("values"):
        service.spreadsheets().values().append(
            spreadsheetId=spreadsheet_id,
            range=SHEET_RANGE,
            valueInputOption="RAW",
            body={"values": [HEADER_ROW]},
        ).execute()


def log_to_sheets(lead: dict, status: str, drive_url: str | None) -> None:
    spreadsheet_id = settings.GOOGLE_SHEETS_SPREADSHEET_ID
    if not spreadsheet_id:
        print("  ⚠ Sheets logging skipped: GOOGLE_SHEETS_SPREADSHEET_ID not set")
        return

    service = _get_service()
    _ensure_header(service, spreadsheet_id)

    row = [
        datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S"),
        lead["name"],
        lead["email"],
        lead["company"],
        lead.get("industry", ""),
        lead.get("role", ""),
        lead.get("team_size", ""),
        status,
        drive_url or "",
    ]

    service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range=SHEET_RANGE,
        valueInputOption="RAW",
        body={"values": [row]},
    ).execute()

    print(f"  ✓ Logged to Google Sheets: {lead['company']}")
