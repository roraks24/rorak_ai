# Rorak AI V2 — Architecture, Implementation Audit, and System Specification

**Document Version:** 2.6.0  
**Audit Date:** October 2026  
**Status:** Comprehensive Source-of-Truth Audit & Implementation Reference  
**Target Branch:** `v2-development`  
**Alembic Migration Head:** `8b09e014fdae`  
**Test Suite Status:** 172 passed in 13.26s (`pytest tests/ -q`)  

---

## 1. V2 Executive Overview

**Rorak AI V2** transitions Rorak from a stateless PDF question-answering prototype into an enterprise-grade, multi-user, multi-workspace document intelligence platform. 

The system provides:
1. **Multi-User Isolation & Authentication (V2.6):** Secure user registration with bcrypt password hashing, JWT bearer authorization, and strict user/workspace isolation across all resources.
2. **Multi-Workspace Organization:** Workspaces acting as tenancy boundaries for documents, conversations, and workspace-scoped memories.
3. **Stateful Conversations & Non-Destructive Context Windows (V2.3):** Multi-turn chat persistence in PostgreSQL with bounded sliding-window retrieval for LLM context assembly.
4. **Durable Long-Term Memory (V2.4):** Explicit preference and fact retention separate from short-term conversation history, with sensitive credential filtering and dual scoping (User vs. Workspace).
5. **Format-Agnostic Ingestion Engine (V2.5 Steps 1–4):** Canonical parser interface (`DocumentParser`, `ParsedDocument`, `StructuredBlock`) and extensible adapter registry supporting PDF, DOCX, TXT, Markdown, and table-aware CSV.
6. **Hardened Two-Stage RAG Pipeline:** Vector similarity search (FAISS) + Neural Reranking (`cross-encoder/ms-marco-MiniLM-L-6-v2`) with prompt injection defense via XML sandboxing and Groq Cloud LPU inference (`openai/gpt-oss-20b`).

---

## 2. High-Level System Architecture

```text
                                   RORAK AI V2
                                        |
                 +----------------------+----------------------+
                 |                                             |
       Client Web Application                        FastAPI REST API
     (Static SPA on Port 3000)                     (Uvicorn on Port 8000)
                 |                                             |
                 +----------------------+----------------------+
                                        |
                            Authentication & Middleware
                      (JWT Bearer, RateLimiter, RequestLogger)
                                        |
                                 User & Workspace
                                        |
                 +----------------------+----------------------+
                 |                      |                      |
            Conversations            Memories              Documents
                 |                      |                      |
              Messages               Durable           Format-Agnostic
          (Short-Term Thread         Memory            Parser Engine
               History)                 |                      |
                                        |             +--------+--------+
                                        |             | PDF, DOCX, TXT, |
                                        |             |  MD, CSV (S4)   |
                                        |             +--------+--------+
                                        |                      |
                                        |                ParsedDocument
                                        |                      |
                                        |                Text Chunking
                                        |              (500 char / 50 ov)
                                        |                      |
                                        |               Dense Embeddings
                                        |              (all-MiniLM-L6-v2)
                                        |                      |
                                        |                 FAISS Index
                                        |             (RAM & Local Disk)
                                        |                      |
                                        |               Vector Retrieval
                                        |                  (Top-10)
                                        |                      |
                                        |               Neural Reranker
                                        |              (CrossEncoder T3)
                                        |                      |
                                        +-------+-------+------+
                                                |
                                      Context Assembly Engine
                                                |
                     +--------------------------+--------------------------+
                     |                          |                          |
             System Guidelines           Durable Memories          Thread History
                     |                          |                          |
                     +--------------------------+--------------------------+
                                                |
                                        Document Evidence
                                                |
                                     Hardened Stateful Prompt
                                                |
                                     Groq Cloud LPU Inference
                                      (openai/gpt-oss-20b)
                                                |
                                        Response Payload
```

---

