from pathlib import Path

from dotenv import load_dotenv
from langchain.tools import tool
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import TextLoader

load_dotenv()


PROJECT_ROOT = Path(__file__).resolve().parents[2]

POLICIES_DIR = PROJECT_ROOT / "policies"

CHROMA_DB_DIR = PROJECT_ROOT / "chroma_db"


POLICY_FILES = [
    "returns_policy.txt",
    "shipping_policy.txt",
    "faq_returns_and_cancellations.txt",
]


_vector_store = None


def get_vector_store():
    """Create or load the Chroma vector store."""

    global _vector_store

    if _vector_store is not None:
        return _vector_store

    embeddings = OpenAIEmbeddings()

    if CHROMA_DB_DIR.exists():
        _vector_store = Chroma(
            persist_directory=str(CHROMA_DB_DIR),
            embedding_function=embeddings,
        )

        return _vector_store

    documents = []

    for file_name in POLICY_FILES:
        file_path = POLICIES_DIR / file_name

        loader = TextLoader(
            str(file_path),
            encoding="utf-8",
        )

        documents.extend(loader.load())

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=1000,
        chunk_overlap=200,
    )

    chunks = splitter.split_documents(documents)

    _vector_store = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=str(CHROMA_DB_DIR),
    )

    return _vector_store


@tool
def rag_policy_search(query: str) -> str:
    """Search the store's returns, shipping, refund, and cancellation policies.

    Use this tool for general policy questions that do not require
    customer-specific order, payment, return, or ticket data.
    """

    vector_store = get_vector_store()

    documents = vector_store.similarity_search(
        query,
        k=4,
    )

    if not documents:
        return "No relevant policy information was found."

    results = []

    for document in documents:
        results.append(document.page_content)

    return "\n\n---\n\n".join(results)


def get_rag_tools():
    """Return the RAG policy search tools."""

    return [rag_policy_search]
