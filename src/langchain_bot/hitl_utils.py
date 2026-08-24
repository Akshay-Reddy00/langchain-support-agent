import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from langgraph.types import Command

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "ecommerce.db"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def create_pending_action(
    *,
    thread_id: str,
    user_email: str,
    action_type: str,
    order_id: int,
    product_name: str | None,
    reason: str | None,
) -> int:
    """Create a PENDING human-review action."""

    now = _now()

    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            """
            INSERT INTO pending_actions (
                thread_id,
                user_email,
                action_type,
                order_id,
                product_name,
                reason,
                status,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, 'PENDING', ?, ?)
            """,
            (
                thread_id,
                user_email,
                action_type,
                order_id,
                product_name,
                reason,
                now,
                now,
            ),
        )

        conn.commit()

        return cursor.lastrowid


def update_pending_action(
    action_id: int,
    status: str,
) -> None:
    """Update the status of a pending action."""

    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            UPDATE pending_actions
            SET status = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                status,
                _now(),
                action_id,
            ),
        )

        conn.commit()


def get_pending_action(action_id: int):
    """Return one pending action."""

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        return conn.execute(
            """
            SELECT *
            FROM pending_actions
            WHERE id = ?
            """,
            (action_id,),
        ).fetchone()


def list_pending_actions():
    """Return all pending human-review actions."""

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        return conn.execute("""
            SELECT *
            FROM pending_actions
            WHERE status = 'PENDING'
            ORDER BY created_at ASC
            """).fetchall()


def resume_with_decision(
    *,
    agent,
    thread_id: str,
    decision: str,
):
    """Resume a paused LangGraph thread with an admin decision."""

    if decision not in {"approve", "reject"}:
        raise ValueError("decision must be 'approve' or 'reject'")

    config = {
        "configurable": {
            "thread_id": thread_id,
        }
    }

    return agent.invoke(
        Command(
            resume={
                "decisions": [
                    {
                        "type": decision,
                    }
                ]
            }
        ),
        config=config,
    )
