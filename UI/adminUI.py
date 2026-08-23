import sqlite3
from pathlib import Path

import streamlit as st

# Database

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_ROOT / "ecommerce.db"


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

def get_return_requests():
    """Fetch return requests with their ticket and order details."""

    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row

        rows = conn.execute(
            """
            SELECT
                r.id AS return_id,
                r.order_id,
                r.reason,
                r.status AS return_status,
                r.requested_at,
                r.resolved_at,

                t.id AS ticket_id,
                t.subject,
                t.status AS ticket_status,
                t.thread_id,
                t.user_email,
                t.created_at AS ticket_created_at,

                p.name AS product_name

            FROM returns r

            LEFT JOIN tickets t
                ON t.return_id = r.id

            LEFT JOIN order_items oi
                ON oi.id = r.order_item_id

            LEFT JOIN products p
                ON p.id = oi.product_id

            ORDER BY r.requested_at DESC
            """
        ).fetchall()

    return rows

# Session

def init_session():
    """Initialize Streamlit session state."""

    st.session_state.setdefault("admin_logged_in", False)
    st.session_state.setdefault("admin_email", None)
    st.session_state.setdefault("admin_name", None)

# Login

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

        user = authenticate_admin(email, password)

        if user is None:
            st.error("Invalid admin credentials.")
            return

        st.session_state.admin_logged_in = True
        st.session_state.admin_email = user["email"]
        st.session_state.admin_name = user["full_name"]

        st.success("Login successful.")
        st.rerun()

# Dashboard

def show_dashboard():
    """Display the admin dashboard."""

    st.title("🛠️ Support Admin Dashboard")

    # Sidebar
    with st.sidebar:
        st.header("Admin")

        st.write(
            f"**{st.session_state.admin_name}**"
        )

        st.caption(
            st.session_state.admin_email
        )

        st.divider()

        if st.button(
            "Logout",
            use_container_width=True,
        ):
            st.session_state.admin_logged_in = False
            st.session_state.admin_email = None
            st.session_state.admin_name = None
            st.rerun()

    # Dashboard header
    st.subheader("Return Requests")

    st.info(
        "The return request queue will appear here."
    )

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "Pending",
            "0",
        )

    with col2:
        st.metric(
            "Approved",
            "0",
        )

    with col3:
        st.metric(
            "Rejected",
            "0",
        )

    st.divider()

    st.subheader("Request Queue")

    return_requests = get_return_requests()

    if not return_requests:
        st.write("No return requests to display yet.")
    else:
        for request in return_requests:
            with st.container(border=True):
                st.markdown(
                    f"### Return #{request['return_id']}"
                )

                col1, col2, col3 = st.columns(3)

                with col1:
                    st.write(
                        f"**Customer:** {request['user_email']}"
                    )
                    st.write(
                        f"**Order:** #{request['order_id']}"
                    )

                with col2:
                    st.write(
                        f"**Product:** {request['product_name']}"
                    )
                    st.write(
                        f"**Return status:** {request['return_status']}"
                    )

                with col3:
                    st.write(
                        f"**Ticket:** #{request['ticket_id']}"
                    )
                    st.write(
                        f"**Ticket status:** {request['ticket_status']}"
                    )

                st.write(
                    f"**Reason:** {request['reason']}"
                )

                st.caption(
                    f"Thread ID: {request['thread_id']}"
                )

                st.caption(
                    f"Requested: {request['requested_at']}"
                )

# Main

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