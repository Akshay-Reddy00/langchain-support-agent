import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from langgraph.types import Command
from langchain_bot.context import SessionContext

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


def _get_interrupt_id(agent, thread_id: str) -> str:
    """Get the active LangGraph interrupt ID for a paused thread."""

    config = {
        "configurable": {
            "thread_id": thread_id,
        }
    }

    state = agent.get_state(config)

    if not state.tasks:
        raise ValueError(
            f"Thread '{thread_id}' is not currently paused for human review."
        )

    for task in state.tasks:
        if task.interrupts:
            return task.interrupts[0].id

    raise ValueError(f"No active HITL interrupt found for thread '{thread_id}'.")


def resume_with_decision(
    *,
    agent,
    action_id: int,
    decision: str,
):
    """Resume the customer thread for a pending admin action."""

    if decision not in {"approve", "reject"}:
        raise ValueError("decision must be 'approve' or 'reject'")

    action = get_pending_action(action_id)

    if action is None:
        raise ValueError(f"Pending action #{action_id} was not found.")

    if action["status"] != "PENDING":
        raise ValueError(
            f"Pending action #{action_id} is already " f"{action['status']}."
        )

    thread_id = action["thread_id"]
    user_email = action["user_email"]

    # thread_id format:
    # user_email:conversation_id
    prefix = f"{user_email}:"

    if not thread_id.startswith(prefix):
        raise ValueError("Pending action has an invalid thread_id.")

    conversation_id = thread_id[len(prefix) :]

    context = SessionContext(
        user_email=user_email,
        conversation_id=conversation_id,
        role="customer",
    )

    config = {
        "configurable": {
            "thread_id": thread_id,
        }
    }

    interrupt_id = _get_interrupt_id(
        agent,
        thread_id,
    )

    # The actual HITL decision resumes the original
    # LangGraph execution.
    result = agent.invoke(
        Command(
            resume={
                interrupt_id: {
                    "decisions": [
                        {
                            "type": decision,
                        }
                    ]
                }
            }
        ),
        config=config,
        context=context,
    )

    update_pending_action(
        action_id,
        "APPROVED" if decision == "approve" else "REJECTED",
    )

    return result


def handle_interrupt(
    *,
    interrupt,
    user_email: str,
    thread_id: str,
) -> list[int]:
    """Persist interrupted actions as PENDING admin actions."""

    action_ids = []

    value = interrupt.value

    for action_request in value.get("action_requests", []):
        name = action_request["name"]
        args = action_request.get("args", {})

        if name != "create_return_action":
            continue

        action_id = create_pending_action(
            thread_id=thread_id,
            user_email=user_email,
            action_type="CREATE_RETURN",
            order_id=int(args["order_id"]),
            product_name=args.get("product_name"),
            reason=args.get("reason"),
        )

        action_ids.append(action_id)

    return action_ids
