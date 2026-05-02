"""Send a test email via Gmail API using existing token.json.

Usage:
  python send_test_email.py
  python send_test_email.py --to another@example.com
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Allow running as `python scripts/send_test_email.py` from repo root.
REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from api.gmail_sender import send_email

DEFAULT_TO_EMAIL = "example@mail.com"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Send a Gmail test email.")
    parser.add_argument("--to", default=DEFAULT_TO_EMAIL, help="Recipient email.")
    parser.add_argument(
        "--subject",
        default="Тестовое письмо из romantic-storage",
        help="Email subject.",
    )
    parser.add_argument(
        "--body",
        default=(
            "Привет! Это тестовое письмо, отправленное через Gmail API "
            "из проекта romantic-storage."
        ),
        help="Email body text.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    try:
        message_id = send_email(args.to, args.subject, args.body)
        print(f"Email sent successfully. Message ID: {message_id}")
    except Exception as error:
        print(f"Gmail API error: {error}")
        raise SystemExit(1) from error


if __name__ == "__main__":
    main()