## 3. Comprehensive Feature Audit Matrix

Status Definitions:
- **`IMPLEMENTED`**: Code is written, active, verified in source, and covered by automated tests.
- **`PARTIAL`**: Core functionality exists, but secondary capabilities or edge-case handling are limited.
- **`NOT IMPLEMENTED`**: Not present in the codebase.
- **`DEFERRED`**: Explicitly excluded from V2 scope by design milestone decisions.

| Category | Feature / Requirement | Audit Status | Code Reference | Verification Notes |
| :--- | :--- | :--- | :--- | :--- |
| **A. Conversations** | Conversation creation | `IMPLEMENTED` | `backend/services/conversation_service.py` | `POST /conversations/` |
| | Conversation listing | `IMPLEMENTED` | `backend/routes/conversations.py` | Scoped to user & workspace with pagination |
| | Conversation retrieval | `IMPLEMENTED` | `backend/repositories/conversation_repository.py` | Validates user & workspace ownership |
| | Conversation renaming | `IMPLEMENTED` | `backend/services/conversation_service.py` | `PATCH /conversations/{id}` |
| | Conversation deletion | `IMPLEMENTED` | `backend/services/conversation_service.py` | Cascading delete of messages |
| | Persistent messages | `IMPLEMENTED` | `backend/models/db/message.py` | PostgreSQL `messages` table |
| | Reopen previous chats | `IMPLEMENTED` | `backend/routes/conversations.py` | `GET /conversations/{id}/messages` |
| | Deterministic message ordering | `IMPLEMENTED` | `backend/repositories/message_repository.py` | Ordered by `created_at ASC, id ASC` |
| | Multi-turn continuity | `IMPLEMENTED` | `backend/services/conversation_service.py` | `send_user_message_and_reply()` |
| | Conversation ID propagation | `IMPLEMENTED` | `backend/routes/chat.py` | Carried across chat turns |
| **B. Context Window** | Bounded recent-message window | `IMPLEMENTED` | `backend/core/config.py` | Default `CONTEXT_WINDOW_SIZE = 10` |
| | Deterministic sliding window | `IMPLEMENTED` | `backend/repositories/message_repository.py` | `get_recent_for_context()` |
| | Configurable window size | `IMPLEMENTED` | `backend/services/conversation_service.py` | Service/call-level parameter override |
| | Chronological context delivery | `IMPLEMENTED` | `backend/services/conversation_service.py` | Reverse sort from descending query |
| | Role preservation | `IMPLEMENTED` | `backend/rag/prompts.py` | User and Assistant roles cleanly partitioned |
| | Non-destructive projection | `IMPLEMENTED` | `backend/services/conversation_service.py` | Full history remains intact in DB |
| | History vs Memory separation | `IMPLEMENTED` | `backend/services/conversation_service.py` | Distinct tables and prompt sections |
| **C. Stateful Prompt** | System instructions sandboxing | `IMPLEMENTED` | `backend/rag/prompts.py` | Strict XML tag boundaries |
| | Durable memory injection | `IMPLEMENTED` | `backend/rag/prompts.py` | `<memory>` block |
| | Conversation history injection | `IMPLEMENTED` | `backend/rag/prompts.py` | `<conversation_history>` block |
| | Retrieved context injection | `IMPLEMENTED` | `backend/rag/prompts.py` | `<context>` block marked UNTRUSTED |
| | User question isolation | `IMPLEMENTED` | `backend/rag/prompts.py` | `<question>` block |
| **D. Long-Term Memory**| Memory data model | `IMPLEMENTED` | `backend/models/db/memory.py` | PostgreSQL `memories` table |
| | Memory Repository & Service | `IMPLEMENTED` | `backend/services/memory_service.py` | CRUD, validation, isolation |
| | User-level memories | `IMPLEMENTED` | `backend/services/memory_service.py` | `scope="user"`, `workspace_id=None` |
| | Workspace-level memories | `IMPLEMENTED` | `backend/services/memory_service.py` | `scope="workspace"`, `workspace_id=UUID` |
| | Scoped memory retrieval | `IMPLEMENTED` | `backend/repositories/memory_repository.py` | Merges user and workspace memories |
| | Sensitive credential detection | `IMPLEMENTED` | `backend/services/memory_service.py` | Regex filtering (OpenAI, AWS, JWT, etc.) |
| | Memory CRUD endpoints | `IMPLEMENTED` | `backend/routes/memories.py` | `POST`, `GET`, `PATCH`, `DELETE` |
| **E. RAG Pipeline** | Dense vector similarity | `IMPLEMENTED` | `backend/rag/vector_store.py` | FAISS CPU index with RAM/disk sync |
| | Neural cross-encoder reranker | `IMPLEMENTED` | `backend/services/reranker.py` | `cross-encoder/ms-marco-MiniLM-L-6-v2` |
| | Grounded generation | `IMPLEMENTED` | `backend/services/generator.py` | Fallback on missing context |
| | General Assistant mode | `IMPLEMENTED` | `backend/services/generator.py` | Fires when no documents are attached |
| | Groq LPU inference | `IMPLEMENTED` | `backend/services/generator.py` | `openai/gpt-oss-20b` with retry |
| **F. Ingestion Engine**| Canonical parser interface | `IMPLEMENTED` | `backend/parsers/base.py` | `DocumentParser`, `ParsedDocument` |
| | Parser Registry | `IMPLEMENTED` | `backend/parsers/registry.py` | MIME and extension dispatch |
| | Generic Ingestion Pipeline | `IMPLEMENTED` | `backend/services/ingestion.py` | Format-agnostic processing |
| **G. PDF Adapter** | PDF extraction & blocks | `IMPLEMENTED` | `backend/parsers/adapters/pdf.py` | `pypdf` with fallback extraction |
| **H. DOCX Adapter** | DOCX extraction & headings | `IMPLEMENTED` | `backend/parsers/adapters/docx.py` | Paragraphs, tables, heading paths |
| **I. TXT Adapter** | TXT multi-encoding & bounds | `IMPLEMENTED` | `backend/parsers/adapters/txt.py` | UTF-8, BOM, CP1252, Latin-1, null check |
| **J. Markdown Adapter**| Markdown parsing & code blocks | `IMPLEMENTED` | `backend/parsers/adapters/markdown.py` | ATX hierarchy, fenced code metadata |
| **K. CSV Ingestion** | Table-aware row context | `IMPLEMENTED` | `backend/parsers/adapters/csv.py` | V2.5 Step 4: row-level semantic blocks |
| | CSV sanitization & bounds | `IMPLEMENTED` | `backend/parsers/adapters/csv.py` | Delimiter sniffer, header norm, max rows |
| **L. API Contracts** | REST standards & schemas | `IMPLEMENTED` | `backend/models/schemas.py` | Pydantic V2 validated request/response |
| | HTTP status code semantics | `IMPLEMENTED` | `backend/routes/` | 200, 201, 204, 400, 401, 403, 404, 409, 422 |
| **M. Database** | PostgreSQL schema & migrations | `IMPLEMENTED` | `alembic/versions/` | Alembic head `8b09e014fdae` |
| | Relational foreign keys & cascade | `IMPLEMENTED` | `backend/models/db/` | Workspaces, Users, Messages, Memories |
| **N. Architecture** | Routes -> Services -> Repos | `IMPLEMENTED` | `backend/` | Strict separation of concerns |
| **O. Auth & Isolation**| Registration & bcrypt hashing | `IMPLEMENTED` | `backend/routes/auth.py` | Salted bcrypt via `passlib` |
| | Login & JWT Access Token | `IMPLEMENTED` | `backend/core/security.py` | HS256 JWT with configurable expiration |
| | Bearer token dependency | `IMPLEMENTED` | `backend/core/auth.py` | `get_current_user`, `get_optional_current_user` |
| | Identity resolution | `IMPLEMENTED` | `backend/core/auth.py` | Uses `current_user.id`, ignores spoofed IDs |
| | Resource ownership enforcement | `IMPLEMENTED` | `backend/core/auth.py` | 403 Forbidden on cross-tenant access |
| | Google OAuth / Social Login | `NOT IMPLEMENTED` | - | Explicitly excluded from V2 scope |
| **P. Security** | Multi-tenant isolation | `IMPLEMENTED` | `backend/core/auth.py` | Verified across conversations, docs, memories |
| | Privacy-preserving logging | `IMPLEMENTED` | `backend/main.py` | Message contents omitted from logs |
| **Q. Testing** | Comprehensive automated tests | `IMPLEMENTED` | `tests/` | 172 automated tests passing |
| **R. V2.5 Scope** | Frozen at Step 4 | `IMPLEMENTED` | `backend/parsers/` | Steps 1-4 active; Steps 5-8 deferred |
| **S. Persistence** | Multi-tenant FAISS partitioning | `PARTIAL` | `backend/rag/vector_store.py` | Partitioned via metadata; single index file |
| | Async background worker queue | `DEFERRED` | - | Ingestion runs synchronously in API process |

