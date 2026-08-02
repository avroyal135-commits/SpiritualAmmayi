"""
drive_upload.py
================
Uploads the generated video, thumbnail, and metadata JSON to Google
Drive using a Service Account, organizing files into a
Year/Month/Day/GodName folder hierarchy under a configurable root
folder.

Credentials come entirely from the environment (GitHub Secrets):

    GDRIVE_SERVICE_ACCOUNT_JSON  - the full service account JSON key
    GDRIVE_ROOT_FOLDER_ID        - the Drive folder ID to upload into

If either is missing, uploading is skipped gracefully (useful for local
test runs without Drive access).
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import config
from utils import log

_SCOPES = ["https://www.googleapis.com/auth/drive"]


class DriveUploader:
    """Thin wrapper around the Drive v3 API for this project's needs."""

    def __init__(self) -> None:
        self._service = None
        self.enabled = False
        self.root_folder_id: Optional[str] = os.environ.get(config.GDRIVE_ROOT_FOLDER_ID_ENV)
        self._folder_cache: Dict[str, str] = {}
        self._init_service()


    def _init_service(self) -> None:
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
    refresh_token = os.environ.get("GOOGLE_REFRESH_TOKEN")

    if not all([client_id, client_secret, refresh_token, self.root_folder_id]):
        log.warning("OAuth credentials not configured.")
        return

    try:
        from google.oauth2.credentials import Credentials
        from googleapiclient.discovery import build

        credentials = Credentials(
            token=None,
            refresh_token=refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=client_id,
            client_secret=client_secret,
            scopes=_SCOPES,
        )

        self._service = build(
            "drive",
            "v3",
            credentials=credentials,
            cache_discovery=False,
        )

        self.enabled = True
        log.info("Google Drive OAuth initialized.")

    except Exception as exc:
        log.error("Failed to initialize Google Drive OAuth: %s", exc)
        self.enabled = False
    # ------------------------------------------------------------------
    # Folder management
    # ------------------------------------------------------------------
    def _get_or_create_folder(self, name: str, parent_id: str) -> str:
        cache_key = f"{parent_id}/{name}"
        if cache_key in self._folder_cache:
            return self._folder_cache[cache_key]

        query = (
            f"name = '{name}' and '{parent_id}' in parents "
            "and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
        )
        results = self._service.files().list(
            q=query, spaces="drive", fields="files(id, name)"
        ).execute()
        files = results.get("files", [])
        if files:
            folder_id = files[0]["id"]
        else:
            metadata = {
                "name": name,
                "mimeType": "application/vnd.google-apps.folder",
                "parents": [parent_id],
            }
            created = self._service.files().create(body=metadata, fields="id").execute()
            folder_id = created["id"]
            log.info("Created Drive folder '%s' under parent %s", name, parent_id)

        self._folder_cache[cache_key] = folder_id
        return folder_id

    def _build_date_folder_path(self, god_name: str, when: Optional[datetime] = None) -> str:
        when = when or datetime.utcnow()
        parent = self.root_folder_id
        for part in (str(when.year), f"{when.month:02d}", f"{when.day:02d}", god_name.title()):
            parent = self._get_or_create_folder(part, parent)
        return parent

    # ------------------------------------------------------------------
    # Upload
    # ------------------------------------------------------------------
    def _upload_file(self, local_path: Path, parent_id: str, mimetype: str) -> Optional[str]:
        from googleapiclient.http import MediaFileUpload

        media = MediaFileUpload(str(local_path), mimetype=mimetype, resumable=True)
        metadata = {"name": local_path.name, "parents": [parent_id]}
        try:
            uploaded = self._service.files().create(
                body=metadata, media_body=media, fields="id, webViewLink"
            ).execute()
            log.info("Uploaded %s -> Drive file id %s", local_path.name, uploaded.get("id"))
            return uploaded.get("id")
        except Exception as exc:  # noqa: BLE001
            log.error("Failed to upload %s to Drive: %s", local_path.name, exc)
            return None

    def upload_short(
        self,
        god_name: str,
        video_path: Path,
        thumbnail_path: Path,
        metadata_path: Path,
    ) -> Dict[str, Optional[str]]:
        """
        Upload the trio of output files for one Short into the
        Year/Month/Day/God folder hierarchy. Returns a dict of Drive
        file IDs (or None for any file that failed / was skipped).
        """
        if not self.enabled:
            log.warning("Drive upload skipped (uploader not enabled).")
            return {"video": None, "thumbnail": None, "metadata": None}

        folder_id = self._build_date_folder_path(god_name)

        video_id = self._upload_file(video_path, folder_id, "video/mp4") if video_path.exists() else None
        thumb_id = self._upload_file(thumbnail_path, folder_id, "image/jpeg") if thumbnail_path.exists() else None
        meta_id = self._upload_file(metadata_path, folder_id, "application/json") if metadata_path.exists() else None

        return {"video": video_id, "thumbnail": thumb_id, "metadata": meta_id}
