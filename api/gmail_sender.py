from __future__ import annotations

import base64
import os
from email.mime.text import MIMEText

from api.config import get_settings

SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def get_credentials(token_file: str | None = None):
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials

    settings = get_settings()
    token_path = token_file or settings.gmail_token_file

    if not os.path.exists(token_path):
        raise FileNotFoundError(
            f"{token_path} not found. Run `python api/get_gmail_token.py` first."
        )

    creds = Credentials.from_authorized_user_file(token_path, SCOPES)
    if not creds.valid:
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            with open(token_path, "w", encoding="utf-8") as token_file:
                token_file.write(creds.to_json())
        else:
            raise RuntimeError(
                f"{token_path} is invalid and cannot be refreshed. "
                "Recreate it with `python api/get_gmail_token.py`."
            )

    return creds


def create_message(to_email: str, subject: str, body: str) -> dict[str, str]:
    message = MIMEText(body, "plain", "utf-8")
    message["to"] = to_email
    message["subject"] = subject
    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")
    return {"raw": raw_message}


def send_email(to_email: str, subject: str, body: str) -> str:
    from googleapiclient.discovery import build

    service = build("gmail", "v1", credentials=get_credentials())
    message = create_message(to_email, subject, body)
    sent_message = service.users().messages().send(
        userId=get_settings().gmail_default_sender,
        body=message,
    ).execute()
    return str(sent_message.get("id"))