---

## 4. Conversation System (V2.3)

### Data Flow
```text
Client (POST /chat/)
  │
  ├─► routes/chat.py
  │     ├─► Validates current_user via JWT Bearer
  │     ├─► Resolves workspace_id (explicit or user default)
  │     └─► Calls ConversationService.send_user_message_and_reply()
  │
  └─► services/conversation_service.py
        ├─► Persists User Message (atomic transaction)
        ├─► Fetches Bounded History (MessageRepository)
        ├─► Fetches Scoped Memories (MemoryRepository)
        ├─► Calls generator.chat_func()
        ├─► Persists Assistant Message
        └─► Commits transaction & updates conversation.updated_at
```

### Endpoints
- `POST /conversations/`: Creates a conversation within an authorized workspace.
- `GET /conversations/?workspace_id=...`: Lists conversations for the user in the workspace (paginated).
- `GET /conversations/{id}`: Retrieves conversation metadata (enforces ownership).
- `PATCH /conversations/{id}`: Renames conversation title.
- `DELETE /conversations/{id}`: Deletes conversation and all linked messages.
- `GET /conversations/{id}/messages`: Fetches chronological message history with pagination.

---

## 5. Context Window Policy

Rorak AI V2 implements a **non-destructive, bounded sliding window**:
- **Sliding Limit:** Defined by `CONTEXT_WINDOW_SIZE` (default: 10 messages) or call-level override (`history_limit`).
- **Deterministic Ordering:** Retrieved via `ORDER BY created_at DESC, id DESC LIMIT N`, then reversed to provide strict chronological sequence to the LLM.
- **Non-Destructive Projection:** Older messages remain stored in PostgreSQL; they are merely projected out of the generation window to respect LLM context budgets and prevent token dilution.
- **Strict Distinction:** Conversation messages represent ephemeral thread history (*"What was said in this session?"*). They are **never** automatically promoted into durable long-term memory.

