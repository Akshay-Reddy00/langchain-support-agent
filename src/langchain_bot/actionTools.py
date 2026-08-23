import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from langchain.tools import tool, ToolRuntime

from langchain_bot.context import SessionContext

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "ecommerce.db"


@tool
def create_return_action(
    order_id: int,
    product_name: str,
    reason: str,
    runtime: ToolRuntime[SessionContext],
) -> str:
    """Create an approved return request for a product in the customer's order.

    This tool performs the actual database changes only after the agent's
    human-in-the-loop approval has been granted.

    The logged-in customer identity comes from SessionContext. Do not accept
    user_email from the model.
    """

    context = runtime.context

    if context is None:
        return "Unable to create the return because customer context is missing."

    user_email = context.user_email
    conversation_id = context.conversation_id
    thread_id = f"{user_email}:{conversation_id}"

    now = datetime.now(timezone.utc).isoformat()

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        # Find the logged-in customer.
        user = conn.execute(
            """
            SELECT id, email
            FROM users
            WHERE email = ?
              AND role = 'customer'
            """,
            (user_email,),
        ).fetchone()

        if user is None:
            return "Unable to create the return because the customer account was not found."

        # Verify the order belongs to the logged-in customer.
        order = conn.execute(
            """
            SELECT id, status
            FROM orders
            WHERE id = ?
              AND user_id = ?
            """,
            (order_id, user["id"]),
        ).fetchone()

        if order is None:
            return f"Order #{order_id} was not found for your account."

        if order["status"] not in {"SHIPPED", "DELIVERED"}:
            return (
                f"Order #{order_id} is currently {order['status']}. "
                "A return can only be created for a SHIPPED or DELIVERED order."
            )

        # Find the requested product in this order.
        item = conn.execute(
            """
            SELECT
                oi.id AS order_item_id,
                p.id AS product_id,
                p.name AS product_name
            FROM order_items oi
            JOIN products p
                ON p.id = oi.product_id
            WHERE oi.order_id = ?
              AND LOWER(p.name) = LOWER(?)
            """,
            (order_id, product_name),
        ).fetchone()

        if item is None:
            return (
                f"I could not find '{product_name}' in order #{order_id}. "
                "Please provide the exact product name from the order."
            )

        # Prevent duplicate pending/approved returns for the same item.
        existing = conn.execute(
            """
            SELECT id, status
            FROM returns
            WHERE order_id = ?
              AND order_item_id = ?
              AND user_id = ?
              AND status IN ('PENDING', 'APPROVED')
            """,
            (order_id, item["order_item_id"], user["id"]),
        ).fetchone()

        if existing is not None:
            return (
                f"A return already exists for '{item['product_name']}' "
                f"in order #{order_id} with status {existing['status']}."
            )

        # Create the return.
        cursor = conn.execute(
            """
            INSERT INTO returns (
                order_id,
                order_item_id,
                user_id,
                reason,
                status,
                requested_at,
                resolved_at,
                admin_id
            )
            VALUES (?, ?, ?, ?, 'PENDING', ?, NULL, NULL)
            """,
            (
                order_id,
                item["order_item_id"],
                user["id"],
                reason,
                now,
            ),
        )

        return_id = cursor.lastrowid

        # Create the ticket linked to the same conversation thread.
        subject = f"Return request for {item['product_name']}"

        conn.execute(
            """
            INSERT INTO tickets (
                user_id,
                return_id,
                subject,
                status,
                thread_id,
                user_email,
                created_at,
                updated_at
            )
            VALUES (?, ?, ?, 'OPEN', ?, ?, ?, ?)
            """,
            (
                user["id"],
                return_id,
                subject,
                thread_id,
                user_email,
                now,
                now,
            ),
        )

        conn.commit()

    return (
        f"Return request #{return_id} has been created for "
        f"'{item['product_name']}' in order #{order_id}. "
        "The request is now pending human review."
    )


def get_action_tools():
    """Return the customer action tools."""
    return [create_return_action]
