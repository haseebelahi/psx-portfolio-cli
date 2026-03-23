"""Google Drive client for syncing portfolio data across machines."""
import io
import os

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

SCOPES = ["https://www.googleapis.com/auth/drive.file"]


class DriveClient:
    def __init__(self, credentials_path: str, token_path: str):
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.service = self._authenticate()

    def _authenticate(self):
        creds = None

        if os.path.exists(self.token_path):
            creds = Credentials.from_authorized_user_file(self.token_path, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, SCOPES
                )
                creds = flow.run_local_server(port=0)

            os.makedirs(os.path.dirname(self.token_path), exist_ok=True)
            with open(self.token_path, "w") as token:
                token.write(creds.to_json())

        return build("drive", "v3", credentials=creds)

    def _get_file_id(self, remote_name: str) -> str | None:
        results = (
            self.service.files()
            .list(
                q=f"name='{remote_name}' and trashed=false",
                spaces="drive",
                fields="files(id)",
            )
            .execute()
        )
        files = results.get("files", [])
        return files[0]["id"] if files else None

    def push_file(self, local_path: str, remote_name: str) -> None:
        media = MediaFileUpload(local_path, mimetype="application/octet-stream", resumable=False)
        file_id = self._get_file_id(remote_name)
        if file_id is None:
            self.service.files().create(
                body={"name": remote_name},
                media_body=media,
                fields="id",
            ).execute()
        else:
            self.service.files().update(
                fileId=file_id,
                media_body=media,
            ).execute()

    def pull_file(self, remote_name: str, local_path: str) -> bool:
        file_id = self._get_file_id(remote_name)
        if file_id is None:
            return False

        request = self.service.files().get_media(fileId=file_id)
        buf = io.BytesIO()
        downloader = MediaIoBaseDownload(buf, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()

        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        with open(local_path, "wb") as f:
            f.write(buf.getvalue())
        return True