---

## 6. Long-Term Durable Memory (V2.4)

### Data Architecture
Memories represent durable facts, preferences, or operational instructions stored across conversations.
- **User Scope (`scope="user"`):** Available across all workspaces and conversations owned by the user (e.g., *"User prefers concise answers"*).
- **Workspace Scope (`scope="workspace"`):** Available to all members within a specific workspace (e.g., *"Project Alpha deadline is November 15"*).

### Sensitive Information Protection
Before persistence, memory content is scanned using regular expressions in `backend/services/memory_service.py`:
- Rejects OpenAI (`sk-...`), Anthropic (`sk-ant-...`), AWS (`AKIA...`), and GitHub (`ghp_...`) tokens.
- Rejects Bearer tokens, private keys (`-----BEGIN PRIVATE KEY-----`), and passwords.
- Throws HTTP 400 `ValidationError` preventing credential leakage into prompt contexts.

---

## 7. RAG Pipeline & Generation

```text
User Query ──► retriev_func() ──► FAISS Vector Store (Top-10 Candidates)
                     │
                     ▼
               rerank_func() ──► Cross-Encoder Model (Top-3 Reranked)
                     │
                     ▼
             context_func() ──► Formatted Document Context
                     │
                     ▼
          stateful_prompt_func()
                     ├─► System Instructions
                     ├─► <memory> (Scoped Durable Facts)
                     ├─► <conversation_history> (Chronological Turns)
                     ├─► <context> (UNTRUSTED Document Blocks)
                     └─► <question> (Sanitized User Input)
                     │
                     ▼
             _call_groq_completion() ──► Groq Cloud LPU (openai/gpt-oss-20b)
```

