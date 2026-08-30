import logging
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from langchain_google_community import GmailToolkit

from langchain_bot.action_tools import DB_PATH

load_dotenv()

# Allow HTTP OAuth redirect for localhost development only.
os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"


PROJECT_ROOT = Path(__file__).resolve().parents[2]

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
]


logger = logging.getLogger("email")


def get_credentials_path() -> Path:
    """Return the Google OAuth client credentials path."""

    return Path(
        os.getenv(
            "GOOGLE_CREDENTIALS_PATH",
            str(PROJECT_ROOT / "credentials.json"),
        )
    )


def get_token_path() -> Path:
    """Return the saved Gmail OAuth token path."""

    return Path(
        os.getenv(
            "GOOGLE_TOKEN_PATH",
            str(PROJECT_ROOT / "token.json"),
        )
    )


def get_gmail_credentials() -> Credentials:
    """Load and refresh saved Gmail OAuth credentials."""

    token_path = get_token_path()

    if not token_path.exists():
        raise FileNotFoundError(
            "Gmail token.json was not found. "
            "Complete the Gmail OAuth authorization flow first."
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
            "Gmail credentials are invalid. "
            "Complete the Gmail OAuth authorization flow again."
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


def get_gmail_send_tool():
    """Return the LangChain Gmail send tool."""

    toolkit = GmailToolkit(
        api_resource=get_gmail_service(),
    )

    tools = toolkit.get_tools()

    for tool in tools:
        if tool.name == "send_gmail_message":
            return tool

    raise RuntimeError("send_gmail_message tool was not found in GmailToolkit.")


def send_email(
    *,
    to_email: str,
    subject: str,
    body: str,
) -> str:
    """Send an email using LangChain GmailToolkit."""

    send_tool = get_gmail_send_tool()

    result = send_tool.invoke(
        {
            "message": body,
            "to": to_email,
            "subject": subject,
        }
    )

    logger.info(
        "EMAIL SENT | to=%s | subject=%s | result=%s",
        to_email,
        subject,
        result,
    )

    return str(result)


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

    logger.info(
        "EMAIL DATABASE LOGGED | user_id=%s | to=%s | type=%s",
        user_id,
        email,
        email_type,
    )


def send_and_log_email(
    *,
    user_id: int,
    to_email: str,
    subject: str,
    body: str,
    email_type: str,
) -> str:
    """Send an email through GmailToolkit and log it in the database."""

    result = send_email(
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

    return result
