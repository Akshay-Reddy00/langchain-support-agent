import logging
from datetime import datetime
from pathlib import Path

from langchain.agents.middleware import (
    ModelRequest,
    wrap_model_call,
    wrap_tool_call,
)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOG_DIR = PROJECT_ROOT / "logs"
LOG_DIR.mkdir(exist_ok=True)

LOG_FILE = LOG_DIR / "app.log"


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler(LOG_FILE, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger(__name__)


def _ts() -> str:
    """Return a readable timestamp."""
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _get_user_email(request) -> str:
    """Extract user email from runtime context when available."""

    try:
        context = request.runtime.context

        if context is not None:
            return getattr(context, "user_email", "unknown")
    except Exception:
        pass

    return "unknown"


def _preview(content, limit: int = 250) -> str:
    """Create a short one-line preview."""

    if content is None:
        return ""

    text = str(content).replace("\n", " ").strip()

    if len(text) > limit:
        return text[:limit] + "..."

    return text


@wrap_model_call
def model_logging_middleware(
    request: ModelRequest,
    handler,
):
    """Log model requests and responses."""

    user_email = _get_user_email(request)

    messages = request.messages

    last_message = messages[-1] if messages else None

    last_content = ""

    if last_message is not None:
        last_content = getattr(
            last_message,
            "content",
            "",
        )

    logger.info(
        "%s | MODEL REQUEST | user=%s | messages=%s | preview=%s",
        _ts(),
        user_email,
        len(messages),
        _preview(last_content),
    )

    try:
        response = handler(request)

        response_message = getattr(
            response,
            "result",
            None,
        )

        # Some LangChain versions return the AI message
        # directly as response.result.
        if response_message is None:
            response_message = response

        content = getattr(
            response_message,
            "content",
            "",
        )

        tool_calls = getattr(
            response_message,
            "tool_calls",
            [],
        )

        # If the response object contains a list of messages,
        # extract the last AI message.
        if not content and not tool_calls:
            result_messages = getattr(
                response,
                "messages",
                None,
            )

            if result_messages:
                for message in reversed(result_messages):
                    message_type = getattr(
                        message,
                        "type",
                        "",
                    )

                    if message_type == "ai":
                        content = getattr(
                            message,
                            "content",
                            "",
                        )

                        tool_calls = getattr(
                            message,
                            "tool_calls",
                            [],
                        )

                        break

        if tool_calls:
            tool_names = []

            for tool_call in tool_calls:
                if isinstance(tool_call, dict):
                    tool_names.append(
                        tool_call.get(
                            "name",
                            "unknown",
                        )
                    )
                else:
                    tool_names.append(
                        getattr(
                            tool_call,
                            "name",
                            "unknown",
                        )
                    )

            logger.info(
                "%s | MODEL RESPONSE | user=%s | type=TOOL_CALLS | "
                "tools=%s | preview=%s",
                _ts(),
                user_email,
                tool_names,
                _preview(content),
            )

        else:
            logger.info(
                "%s | MODEL RESPONSE | user=%s | type=TEXT | preview=%s",
                _ts(),
                user_email,
                _preview(content),
            )

        return response

    except Exception as error:

        logger.exception(
            "%s | MODEL ERROR | user=%s | error=%s",
            _ts(),
            user_email,
            str(error),
        )

        raise


@wrap_tool_call
def tool_logging_middleware(
    request,
    handler,
):
    """Log tool requests and results."""

    tool_call = request.tool_call

    tool_name = tool_call.get(
        "name",
        "unknown",
    )

    tool_args = tool_call.get(
        "args",
        {},
    )

    user_email = "unknown"

    try:
        context = request.runtime.context

        if context is not None:
            user_email = getattr(
                context,
                "user_email",
                "unknown",
            )
    except Exception:
        pass

    logger.info(
        "%s | TOOL REQUEST | user=%s | tool=%s | args=%s",
        _ts(),
        user_email,
        tool_name,
        tool_args,
    )

    try:

        result = handler(request)

        result_preview = _preview(
            getattr(
                result,
                "content",
                result,
            ),
        )

        logger.info(
            "%s | TOOL SUCCESS | user=%s | tool=%s | result=%s",
            _ts(),
            user_email,
            tool_name,
            result_preview,
        )

        return result

    except Exception as error:

        logger.exception(
            "%s | TOOL ERROR | user=%s | tool=%s | error=%s",
            _ts(),
            user_email,
            tool_name,
            str(error),
        )

        raise


def get_logging_middleware():
    """Return the logging middleware used by the support agent."""

    return [
        model_logging_middleware,
        tool_logging_middleware,
    ]