- **Dual-Mode Intelligence:** If no documents are uploaded/retrieved, the assistant operates in general conversation mode rather than failing.
- **Fallback Verification:** If a document is queried but the answer is not present in retrieved context, Rorak strictly outputs: `"I couldn't find this information in the uploaded document."`

---

## 8. Format-Agnostic Document Ingestion Engine (V2.5)

### Canonical Parser Architecture
Located in `backend/parsers/`:
- `DocumentParser` (Abstract Base Class): Defines `parse(file_bytes, filename) -> ParsedDocument`.
- `ParsedDocument`: Standardized data container holding document text, metadata, page/row counts, and a list of `StructuredBlock` objects.
- `StructuredBlock`: Discrete structural element holding `block_type` (paragraph, heading, table, row, code), `content`, `metadata` (heading path, page number, row index), and `index`.
- `ParserRegistry`: Thread-safe registry mapping MIME types and file extensions to registered parser instances.

---

## 9. Supported Document Formats & Adapters

| Format | Adapter Class | MIME Types | Extensions | Features & Capabilities |
| :--- | :--- | :--- | :--- | :--- |
| **PDF** | `PDFDocumentParser` | `application/pdf` | `.pdf` | Multi-strategy extraction via `pypdf`, page-level metadata, fallback string recovery. |
| **DOCX** | `DOCXDocumentParser` | `application/vnd.openxmlformats-officedocument...` | `.docx` | Paragraph extraction, table-to-text formatting, hierarchical heading path preservation (`heading_path`), corrupt file detection. |
| **TXT** | `TXTDocumentParser` | `text/plain` | `.txt` | Multi-encoding decoding (UTF-8, UTF-8 BOM, CP1252, Latin-1), null-byte binary rejection, line-ending normalization, paragraph segmentation. |
| **Markdown** | `MarkdownDocumentParser` | `text/markdown`, `text/x-markdown` | `.md` | ATX heading hierarchy parsing, nested section tracking, fenced code block extraction with programming language tagging and indentation preservation. |
| **CSV** | `CSVDocumentParser` | `text/csv`, `application/csv` | `.csv` | Table-aware row-context serialization, delimiter sniffing, header normalization, duplicate column renaming, bounded row intake. |

---

## 10. Table-Aware CSV Ingestion (V2.5 Step 4)

Rather than collapsing tabular data into an unstructured blob, `CSVDocumentParser` preserves relational structure:
- **Delimiter Detection:** Employs `csv.Sniffer` with fallback to comma.
- **Header Normalization:** Strips whitespace, auto-labels empty headers as `unnamed_1`, and de-duplicates collisions as `column_1`, `column_2`.
- **Semantic Row Serialization:** Each row is mapped to an independent `StructuredBlock`:
  ```text
  Row 4: | Employee ID: 1042 | Full Name: Jane Doe | Department: Engineering | Status: Active |
  ```
