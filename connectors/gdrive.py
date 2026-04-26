"""
connectors/gdrive.py
Authenticates with Google Drive via a service account and yields raw
(file_name, mime_type, bytes_content) tuples for every supported document.

Supported MIME types:
  • application/pdf
  • application/vnd.google-apps.document  (exported as text/plain)
  • text/plain
"""
from __future__ import annotations

import io
import logging
import tempfile
from pathlib import Path
from typing import Generator, Tuple

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from config import settings

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

SUPPORTED_MIME = {
    "application/pdf",
    "application/vnd.google-apps.document",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "text/plain",
}

# Google Docs must be *exported* rather than downloaded
EXPORT_MAP = {
    "application/vnd.google-apps.document": "text/plain",
}


def _build_service():
    creds = service_account.Credentials.from_service_account_file(
        settings.google_service_account_file, scopes=SCOPES
    )
    return build("drive", "v3", credentials=creds, cache_discovery=False)


def list_files(service) -> list[dict]:
    """Return all supported files from Drive (optionally scoped to a folder)."""
    mime_filter = " or ".join(f"mimeType='{m}'" for m in SUPPORTED_MIME)
    query = f"({mime_filter}) and trashed=false"

    if settings.gdrive_folder_id:
        query += f" and '{settings.gdrive_folder_id}' in parents"

    files, page_token = [], None
    while True:
        resp = (
            service.files()
            .list(
                q=query,
                spaces="drive",
                fields="nextPageToken, files(id, name, mimeType, modifiedTime)",
                pageToken=page_token,
                pageSize=100,
            )
            .execute()
        )
        files.extend(resp.get("files", []))
        page_token = resp.get("nextPageToken")
        if not page_token:
            break

    logger.info("Found %d supported files in Google Drive", len(files))
    return files


def download_file(service, file_meta: dict) -> bytes:
    """Download or export a file and return its raw bytes."""
    file_id = file_meta["id"]
    mime = file_meta["mimeType"]

    DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

    # Google Docs → export as text
    # DOCX → download raw (do NOT export)
    if mime in EXPORT_MAP and mime != DOCX_MIME:
        request = service.files().export_media(
            fileId=file_id, mimeType=EXPORT_MAP[mime]
        )
    else:
        request = service.files().get_media(fileId=file_id)

    buf = io.BytesIO()
    downloader = MediaIoBaseDownload(buf, request)
    done = False
    while not done:
        _, done = downloader.next_chunk()

    return buf.getvalue()

def fetch_documents() -> Generator[Tuple[str, str, bytes], None, None]:
    """
    Public interface used by the sync pipeline.

    Yields:
        (file_name, mime_type, raw_bytes)
    """
    service = _build_service()
    files = list_files(service)

    for meta in files:
        try:
            raw = download_file(service, meta)
            logger.info("Downloaded: %s (%s)", meta["name"], meta["mimeType"])
            yield meta["name"], meta["mimeType"], raw
        except Exception as exc:
            logger.error("Failed to download %s: %s", meta["name"], exc)