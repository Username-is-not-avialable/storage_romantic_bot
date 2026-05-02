"""Create token.json for Gmail API send scope.

Usage:
  python get_gmail_token.py
"""

from __future__ import annotations

import os.path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# If modifying scopes, delete token.json and re-authorize.
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]


def main() -> None:
    creds: Credentials | None = None

    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            try:
                # Works on local machine with browser.
                creds = flow.run_local_server(port=0)
            except OSError:
                # Fallback for headless environments.
                creds = flow.run_console()

        with open("token.json", "w", encoding="utf-8") as token_file:
            token_file.write(creds.to_json())

    print("token.json created/updated successfully.")


if __name__ == "__main__":
    main()
