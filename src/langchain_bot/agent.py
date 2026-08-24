import os
import sqlite3

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.sqlite import SqliteSaver

from langchain_bot.action_tools import get_action_tools
from langchain_bot.context import SessionContext

load_dotenv()


_checkpointer = None
_agent = None


def get_checkpointer():
    """Return the shared SQLite LangGraph checkpointer."""
    global _checkpointer

    if _checkpointer is None:
        checkpoint_path = os.getenv(
            "CHECKPOINTS_DB_PATH",
            "checkpoints.sqlite",
        )

        conn = sqlite3.connect(
            checkpoint_path,
            check_same_thread=False,
        )

        _checkpointer = SqliteSaver(conn)
        _checkpointer.setup()

    return _checkpointer


def get_thread_config(
    user_email: str,
    conversation_id: str,
) -> dict:
    """Build the LangGraph configuration for a customer conversation."""

    thread_id = f"{user_email}:{conversation_id}"

    return {
        "configurable": {
            "thread_id": thread_id,
        },
        "recursion_limit": 20,
    }


def create_support_agent():
    """Create the single support agent."""

    model = ChatOpenAI(
        model="gpt-4.1-mini",
        temperature=0.2,
    )

    return create_agent(
        model=model,
        tools=get_action_tools(),
        system_prompt=(
            "You are an e-commerce customer support agent. "
            "Help customers with return requests. "
            "When a customer wants to return an item, verify the "
            "necessary order information and use the return action tool. "
            "The return action requires human approval before it executes."
        ),
        context_schema=SessionContext,
        checkpointer=get_checkpointer(),
        middleware=[
            HumanInTheLoopMiddleware(
                interrupt_on={
                    "create_return_action": True,
                }
            )
        ],
    )


def get_agent():
    """Return the shared support agent."""

    global _agent

    if _agent is None:
        _agent = create_support_agent()

    return _agent
