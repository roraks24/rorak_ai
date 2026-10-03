<div align="center">

<img src="frontend/logo.jpg" alt="Rorak AI" width="96" height="96" />

# Rorak AI

**A document-grounded AI assistant with persistent conversations, long-term memory, and multi-format RAG.**

[![CI](https://github.com/roraks24/rorak_ai/actions/workflows/ci.yml/badge.svg)](https://github.com/roraks24/rorak_ai/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.12%20%7C%203.14-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-4169E1?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

[Live demo](https://rorak.tech) · [Architecture](docs/ARCHITECTURE.md) · [Changelog](CHANGELOG.md) · [Report a bug](https://github.com/roraks24/rorak_ai/issues/new?template=bug_report.md)

</div>

---

Rorak AI lets you upload documents into a chat and ask questions about them. Answers are grounded in the retrieved passages; when a conversation has no documents, it falls back to a general-purpose assistant. Conversations, uploaded files, and learned user preferences are persisted per user in PostgreSQL.

> [!NOTE]
> The public demo at [rorak.tech](https://rorak.tech) currently runs **v1**. This branch contains **v2** — accounts, persistent conversations, memory, and multi-format ingestion.

## Features

- **Two-stage retrieval** — FAISS dense search (top-10) followed by a cross-encoder reranker (top-3) before generation.
- **Multi-format ingestion** — PDF, DOCX, TXT, Markdown, and table-aware CSV through a pluggable parser registry.
- **Conversation-scoped documents** — files uploaded in a chat are only retrieved for that chat.
- **Persistent conversations** — full history in PostgreSQL with a bounded sliding context window sent to the model.
- **Long-term memory** — durable user facts and preferences, created manually or extracted automatically from chat, with secret/credential filtering.
- **Accounts & isolation** — bcrypt password hashing, JWT bearer auth, and ownership checks on every conversation, document, and memory.
- **Prompt-injection hardening** — retrieved text is passed as explicitly untrusted, XML-delimited context.
- **Operational basics** — liveness/readiness probes, per-IP rate limiting, request logging with secret redaction, Alembic migrations.

## Architecture

```mermaid
flowchart LR
    UI["Web client<br/>(vanilla JS SPA)"] -->|"HTTPS + JWT"| API["FastAPI"]

    subgraph Backend
        API --> Auth["Auth & ownership checks"]
        Auth --> Conv["Conversation service"]
        Auth --> Docs["Document service"]
        Auth --> Mem["Memory service"]

        Docs --> Parsers["Parser registry<br/>PDF · DOCX · TXT · MD · CSV"]
        Parsers --> Embed["Embeddings<br/>all-MiniLM-L6-v2"]
        Embed --> FAISS[("FAISS index")]

        Conv --> Retr["Retriever (top-10)"]
        FAISS --> Retr
        Retr --> Rerank["Cross-encoder reranker (top-3)"]
        Rerank --> Prompt["Prompt assembly<br/>memory · history · context · question"]
        Mem --> Prompt
        Prompt --> LLM["Groq LLM"]
    end

    Conv & Docs & Mem --> PG[("PostgreSQL")]
```

Routes → services → repositories, with SQLAlchemy models and Alembic migrations. See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the request lifecycle, data model, and design decisions.

## Tech stack

| Layer | Technology |
| --- | --- |
| API | FastAPI, Uvicorn, Pydantic v2 |
| Persistence | PostgreSQL, SQLAlchemy 2, Alembic |
| Retrieval | FAISS (CPU), `sentence-transformers/all-MiniLM-L6-v2`, `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| Generation | Groq (`openai/gpt-oss-20b` by default) |
| Parsing | pypdf, python-docx, LangChain text splitters |
| Auth | PyJWT, bcrypt |
| Frontend | HTML, CSS, vanilla JavaScript, marked.js, DOMPurify |

## Getting started

You need a free [Groq API key](https://console.groq.com/keys).

### Option A — Docker Compose (recommended)

```bash
git clone https://github.com/roraks24/rorak_ai.git
cd rorak_ai
cp .env.example .env          # set GROQ_API_KEY and JWT_SECRET_KEY
docker compose up --build
```

- App: <http://localhost:3000>
- API docs: <http://localhost:8000/docs>

The first start downloads the embedding and reranker models (~200 MB), which are cached in a Docker volume.

### Option B — Local development

Requires Python 3.12+ and a running PostgreSQL instance.

```bash
python -m venv .venv
source .venv/bin/activate                     # Windows: .venv\Scripts\activate
pip install --extra-index-url https://download.pytorch.org/whl/cpu -r requirements-dev.txt

cp .env.example .env                          # set DATABASE_URL, GROQ_API_KEY, JWT_SECRET_KEY
alembic upgrade head

uvicorn backend.main:app --reload --port 8000                # terminal 1
python -m http.server 3000 --directory frontend              # terminal 2
```

If you have `make`, `make help` lists shortcuts for these commands.

## Configuration

All settings are read from environment variables (or `.env`). See [`.env.example`](.env.example) for the full annotated list.

| Variable | Default | Purpose |
| --- | --- | --- |
| `DATABASE_URL` | — | PostgreSQL URL, e.g. `postgresql+psycopg://user:pass@host:5432/rorak` |
| `GROQ_API_KEY` | — | Groq API key (required for generation) |
| `JWT_SECRET_KEY` | insecure dev default | Token signing secret; **must** be set when `ENVIRONMENT=production` |
| `ENVIRONMENT` | `development` | `production` enforces a real JWT secret |
| `GROQ_MODEL` | `openai/gpt-oss-20b` | LLM used for answers and memory extraction |
| `CHUNK_SIZE` / `CHUNK_OVERLAP` | `500` / `50` | Text splitting (characters) |
| `RETRIEVAL_K` / `RERANK_TOP_K` | `10` / `3` | Candidates retrieved / kept after reranking |
| `CONTEXT_WINDOW_SIZE` | `10` | Recent messages included in each prompt |
| `MEMORY_WINDOW_SIZE` | `5` | Long-term memories included in each prompt |
| `MAX_UPLOAD_SIZE_BYTES` | `10485760` | Upload limit (10 MB) |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | JWT lifetime |

## API overview

Interactive OpenAPI docs are served at `/docs`. All endpoints except auth and health require `Authorization: Bearer <token>`.

| Area | Endpoints |
| --- | --- |
| Auth | `POST /auth/register`, `POST /auth/login`, `GET /auth/me` |
| Chat | `POST /chat/` — ask a question, optionally within a `conversation_id` |
| Conversations | `GET/POST /conversations/`, `GET/PATCH/DELETE /conversations/{id}`, `GET/POST /conversations/{id}/messages` |
| Documents | `POST /documents/upload?conversation_id=…`, `GET /documents/`, `GET/PATCH/DELETE /documents/{id}` |
| Memories | `GET/POST /memories/`, `GET/PATCH/DELETE /memories/{id}` |
| Health | `GET /health/` (liveness), `GET /ready/` (models, vector store, database) |

```bash
# Register, log in, and ask a question
curl -X POST localhost:8000/auth/register -H 'Content-Type: application/json' \
     -d '{"name": "Ada", "email": "ada@example.com", "password": "correct-horse-battery"}'

TOKEN=$(curl -s -X POST localhost:8000/auth/login -H 'Content-Type: application/json' \
     -d '{"email": "ada@example.com", "password": "correct-horse-battery"}' | jq -r .access_token)

curl -X POST localhost:8000/chat/ -H "Authorization: Bearer $TOKEN" \
     -H 'Content-Type: application/json' -d '{"question": "Hello!"}'
```

## Project structure

```text
backend/
├── core/           # settings, database session, JWT/security, auth dependencies, logging
├── models/         # SQLAlchemy models (db/) and Pydantic API schemas
├── parsers/        # parser interface, registry, and format adapters
├── rag/            # embeddings, FAISS vector store, prompt templates
├── repositories/   # data-access layer
├── routes/         # FastAPI routers
├── services/       # business logic: chat, conversations, documents, memory, retrieval
└── main.py         # app factory, middleware, router registration
alembic/            # database migrations
frontend/           # static single-page web client
tests/              # pytest suite (API, services, repositories, parsers, security)
docs/               # architecture and design notes
```

## Testing

The suite runs against a real PostgreSQL database (the same one configured in `DATABASE_URL`).

```bash
alembic upgrade head
pytest -q
```

CI runs the suite on every pull request against PostgreSQL 16 on Python 3.12 and 3.14.

## Security

- Passwords are hashed with bcrypt; sessions use short-lived HS256 JWTs.
- Every resource lookup is scoped to the authenticated user.
- Retrieved document text is treated as untrusted data in the prompt.
- Memory content is screened for API keys, tokens, and private keys before it is stored.

Please report vulnerabilities privately — see [SECURITY.md](SECURITY.md).

## Roadmap

- [ ] Background ingestion queue for large uploads
- [ ] Per-user vector partitioning (pgvector or sharded FAISS)
- [ ] Streaming responses
- [ ] Inline citations with source page preview
- [ ] OCR for scanned PDFs

## Contributing

Contributions are welcome. Please read [CONTRIBUTING.md](CONTRIBUTING.md) and the [Code of Conduct](CODE_OF_CONDUCT.md) first.

## License

[MIT](LICENSE) © Rohit Saini