- **Boundaries & Guardrails:** Configurable `max_rows` (default: 5,000) prevents denial-of-service via massive files. Truncation flags are recorded in document metadata.

---

## 11. Complete API Contract Reference

### Authentication (`/auth`)
- `POST /auth/register`: Creates new user account; auto-provisions default personal workspace.
- `POST /auth/login`: Validates credentials; returns JWT access token.
- `GET /auth/me`: Resolves current authenticated user profile.

### Workspaces (`/workspaces`)
- `POST /workspaces/`: Creates workspace (assigns creator as `owner`).
- `GET /workspaces/`: Lists workspaces current user is a member of.
- `GET /workspaces/{id}`: Retrieves workspace metadata (requires membership).
- `DELETE /workspaces/{id}`: Deletes workspace (owner only).
- `POST /workspaces/{id}/members`: Adds member with role (`admin`, `member`, `viewer`).
- `GET /workspaces/{id}/members`: Lists workspace members.
- `DELETE /workspaces/{id}/members/{user_id}`: Removes member from workspace.

### Conversations (`/conversations`)
- `POST /conversations/`: Creates conversation in workspace.
- `GET /conversations/?workspace_id=...`: Lists conversations (paginated).
- `GET /conversations/{id}`: Gets conversation metadata.
- `PATCH /conversations/{id}`: Renames conversation.
- `DELETE /conversations/{id}`: Deletes conversation.
- `GET /conversations/{id}/messages`: Retrieves message history (paginated).

### Chat (`/chat`)
- `POST /chat/`: Stateful and grounded chat generation. Accepts `question`, optional `conversation_id`, and optional `workspace_id`. If `workspace_id` is omitted by an authenticated user, defaults to user's personal workspace.

### Memories (`/memories`)
- `POST /memories/`: Stores durable memory (User or Workspace scope).
- `GET /memories/`: Lists memories (scoped by user and workspace access).
- `GET /memories/{id}`: Retrieves specific memory.
- `PATCH /memories/{id}`: Updates memory content.
- `DELETE /memories/{id}`: Deletes memory.

### Documents (`/documents`)
- `POST /documents/upload`: Multipart document upload, format parsing, vector indexing, and artifact persistence.
- `GET /documents/?workspace_id=...`: Lists workspace documents (paginated).
- `GET /documents/{id}`: Retrieves document details and chunk counts.
- `PATCH /documents/{id}`: Renames document.
- `DELETE /documents/{id}`: Removes document, DB chunks, and source artifacts.
- `GET /documents/{id}/content`: Retrieves raw text content.

### System & Health (`/health`, `/ready`)
- `GET /health/`: Kubernetes liveness probe (exempt from rate limits).
- `GET /ready/`: Kubernetes readiness probe (verifies database, vector store, and embedding models).

---

## 12. Database Architecture & Migrations

### Entity-Relationship Diagram

```mermaid
erDiagram
    users ||--o{ workspace_members : "belongs to"
    users ||--o{ conversations : "owns"
    users ||--o{ memories : "stores"
    workspaces ||--o{ workspace_members : "contains"
    workspaces ||--o{ conversations : "groups"
    workspaces ||--o{ documents : "owns"
    workspaces ||--o{ memories : "scopes"
    conversations ||--o{ messages : "contains"
    documents ||--o{ document_chunks : "segments into"
    documents ||--o{ ingestion_jobs : "tracks"

    users {
        uuid id PK
        string email UK
        string password_hash
        timestamp created_at
        timestamp updated_at
    }

    workspaces {
        uuid id PK
        string name
        timestamp created_at
        timestamp updated_at
    }

    workspace_members {
        uuid workspace_id FK
        uuid user_id FK
        string role
        timestamp created_at
    }

    conversations {
        uuid id PK
        uuid workspace_id FK
        uuid user_id FK
        string title
        timestamp created_at
        timestamp updated_at
    }

    messages {
        uuid id PK
        uuid conversation_id FK
        string role
        text content
        timestamp created_at
    }

    memories {
        uuid id PK
        uuid user_id FK
        uuid workspace_id FK
        string scope
        string memory_type
        text content
        timestamp created_at
        timestamp updated_at
    }

    documents {
        uuid id PK
        uuid workspace_id FK
        string filename
        string original_filename
        string file_type
        integer file_size
        integer page_count
        string status
        timestamp created_at
        timestamp updated_at
    }
```

