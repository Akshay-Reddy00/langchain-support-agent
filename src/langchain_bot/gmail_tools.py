import base64
import logging
import os
import sqlite3

from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

from langchain_bot.action_tools import DB_PATH

load_dotenv()

# Allow HTTP OAuth redirect for localhost development only.
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"


PROJECT_ROOT = Path(__file__).resolve().parents[2]

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
]


# ---------------------------------------------------------
# Email logger
# ---------------------------------------------------------

LOGS_DIR = PROJECT_ROOT / "logs"
LOGS_DIR.mkdir(exist_ok=True)

EMAIL_LOG_PATH = LOGS_DIR / "email.log"

email_logger = logging.getLogger("langchain_bot.email")
email_logger.setLevel(logging.INFO)
email_logger.propagate = False


if not email_logger.handlers:
    email_handler = logging.FileHandler(
        EMAIL_LOG_PATH,
        encoding="utf-8",
    )

    email_formatter = logging.Formatter("%(asctime)s | %(levelname)s | %(message)s")

    email_handler.setFormatter(email_formatter)

    email_logger.addHandler(email_handler)


# ---------------------------------------------------------
# Gmail authentication
# ---------------------------------------------------------


def get_credentials_path() -> Path:
    """Return the Google OAuth client credentials path."""

    return Path(
        os.getenv(
            "GOOGLE_CREDENTIALS_PATH",
            PROJECT_ROOT / "credentials.json",
        )
    )


def get_token_path() -> Path:
    """Return the saved Gmail OAuth token path."""

    return Path(
        os.getenv(
            "GOOGLE_TOKEN_PATH",
            PROJECT_ROOT / "token.json",
        )
    )


def get_gmail_credentials() -> Credentials:
    """Load and refresh saved Gmail OAuth credentials."""

    token_path = get_token_path()

    if not token_path.exists():
        raise FileNotFoundError(
            "Gmail token.json was not found. " "Run authorize_gmail.py first."
        )

    credentials = Credentials.from_authorized_user_file(
        str(token_path),
        GMAIL_SCOPES,
    )

    if credentials.expired and credentials.refresh_token:
        credentials.refresh(Request())

        token_path.write_text(
            credentials.to_json(),
            encoding="utf-8",
        )

    if not credentials.valid:
        raise RuntimeError(
            "Gmail credentials are invalid. " "Run authorize_gmail.py again."
        )

    return credentials


def get_gmail_service():
    """Return an authenticated Gmail API service."""

    credentials = get_gmail_credentials()

    return build(
        "gmail",
        "v1",
        credentials=credentials,
    )


# ---------------------------------------------------------
# Gmail sending
# ---------------------------------------------------------


def send_email(
    *,
    to_email: str,
    subject: str,
    body: str,
) -> str:
    """Send a plain-text email using the Gmail API."""

    try:
        message = EmailMessage()

        message["To"] = to_email
        message["Subject"] = subject

        message.set_content(body)

        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

        service = get_gmail_service()

        result = (
            service.users()
            .messages()
            .send(
                userId="me",
                body={
                    "raw": encoded_message,
                },
            )
            .execute()
        )

        message_id = result["id"]

        email_logger.info(
            "EMAIL SENT | to=%s | subject=%s | gmail_message_id=%s",
            to_email,
            subject,
            message_id,
        )

        return message_id

    except Exception as exc:

        email_logger.exception(
            "EMAIL FAILED | to=%s | subject=%s | error=%s",
            to_email,
            subject,
            exc,
        )

        raise


# ---------------------------------------------------------
# Database audit logging
# ---------------------------------------------------------


def log_email(
    *,
    user_id: int,
    email: str,
    subject: str,
    body: str,
    email_type: str,
) -> None:
    """Record a successfully sent email in email_logs."""

    body_preview = body[:500]

    sent_at = datetime.now(timezone.utc).isoformat()

    with sqlite3.connect(DB_PATH) as conn:

        conn.execute(
            """
            INSERT INTO email_logs (
                user_id,
                email,
                subject,
                body_preview,
                email_type,
                sent_at
            )
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                user_id,
                email,
                subject,
                body_preview,
                email_type,
                sent_at,
            ),
        )

        conn.commit()

    email_logger.info(
        "EMAIL DATABASE LOGGED | user_id=%s | to=%s | type=%s",
        user_id,
        email,
        email_type,
    )


# ---------------------------------------------------------
# Send + database log
# ---------------------------------------------------------


def send_and_log_email(
    *,
    user_id: int,
    to_email: str,
    subject: str,
    body: str,
    email_type: str,
) -> str:
    """Send an email through Gmail and log it in the database."""

    message_id = send_email(
        to_email=to_email,
        subject=subject,
        body=body,
    )

    log_email(
        user_id=user_id,
        email=to_email,
        subject=subject,
        body=body,
        email_type=email_type,
    )

    return message_id
