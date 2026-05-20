"""
drive_archiver.py (BONUS)
Uploads the generated PDF to a Google Drive folder and returns the shareable URL.
Requires: GOOGLE_SERVICE_ACCOUNT_FILE, GOOGLE_DRIVE_FOLDER_ID in settings.
"""
import os
from django.conf import settings

SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def _get_service():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    sa_file = settings.GOOGLE_SERVICE_ACCOUNT_FILE
    if not sa_file:
        raise ValueError("GOOGLE_SERVICE_ACCOUNT_FILE not configured")

    creds = service_account.Credentials.from_service_account_file(sa_file, scopes=SCOPES)
    return build("drive", "v3", credentials=creds)


def archive_to_drive(report_path: str, lead: dict) -> str:
    """Upload PDF to Drive folder and return the view URL."""
    folder_id = settings.GOOGLE_DRIVE_FOLDER_ID
    if not folder_id:
        print("  ⚠ Drive archiving skipped: GOOGLE_DRIVE_FOLDER_ID not set")
        return ""

    from googleapiclient.http import MediaFileUpload

    service  = _get_service()
    filename = os.path.basename(report_path)

    file_metadata = {
        "name": filename,
        "parents": [folder_id],
    }
    media = MediaFileUpload(report_path, mimetype="application/pdf", resumable=True)

    uploaded = (
        service.files()
        .create(body=file_metadata, media_body=media, fields="id, webViewLink")
        .execute()
    )

    # Make the file readable by anyone with the link
    service.permissions().create(
        fileId=uploaded["id"],
        body={"type": "anyone", "role": "reader"},
    ).execute()

    url = uploaded.get("webViewLink", "")
    print(f"  ✓ Archived to Google Drive: {url}")
    return url