### Alembic Migrations
- `b56ab54c4f90`: Creates V2.1 foundation schema (`workspaces`, `workspace_members`, `conversations`, `messages`, `memories`, `documents`, `document_chunks`, `ingestion_jobs`).
- `6184867eb413`: Adds document lifecycle fields (`original_filename`, `storage_path`, `content_hash`).
- `8b09e014fdae`: Adds `password_hash` column to `users` table for V2.6 authentication.

---

## 13. Repository & Service Pattern Architecture

The codebase enforces clean separation of concerns:
```text
FastAPI Router (routes/conversations.py)
   │  - Validates HTTP request parameters & JSON bodies
   │  - Enforces JWT authentication & resolves current_user
   ▼
Business Logic Service (services/conversation_service.py)
   │  - Validates business rules & execution limits
   │  - Coordinates transaction boundaries (commit/rollback)
   │  - Manages context window sliding projections
   ▼
Storage Repository (repositories/conversation_repository.py)
   │  - Encapsulates SQLAlchemy ORM query construction
   │  - Executes database queries without HTTP awareness
   ▼
Database Session (core/database.py)
   │  - Manages connection pooling to PostgreSQL
```

---

## 14. Authentication System (V2.6)

- **Password Hashing:** Passwords hashed with salted bcrypt via `passlib.context.CryptContext(schemes=["bcrypt"])`. Plaintext passwords are never stored.
- **JWT Issuance:** Authenticated login issues HS256 signed JSON Web Tokens containing `sub` (user UUID string) and `exp` claims.
- **Authentication Dependencies:**
  - `get_current_user`: Strict dependency requiring valid `Authorization: Bearer <token>`; raises HTTP 401 if missing, invalid, or expired.
  - `get_optional_current_user`: Permissive dependency allowing unauthenticated public access while attaching identity if a valid token is provided.

---

## 15. Authorization & Multi-User Isolation

Identity is strictly derived from the validated JWT token:
$$\text{User Identity} \leftarrow \text{JWT Payload}(\text{sub}) = \text{current\_user.id}$$

Client-supplied `user_id` fields in request bodies or query parameters are **never trusted**:
1. **Conversation Isolation:** User A attempting to read, rename, or delete User B's conversation receives `HTTP 403 Forbidden`.
2. **Message Isolation:** User A attempting to view messages of User B's thread receives `HTTP 403 Forbidden`.
3. **Memory Isolation:** User A attempting to modify or delete User B's memory receives `HTTP 403 Forbidden`.
4. **Document Isolation:** User A cannot access or delete documents in workspaces where they lack membership (`HTTP 403 Forbidden`).
5. **Workspace Membership Isolation:** Non-members cannot list documents, create conversations, or read workspace memories.

---

## 16. Security & Privacy Model

- **Prompt Sandboxing:** Retrieved chunks and memories are enclosed within `<context>` and `<memory>` XML tags with strict system prompt directives warning the LLM to treat document data as untrusted.
- **Credential Protection:** Long-term memory rejects API keys and secrets upon ingestion.
- **Log Privacy:** The `RequestLoggingMiddleware` logs route paths and latencies while explicitly omitting user prompts, chat messages, and document contents.
- **Rate Limiting:** Sliding-window in-memory rate limiter configured to 120 requests/minute per IP, with `/health` and `/ready` probes explicitly exempted.

