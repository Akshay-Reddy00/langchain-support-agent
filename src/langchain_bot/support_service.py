from langchain_bot.agent import get_agent, get_thread_config
from langchain_bot.context import SessionContext
from langchain_bot.hitl_utils import handle_interrupt


def process_customer_message(
    *,
    user_email: str,
    conversation_id: str,
    message: str,
):
    """Process one customer message through the support agent."""

    agent = get_agent()

    context = SessionContext(
        user_email=user_email,
        conversation_id=conversation_id,
        role="customer",
    )

    config = get_thread_config(
        user_email,
        conversation_id,
    )

    result = agent.invoke(
        {
            "messages": [
                {
                    "role": "user",
                    "content": message,
                }
            ]
        },
        config=config,
        context=context,
    )

    interrupts = result.get("__interrupt__")

    if interrupts:
        thread_id = config["configurable"]["thread_id"]

        action_ids = []

        for interrupt in interrupts:
            action_ids.extend(
                handle_interrupt(
                    interrupt=interrupt,
                    user_email=user_email,
                    thread_id=thread_id,
                )
            )

        return {
            "status": "pending",
            "action_ids": action_ids,
            "result": result,
        }

    return {
        "status": "completed",
        "action_ids": [],
        "result": result,
    }
