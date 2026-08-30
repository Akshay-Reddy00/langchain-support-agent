# LangChain E-Commerce Support Agent

An AI-powered customer support application for an e-commerce platform.

The project uses **LangChain 1.x**, **LangGraph**, **Streamlit**, **SQLite**, **ChromaDB**, and **Gmail API integration** to provide customer support for orders, returns, policies, and human-approved actions.

---

## Features

### Customer Support Chatbot

Customers can:

- Log in using email and password.
- Start and manage multiple conversations.
- View persistent conversation history.
- Ask questions about:
  - Orders
  - Returns
  - Payments
  - Account-related information
- Ask policy and FAQ questions using RAG.
- Request order cancellations.
- Request product returns.

### RAG Policy Search

Policy and FAQ questions are answered using a ChromaDB-based retrieval system.

The policy knowledge base includes:

- `returns_policy.txt`
- `shipping_policy.txt`
- `faq_returns_and_cancellations.txt`

The RAG tool is used for policy and FAQ questions rather than customer-specific database queries.

---

### Human-in-the-Loop Approval

Sensitive customer actions require human review.

The current HITL workflow supports actions such as:

- Return requests
- Order cancellation requests

Workflow:

```text
Customer
   |
   v
LangChain Agent
   |
   v
Sensitive Action Requested
   |
   v
LangGraph Interrupt
   |
   v
Pending Action Stored
   |
   v
Admin Review
   |
   +---- Approve ----> Resume Original Agent Thread
   |
   +---- Reject -----> Resume Original Agent Thread
```

### Project Structure

```
langchain-support-agent/
│
├── policies/
│ ├── returns_policy.txt
│ ├── shipping_policy.txt
│ └── faq_returns_and_cancellations.txt
│
├── logs/
│ ├── app.log
│ └── email.log
│
├── chroma_db/
│
├── src/
│ │
│ ├── langchain_bot/
│ │ ├── agent.py
│ │ ├── action_tools.py
│ │ ├── context.py
│ │ ├── customer_context_middleware.py
│ │ ├── db_init.py
│ │ ├── gmail_tools.py
│ │ ├── hitl_middleware.py
│ │ ├── hitl_utils.py
│ │ ├── logging_middleware.py
│ │ ├── rag_tool.py
│ │ ├── sql_tools.py
│ │ └── support_service.py
│ │
│ └── ui/
│ ├── customerUI.py
│ ├── adminUI.py
│ └── authorize_gmail.py
│
├── ecommerce_setup.sql
├── ecommerce.db
├── checkpoints.sqlite
├── conversations.db
├── credentials.json
├── token.json
├── .env
├── .env.example
├── .gitignore
├── pyproject.toml
├── uv.lock
└── README.md
```

### Running the Applications

#### Windows PowerShell

```
Set the Python source path:
$env:PYTHONPATH = "$PWD\src"

Run Customer UI
& ".\.venv\Scripts\python.exe" -m streamlit run .\src\ui\customerUI.py

The customer application runs on a Streamlit server, typically:
http://localhost:8501

Run Admin UI
Open another PowerShell terminal in the project root.

Set: $env:PYTHONPATH = "$PWD\src"

Then run:
& ".\.venv\Scripts\python.exe" -m streamlit run .\src\ui\adminUI.py
```

### Gmail config

#### Create a Web application OAuth client

- For local development, add the redirect URI used by the authorization application `http://localhost:8501`
- Download OAuth client credentials `credentials.json` and place in project root.

#### Generate the OAuth token

```
$env:PYTHONPATH = "$PWD\src"
& ".\.venv\Scripts\python.exe" .\src\ui\authorize_gmail.py
```

- A browser window will open, Sign in with the Gmail account that should send notification emails.
- Approve the requested Gmail permissions and Complete the OAuth flow.
- This will create `token.json`
