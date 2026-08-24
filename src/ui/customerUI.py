import streamlit as st
from uuid import uuid4

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

    st.subheader("Sign in")

    with st.form("login_form"):
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

            st.rerun()


def customer_home() -> None:
    st.title("🛍️ Customer Support")

    st.sidebar.header("Account")
    st.sidebar.write(
        f"**Email:** {st.session_state.user_email}"
    )

    st.sidebar.divider()

    st.sidebar.header("Conversations")

    if st.sidebar.button(
        "➕ New conversation",
        use_container_width=True,
    ):
        start_new_conversation()
        st.rerun()

    st.sidebar.divider()

    if st.sidebar.button(
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

    if st.session_state.conversation_id:
        st.caption(
            f"Conversation ID: "
            f"`{st.session_state.conversation_id}`"
        )
    else:
        st.info(
            "Start a new conversation from the sidebar."
        )

def start_new_conversation() -> None:
    conversation_id = str(uuid4())

    st.session_state.conversation_id = conversation_id
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": "Hi! How can I help you today?",
        }
    ]

    st.session_state.conversations[conversation_id] = (
        st.session_state.messages.copy()
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