---

## 17. Automated Test Coverage

The test suite consists of **172 automated tests** across 15 test modules:

```text
tests/
├── test_api_contracts.py          # HTTP contract verification for conversations & messages
├── test_api_v2.py                 # Core V2 API contracts and error responses
├── test_chat.py                   # Chat endpoint, validation, prompt safety, and fallback modes
├── test_database.py               # Database session, connection pooling, and rollback tests
├── test_document_storage.py       # Local file storage provider and content hashing tests
├── test_documents.py              # Document upload, listing, pagination, and deletion tests
├── test_health_and_rate_limit.py  # Health/readiness probes and sliding-window rate limit tests
├── test_models.py                 # SQLAlchemy ORM entity relationships and cascade behavior
├── test_parsers.py                # Parser base classes, error handling, and registry tests
├── test_repositories.py           # Repository query logic, pagination, and filtering
├── test_schemas.py                # Pydantic schema validation, defaults, and bounds
├── test_security_v2_6.py          # 40+ security tests for auth, isolation, and anti-spoofing
├── test_services.py               # Business service logic and transactional isolation
├── test_step3_adapters.py         # DOCX, TXT, and Markdown parser adapter unit tests
└── test_step4_csv.py              # Table-aware CSV parser unit and integration tests
```

Execution Command:
```powershell
.venv\Scripts\pytest.exe tests/ -q
# Result: 172 passed in 13.26s
```

---

## 18. V2.5 Scope Status: Frozen at Step 4

V2.5 introduced the format-agnostic document ingestion engine and was **intentionally frozen at Step 4**:
- **Step 1 (Implemented):** Common parser interface (`DocumentParser`, `ParsedDocument`, `StructuredBlock`) and registry.
- **Step 2 (Implemented):** PDF adapter integration with `pypdf`.
- **Step 3 (Implemented):** DOCX, TXT, and Markdown adapters with full test coverage.
- **Step 4 (Implemented):** Table-aware CSV adapter with rich row-level context.
- **Steps 5–8 (Deferred by Design):** Advanced multimodal extraction, HTML/web scraping, spreadsheet (XLSX) workbook engines, and semantic knowledge graphs are intentionally deferred.

---

## 19. Current System Limitations

1. **FAISS Multi-Tenant Partitioning (`PARTIAL`):**
   - FAISS currently operates as a shared vector index with runtime document filtering rather than physically isolated vector indices per tenant.
2. **Synchronous Ingestion Processing (`PARTIAL`):**
   - Document parsing, chunking, and embedding generation execute within the request lifecycle rather than delegating to an asynchronous worker queue (e.g., Celery/Redis).
3. **In-Memory Rate Limiting (`PARTIAL`):**
   - The sliding-window rate limiter stores request timestamps in Python memory, which is ideal for single-instance deployments but would require a Redis backend for horizontally scaled multi-worker deployments.
4. **Third-Party Social Authentication (`NOT IMPLEMENTED / DEFERRED`):**
   - Google/GitHub OAuth is not implemented; V2 utilizes local email/password authentication with JWT.

---

## 20. Remaining Work Before Public Release

To transition Rorak AI V2 to public production readiness, the following tasks are scheduled:

1. **Background Job Queue:**
   - Migrate document parsing and embedding generation to an asynchronous background worker (e.g., ARQ or Celery) so large document uploads return immediately with job polling.
2. **Per-Workspace Vector Indexing:**
   - Partition FAISS index files on disk per workspace ID (`documents/{workspace_id}.index`) to ensure strict physical vector isolation.
3. **Database Migration Pipeline in CI/CD:**
   - Ensure GitHub Actions runs `alembic upgrade head` automatically against a staging PostgreSQL instance before running tests.
4. **Rate Limiting Persistence:**
   - Back `RateLimitMiddleware` with Redis for distributed multi-pod Cloud Run deployments.
