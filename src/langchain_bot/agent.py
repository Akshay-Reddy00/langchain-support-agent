import os
import sqlite3

from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.agents.middleware import HumanInTheLoopMiddleware
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.sqlite import SqliteSaver

from langchain_bot.sql_tools import get_sql_tools
from langchain_bot.action_tools import get_action_tools
from langchain_bot.context import SessionContext

from langchain_bot.customer_context_middleware import CustomerContextMiddleware

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

    model_name = os.getenv("MODEL")
    temperature = os.getenv("TEMPERATURE")

    model = ChatOpenAI(
        model=model_name,
        temperature=temperature,
    )

    tools = [
        *get_action_tools(),
        *get_sql_tools(),
    ]

    return create_agent(
        model=model,
        tools=tools,
        system_prompt=(
            "You are an e-commerce customer support agent. "
            "The authenticated customer's email is provided in the runtime context. "
            "Never ask the customer to provide or confirm their email address. "
            "Use the authenticated customer context when calling tools. "
            "\n\n"
            "You have access to SQL database tools for customer-specific information. "
            "You MUST use the SQL database tools when the customer asks about their "
            "orders, order status, payments, returns, tickets, or purchase history. "
            "Do not say that you do not have access to this information unless the "
            "SQL tools return an error or no relevant data exists. "
            "When answering questions about the authenticated customer's data, first "
            "use sql_db_list_tables or sql_db_schema when needed to understand the "
            "database structure, then use sql_db_query to retrieve the information. "
            "Always filter customer-specific SQL results using the authenticated "
            "customer email provided in the runtime context. "
            "Never intentionally retrieve another customer's data. "
            "\n\n"
            "When the customer requests a return, identify the order ID, "
            "product name, and reason from the conversation. "
            "If those details are available, call create_return_action. "
            "Do not ask for information that is already available in the "
            "conversation or runtime context. "
            "The create_return_action tool creates a PENDING return request "
            "and requires human-in-the-loop approval before execution."
        ),
        context_schema=SessionContext,
        checkpointer=get_checkpointer(),
        middleware=[
            CustomerContextMiddleware(),
            HumanInTheLoopMiddleware(
                interrupt_on={
                    "create_return_action": True,
                }
            ),
        ],
    )


def get_agent():
    """Return the shared support agent."""

    global _agent

    if _agent is None:
        _agent = create_support_agent()

    return _agent
