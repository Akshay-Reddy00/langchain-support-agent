import sqlite3
from pathlib import Path

import streamlit as st

from langchain_bot.agent import get_agent
from langchain_bot.hitl_utils import (
    list_pending_actions,
    get_pending_action,
    resume_with_decision,
)

# -------------------------------------------------------------------
# Database
# -------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "ecommerce.db"


# -------------------------------------------------------------------
# Authentication
# -------------------------------------------------------------------


def authenticate_admin(email: str, password: str):
    """Authenticate a user and ensure the account has admin role."""

    with sqlite3.connect(DB_PATH) as conn:
        row = conn.execute(
            """
            SELECT email, full_name, role
            FROM users
            WHERE email = ?
              AND password = ?
              AND role = 'admin'
            """,
            (email, password),
        ).fetchone()

    if row is None:
        return None

    return {
        "email": row[0],
        "full_name": row[1],
        "role": row[2],
    }


# -------------------------------------------------------------------
# Admin statistics
# -------------------------------------------------------------------


def get_action_counts():
    """Return pending-action counts by status."""

    with sqlite3.connect(DB_PATH) as conn:
        rows = conn.execute("""
            SELECT status, COUNT(*)
            FROM pending_actions
            GROUP BY status
            """).fetchall()

    counts = {
        "PENDING": 0,
        "APPROVED": 0,
        "REJECTED": 0,
    }

    for status, count in rows:
        counts[status] = count

    return counts


# -------------------------------------------------------------------
# Session
# -------------------------------------------------------------------


def init_session():
    """Initialize Streamlit session state."""

    st.session_state.setdefault(
        "admin_logged_in",
        False,
    )

    st.session_state.setdefault(
        "admin_email",
        None,
    )

    st.session_state.setdefault(
        "admin_name",
        None,
    )


# -------------------------------------------------------------------
# Login
# -------------------------------------------------------------------


def show_login():
    """Display admin login form."""

    st.title("🛠️ Support Admin")
    st.caption("Administrator dashboard")
    st.divider()

    with st.form("admin_login_form"):
        st.subheader("Admin Login")

        email = st.text_input(
            "Email",
            placeholder="admin@example.com",
        )

        password = st.text_input(
            "Password",
            type="password",
        )

        submitted = st.form_submit_button(
            "Login",
            use_container_width=True,
        )

    if submitted:
        if not email or not password:
            st.error("Please enter your email and password.")
            return

        user = authenticate_admin(
            email,
            password,
        )

        if user is None:
            st.error("Invalid admin credentials.")
            return

        st.session_state.admin_logged_in = True
        st.session_state.admin_email = user["email"]
        st.session_state.admin_name = user["full_name"]

        st.success("Login successful.")
        st.rerun()


# -------------------------------------------------------------------
# Admin actions
# -------------------------------------------------------------------


def process_admin_decision(
    action_id: int,
    decision: str,
):
    """Approve or reject one pending action."""

    action = get_pending_action(action_id)

    if action is None:
        st.error(f"Pending action #{action_id} was not found.")
        return

    if action["status"] != "PENDING":
        st.warning(f"Action #{action_id} is already " f"{action['status']}.")
        return

    try:
        agent = get_agent()

        resume_with_decision(
            agent=agent,
            action_id=action_id,
            decision=decision,
        )

    except Exception as exc:
        st.error(f"Could not {decision} action " f"#{action_id}: {exc}")
        return

    if decision == "approve":
        st.success(f"Action #{action_id} approved.")
    else:
        st.success(f"Action #{action_id} rejected.")

    st.rerun()


# -------------------------------------------------------------------
# Pending action card
# -------------------------------------------------------------------


def show_pending_action(action):
    """Display one pending human-review action."""

    action_id = action["id"]

    with st.container(border=True):
        st.markdown(f"### Action #{action_id}")

        col1, col2, col3 = st.columns(3)

        with col1:
            st.write(f"**Customer:** {action['user_email']}")
            st.write(f"**Order:** #{action['order_id']}")

        with col2:
            st.write(f"**Action:** {action['action_type']}")

            if action["product_name"]:
                st.write(f"**Product:** " f"{action['product_name']}")

        with col3:
            st.write(f"**Status:** {action['status']}")
            st.write(f"**Created:** {action['created_at']}")

        if action["reason"]:
            st.write(f"**Reason:** {action['reason']}")

        st.caption(f"Thread ID: {action['thread_id']}")

        col1, col2 = st.columns(2)

        with col1:
            if st.button(
                "✅ Approve",
                key=f"approve_{action_id}",
                use_container_width=True,
            ):
                process_admin_decision(
                    action_id,
                    "approve",
                )

        with col2:
            if st.button(
                "❌ Reject",
                key=f"reject_{action_id}",
                use_container_width=True,
            ):
                process_admin_decision(
                    action_id,
                    "reject",
                )


# -------------------------------------------------------------------
# Dashboard
# -------------------------------------------------------------------


def show_dashboard():
    """Display the admin dashboard."""

    st.title("🛠️ Support Admin Dashboard")

    with st.sidebar:
        st.header("Admin")

        st.write(f"**{st.session_state.admin_name}**")

        st.caption(st.session_state.admin_email)

        st.divider()

        if st.button(
            "Logout",
            use_container_width=True,
        ):
            st.session_state.admin_logged_in = False
            st.session_state.admin_email = None
            st.session_state.admin_name = None

            st.rerun()

    # ---------------------------------------------------------------
    # Statistics
    # ---------------------------------------------------------------

    st.subheader("Human Review Queue")

    counts = get_action_counts()

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "Pending",
            counts["PENDING"],
        )

    with col2:
        st.metric(
            "Approved",
            counts["APPROVED"],
        )

    with col3:
        st.metric(
            "Rejected",
            counts["REJECTED"],
        )

    st.divider()

    # ---------------------------------------------------------------
    # Pending queue
    # ---------------------------------------------------------------

    st.subheader("Pending Actions")

    pending_actions = list_pending_actions()

    if not pending_actions:
        st.info("There are no pending actions.")
        return

    for action in pending_actions:
        show_pending_action(action)


# -------------------------------------------------------------------
# Main
# -------------------------------------------------------------------


def main():

    st.set_page_config(
        page_title="Support Admin",
        page_icon="🛠️",
        layout="wide",
    )

    init_session()

    if not st.session_state.admin_logged_in:
        show_login()
        return

    show_dashboard()


if __name__ == "__main__":
    main()
