<div align="center">

# 🗄️ Text-to-SQL RAG Agent

**Ask your database a question in plain English. Get back a correct SQL query and a real answer.**

A production-shaped natural language to SQL system built on LangGraph — with Self-RAG schema retrieval, human-in-the-loop clarification, self-correcting SQL generation, and defense-in-depth security. Deployed end-to-end: React frontend on Vercel, FastAPI backend on AWS EC2 behind Nginx with a real SSL certificate.

[**Live Demo**](https://text-to-sql-aiagent.vercel.app/) · [**API Docs**](https://text-to-sql-alokik.duckdns.org/docs) · [**Architecture**](#architecture)

</div>

---

## Screenshots

**Human-in-the-loop clarification when a question is ambiguous — the system pauses, asks, and resumes exactly where it left off:**

![Clarification flow](clarification-flow.png)

---

## Why this exists

Most text-to-SQL demos generate a query and run it — best effort, no verification, no way to say "I'm not sure." This project treats each of those as a real engineering problem instead of an afterthought:

- What if the retrieved schema context is actually wrong or incomplete?
- What if the user's question is genuinely ambiguous?
- What if the generated SQL fails to execute?
- What if the user connects their own database — how much should the system trust it?

Each of those questions maps to a real, deliberate piece of the architecture below, not a shortcut.

## What it does

Ask a question about a database in plain English — *"Which artist has the most albums?"* — and the system:

1. Figures out which parts of the schema are relevant (without you ever seeing the schema)
2. Asks you to clarify if the question is ambiguous
3. Writes the SQL
4. Runs it, catches its own mistakes, and retries if something's wrong
5. Gives you a plain-English answer, alongside the actual SQL it ran

Works against a built-in demo database, or against **your own** PostgreSQL database via connection credentials.

## Using it with your own database

The demo above runs against a built-in sample database (Chinook), but the system is built to work against **any** PostgreSQL database — not just the demo.

1. Open the app and click **"Connect your database"**
2. Paste in your database's connection string:
   ```
   postgresql://user:password@host:5432/dbname
   ```
3. *(Recommended)* Paste in a **separate read-only connection string** if you have one:
   ```
   postgresql://readonly_user:password@host:5432/dbname
   ```
   If you skip this, the system will still generate SQL for your questions — it just won't execute it, since it won't run queries with elevated access it wasn't explicitly given.
4. Ask your question as normal.

The system reflects on your database's actual schema at connection time — no upload, no pre-configuration. It works the same way against your database as it does against the demo one.

> **Why two connection strings?** For the built-in demo, a dedicated read-only Postgres role is created and enforced automatically. For a user's own database, the system has no way to create that role itself — so it relies on whatever credentials the user provides. Supplying separate read-only credentials is the safer option and is strongly recommended over reusing full-access credentials.

## Architecture

![LangGraph architecture](graph.png)

The system is a LangGraph state machine with three core loops, each one addressing a real failure mode:

### 1. Self-RAG schema retrieval
The target database's schema is reflected via SQLAlchemy, chunked per table, and embedded with `sentence-transformers` into a FAISS index. On each query, relevant tables are retrieved — but an LLM **critic** then checks whether what was retrieved is actually sufficient to answer the question. If not, retrieval retries with a wider search instead of silently proceeding on incomplete context. This is the difference between plain RAG and Self-RAG.

### 2. Human-in-the-loop clarification
If a question is ambiguous ("show me the top ones" — top *what*?), the graph doesn't guess. It pauses mid-execution using LangGraph's `interrupt()`, backed by a PostgreSQL checkpointer, asks the user a clarifying question, and resumes from the exact point it paused once an answer comes back — even if that answer arrives in a completely separate HTTP request, minutes or hours later.

### 3. Self-correcting SQL generation
Generated SQL passes through a keyword filter, then executes against a **read-only** database connection. If execution fails, the actual database error is fed back into the SQL generator for another attempt — a real self-correction loop, bounded by a configurable retry limit, with a graceful failure message if all attempts are exhausted.

## Security

Defense-in-depth, not a single point of failure:

| Layer | What it catches |
|---|---|
| Keyword filter | Obviously destructive queries (`DROP`, `DELETE`, `UPDATE`, etc.) before they reach the database |
| Dedicated read-only Postgres role | Enforces read-only access at the database level — even if the filter is bypassed, the database itself refuses writes |
| Generate-without-execute mode | If a user connects their own database without separate read-only credentials, SQL is generated but deliberately never executed |

## Tech stack

**AI / Backend logic**
`LangGraph` · `Groq API (Llama 3.1)` · `FAISS` · `sentence-transformers` · `SQLAlchemy`

**API**
`FastAPI` · `Pydantic` · `PostgreSQL` (checkpointing + demo data)

## Frontend

Built with React + Vite and Tailwind CSS, using a custom design system rather than default styling. The chat interface handles three states from one backend contract — a normal answer, a paused clarification question, and an error — using plain `useState`, no external state library needed at this scale. The `interrupt`/`resume` pattern from LangGraph is handled as a two-request flow (`/query` then `/resume`), tied together by a `thread_id`.

## Deployment

- **Frontend** deployed on Vercel, straight from GitHub, with environment-based config for local vs. production API URLs.
- **Backend** deployed on a hand-provisioned AWS EC2 instance (Ubuntu, `t3.micro`) — Docker, Python, and PostgreSQL set up manually over SSH. Runs as a permanent `systemd` service so it survives disconnects and reboots, sits behind an **Nginx** reverse proxy, and uses a free domain (DuckDNS) with a real **Let's Encrypt SSL certificate** so the API is served over HTTPS rather than plain HTTP.


## Project structure

This is a monorepo — backend and frontend live together for simplicity, deployed separately (backend to EC2, frontend to Vercel).

```
text-to-sql-aiagent/
├── api/              # FastAPI routes
├── pipeline/         # LangGraph state, nodes, graph definition, LLM clients
├── rag/              # Schema retrieval, vector store, Self-RAG critic
├── frontend/         # React + Vite + Tailwind app
├── app.py            # FastAPI entrypoint
└── main.py           # CLI entrypoint for local testing without the API layer
```

## Key design decisions

- **Two-tier LLM usage** — a fast model handles quick classification (retrieval critique, intent checking); SQL generation is a separate, dedicated call. Not every step needs the same model.
- **Dynamic, multi-database architecture** — the system doesn't hardcode a single database. Any question can target the built-in demo (Chinook) or a user-supplied connection string, with schema retrievers and DB engines cached per connection rather than rebuilt on every request.
- **Session-based state, not global state** — retrievers and engines are looked up per query via a session cache, keyed by connection string, so the same architecture cleanly supports one demo user or many concurrent users on different databases.
- **Real infrastructure, not a toy deploy** — the backend runs as a permanent `systemd` service on a real EC2 instance, behind Nginx, with an actual Let's Encrypt SSL certificate on a real domain — not just `localhost` or a one-click PaaS deploy.

## Known limitations

Being direct about what isn't solved yet:

- **Execution success ≠ semantic correctness.** If a requested field doesn't exist in the schema, the SQL generator may substitute a similarly-named column instead of declining to answer. Caught during testing, not yet fixed.
- **In-memory session cache.** Fine for a single-instance demo; would need a shared store (e.g. Redis) to scale across multiple server instances.
- **No automated test suite.** Every flow (happy path, clarification, self-correction, give-up path) was manually verified end-to-end during development — a real `pytest` suite is the natural next step.
- **User-provided databases without read-only credentials get generate-only mode** — the system won't execute with elevated access it wasn't explicitly given, even if that means declining to run the query at all.

## Running locally

### Prerequisites
- Python 3.11+, Node.js 18+, Docker, a Groq API key

### Backend
```bash
git clone https://github.com/Alokik-29/text-to-sql-aiagent.git
cd text-to-sql-aiagent

python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

pip install -r requirements.txt

# spin up Postgres
docker run --name pg-textsql -e POSTGRES_PASSWORD=yourpassword -e POSTGRES_DB=textsql -p 5432:5432 -d postgres

# load the Chinook sample database (see Chinook_PostgreSql.sql in this repo)
docker cp Chinook_PostgreSql.sql pg-textsql:/Chinook_PostgreSql.sql
docker exec -it pg-textsql psql -U postgres -d textsql -f /Chinook_PostgreSql.sql
```

Create a `.env` file:
```
GROQ_API_KEY=your_key_here
CHINOOK_DB_URL=postgresql://postgres:yourpassword@localhost:5432/chinook
CHINOOK_READONLY_DB_URL=postgresql://postgres:yourpassword@localhost:5432/chinook
APP_DB_URL=postgresql://postgres:yourpassword@localhost:5432/textsql
```

Run it:
```bash
uvicorn app:app --reload
```

### Frontend
```bash
cd frontend
npm install
npm run dev
```

## Author

**Alokik Gour**
[GitHub](https://github.com/Alokik-29) · [LinkedIn](https://www.linkedin.com/in/alokik29/)

---

<div align="center">
<sub>Built as a from-scratch upgrade of an earlier project, rebuilt around LangGraph, Self-RAG, and human-in-the-loop agentic design.</sub>
</div>
