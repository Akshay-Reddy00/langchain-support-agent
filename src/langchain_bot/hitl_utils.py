import sqlite3
from datetime import datetime, timezone
from pathlib import Path
import json

from langgraph.types import Command
from langchain_bot.context import SessionContext
from langchain_bot.gmail_tools import send_and_log_email

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


def save_resumed_response(
    *,
    conversation_id: str,
    user_email: str,
    result,
) -> None:
    """Save the final AI response from a resumed HITL workflow."""

    messages = result.get(
        "messages",
        [],
    )

    response = ""

    for message in reversed(messages):
        if message.type == "ai" and message.content:
            response = message.content
            break

    if not response:
        return

    project_root = Path(__file__).resolve().parents[2]

    db_path = project_root / "conversations.db"

    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            """
            SELECT messages
            FROM conversations
            WHERE id = ?
              AND user_email = ?
            """,
            (
                conversation_id,
                user_email,
            ),
        ).fetchone()

        if row is None:
            return

        conversation_messages = json.loads(row[0])

        conversation_messages.append(
            {
                "role": "assistant",
                "content": response,
            }
        )

        conn.execute(
            """
            UPDATE conversations
            SET messages = ?
            WHERE id = ?
              AND user_email = ?
            """,
            (
                json.dumps(conversation_messages),
                conversation_id,
                user_email,
            ),
        )

        conn.commit()


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

    # Resume the original LangGraph execution with the admin decision.
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

    # Update the pending action status only after resume succeeds.
    final_status = "APPROVED" if decision == "approve" else "REJECTED"

    update_pending_action(
        action_id,
        final_status,
    )

    # Save the final assistant response to the customer conversation.
    save_resumed_response(
        conversation_id=conversation_id,
        user_email=user_email,
        result=result,
    )

    # Get the customer's database user ID for email logging.
    with sqlite3.connect(DB_PATH) as conn:
        user_row = conn.execute(
            """
            SELECT id
            FROM users
            WHERE email = ?
              AND role = 'customer'
            """,
            (user_email,),
        ).fetchone()

    # Send an email notification after the admin decision.
    if user_row is not None:
        user_id = user_row[0]

        action_type = action["action_type"]
        order_id = action["order_id"]
        product_name = action["product_name"]

        if action_type == "CREATE_RETURN":

            if decision == "approve":
                subject = f"Return Request Approved - Order #{order_id}"

                body = (
                    "Hello,\n\n"
                    f"Your return request for "
                    f"'{product_name}' from order #{order_id} "
                    "has been approved.\n\n"
                    "Our support team will process the next steps "
                    "for your return.\n\n"
                    "Thank you,\n"
                    "LangChain Support Team"
                )

                email_type = "RETURN_APPROVED"

            else:
                subject = f"Return Request Rejected - Order #{order_id}"

                body = (
                    "Hello,\n\n"
                    f"Your return request for "
                    f"'{product_name}' from order #{order_id} "
                    "has been rejected after review.\n\n"
                    "If you need additional assistance, please "
                    "contact customer support.\n\n"
                    "Thank you,\n"
                    "LangChain Support Team"
                )

                email_type = "RETURN_REJECTED"

        elif action_type == "CANCEL_ORDER":

            if decision == "approve":
                subject = f"Order #{order_id} Cancellation Approved"

                body = (
                    "Hello,\n\n"
                    f"Your request to cancel order #{order_id} "
                    "has been approved and processed.\n\n"
                    "Thank you,\n"
                    "LangChain Support Team"
                )

                email_type = "CANCELLATION_APPROVED"

            else:
                subject = f"Order #{order_id} Cancellation Rejected"

                body = (
                    "Hello,\n\n"
                    f"Your request to cancel order #{order_id} "
                    "has been rejected after review.\n\n"
                    "If you need additional assistance, please "
                    "contact customer support.\n\n"
                    "Thank you,\n"
                    "LangChain Support Team"
                )

                email_type = "CANCELLATION_REJECTED"

        else:
            subject = None
            body = None
            email_type = None

        if subject and body and email_type:
            try:
                send_and_log_email(
                    user_id=user_id,
                    to_email=user_email,
                    subject=subject,
                    body=body,
                    email_type=email_type,
                )
            except Exception as exc:
                # Email failure should not undo an already completed
                # admin decision.
                print(f"Email notification failed for " f"action #{action_id}: {exc}")

    return result


def find_existing_pending_action(
    *,
    thread_id: str,
    action_type: str,
    order_id: int,
    product_name: str | None,
):
    """Return an existing matching pending action, if one exists."""

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        return conn.execute(
            """
            SELECT *
            FROM pending_actions
            WHERE thread_id = ?
              AND action_type = ?
              AND order_id = ?
              AND (
                    product_name = ?
                    OR (
                        product_name IS NULL
                        AND ? IS NULL
                    )
                  )
              AND status = 'PENDING'
            ORDER BY id DESC
            LIMIT 1
            """,
            (
                thread_id,
                action_type,
                order_id,
                product_name,
                product_name,
            ),
        ).fetchone()


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

        if name == "cancel_order_action":

            action_type = "CANCEL_ORDER"
            order_id = int(args["order_id"])
            product_name = None
            reason = None

        elif name == "create_return_action":

            action_type = "CREATE_RETURN"
            order_id = int(args["order_id"])
            product_name = args.get("product_name")
            reason = args.get("reason")

        else:
            continue

        existing_action = find_existing_pending_action(
            thread_id=thread_id,
            action_type=action_type,
            order_id=order_id,
            product_name=product_name,
        )

        if existing_action is not None:
            action_ids.append(existing_action["id"])
            continue

        action_id = create_pending_action(
            thread_id=thread_id,
            user_email=user_email,
            action_type=action_type,
            order_id=order_id,
            product_name=product_name,
            reason=reason,
        )

        action_ids.append(action_id)

    return action_ids
