import json
import sqlite3
from pathlib import Path
from uuid import uuid4

import streamlit as st

from langchain_bot.support_service import process_customer_message


def ensure_conv_store() -> Path:
    """Create the persistent conversation store."""

    project_root = Path(__file__).resolve().parents[2]

    db_path = project_root / "conversations.db"

    with sqlite3.connect(db_path) as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                user_email TEXT NOT NULL,
                messages TEXT NOT NULL
            )
            """)
        conn.commit()

    return db_path


def save_conversation(
    conversation_id: str,
    user_email: str,
    messages: list,
) -> None:
    """Save or update one conversation."""

    db_path = ensure_conv_store()

    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            INSERT INTO conversations (
                id,
                user_email,
                messages
            )
            VALUES (?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                messages = excluded.messages
            """,
            (
                conversation_id,
                user_email,
                json.dumps(messages),
            ),
        )

        conn.commit()


def load_conversations(user_email: str) -> dict:
    """Load all conversations for one customer."""

    db_path = ensure_conv_store()

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute(
            """
            SELECT id, messages
            FROM conversations
            WHERE user_email = ?
            ORDER BY rowid DESC
            """,
            (user_email,),
        ).fetchall()

    return {conversation_id: json.loads(messages) for conversation_id, messages in rows}


def init_session() -> None:
    st.session_state.setdefault("logged_in", False)
    st.session_state.setdefault("user_email", None)
    st.session_state.setdefault("user_role", None)
    st.session_state.setdefault("conversation_id", None)
    st.session_state.setdefault("messages", [])
    st.session_state.setdefault("conversations", {})


def login_screen() -> None:
    st.title("🛍️ Customer Support")
    st.caption("AI-powered e-commerce support")

    with st.form("login_form"):
        st.subheader("Sign in")

        email = st.text_input(
            "Email",
            placeholder="you@example.com",
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

        st.session_state.logged_in = True
        st.session_state.user_email = email
        st.session_state.user_role = "customer"

        st.session_state.conversations = load_conversations(email)
        st.session_state.conversation_id = None
        st.session_state.messages = []

        st.rerun()


def start_new_conversation() -> None:
    conversation_id = str(uuid4())

    messages = [
        {
            "role": "assistant",
            "content": "Hi! How can I help you today?",
        }
    ]

    st.session_state.conversation_id = conversation_id
    st.session_state.messages = messages
    st.session_state.conversations[conversation_id] = messages.copy()

    save_conversation(
        conversation_id,
        st.session_state.user_email,
        messages,
    )


def customer_home() -> None:
    st.title("🛍️ Customer Support")

    # ---------------------------------------------------------------
    # Sidebar
    # ---------------------------------------------------------------

    with st.sidebar:
        st.header("Account")

        st.write(f"**Email:** {st.session_state.user_email}")

        st.divider()

        st.header("Conversations")

        if st.button(
            "➕ New conversation",
            use_container_width=True,
        ):
            start_new_conversation()
            st.rerun()

        for conversation_id, messages in st.session_state.conversations.items():
            if messages:
                first_user_message = next(
                    (
                        message["content"]
                        for message in messages
                        if message["role"] == "user"
                    ),
                    "New conversation",
                )

                label = first_user_message[:40]

            else:
                label = "New conversation"

            if st.button(
                label,
                key=f"conversation_{conversation_id}",
                use_container_width=True,
            ):
                st.session_state.conversation_id = conversation_id
                st.session_state.messages = messages.copy()
                st.rerun()

        st.divider()

        if st.button(
            "Logout",
            use_container_width=True,
        ):
            st.session_state.logged_in = False
            st.session_state.user_email = None
            st.session_state.user_role = None
            st.session_state.conversation_id = None
            st.session_state.messages = []
            st.session_state.conversations = {}

            st.rerun()

    # ---------------------------------------------------------------
    # Main conversation area
    # ---------------------------------------------------------------

    if not st.session_state.conversation_id:
        st.info("Start a new conversation from the sidebar.")
        return

    st.caption(f"Conversation ID: " f"`{st.session_state.conversation_id}`")

    # Display conversation
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.write(message["content"])

    # Chat input
    prompt = st.chat_input("How can I help you?")

    if prompt:
        st.session_state.messages.append(
            {
                "role": "user",
                "content": prompt,
            }
        )

        with st.chat_message("user"):
            st.write(prompt)

        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                result = process_customer_message(
                    user_email=st.session_state.user_email,
                    conversation_id=(st.session_state.conversation_id),
                    message=prompt,
                )

            if result["status"] == "pending":
                response = (
                    "Your request has been submitted for "
                    "human review. An administrator needs to "
                    "approve it before I can proceed."
                )

            else:
                agent_messages = result["result"].get(
                    "messages",
                    [],
                )

                response = ""

                for message in reversed(agent_messages):
                    if message.type == "ai" and message.content:
                        response = message.content
                        break

                if not response:
                    response = "I processed your request."

            st.write(response)

        st.session_state.messages.append(
            {
                "role": "assistant",
                "content": response,
            }
        )

        conversation_id = st.session_state.conversation_id

        st.session_state.conversations[conversation_id] = (
            st.session_state.messages.copy()
        )

        save_conversation(
            conversation_id,
            st.session_state.user_email,
            st.session_state.messages,
        )


def main() -> None:
    st.set_page_config(
        page_title="Customer Support",
        page_icon="🛍️",
        layout="centered",
    )

    init_session()

    if not st.session_state.logged_in:
        login_screen()
    else:
        customer_home()


if __name__ == "__main__":
    main()
