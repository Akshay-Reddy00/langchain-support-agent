from pathlib import Path
from langchain_community.agent_toolkits import SQLDatabaseToolkit
from langchain_openai import ChatOpenAI
from langchain_community.utilities import SQLDatabase

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]

DB_PATH = PROJECT_ROOT / "ecommerce.db"


def get_database() -> SQLDatabase:
    """Return a LangChain SQLDatabase connected to ecommerce.db."""
    return SQLDatabase.from_uri(f"sqlite:///{DB_PATH.as_posix()}")


def get_sql_tools():
    """Return LangChain SQL tools for the e-commerce database."""

    db = get_database()

    llm = ChatOpenAI(
        model="gpt-4o-mini",
        temperature=0,
    )

    toolkit = SQLDatabaseToolkit(
        db=db,
        llm=llm,
    )

    return toolkit.get_tools()
