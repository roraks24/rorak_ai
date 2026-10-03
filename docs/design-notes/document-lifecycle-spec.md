# Rorak AI V2.2 — Exact Implementation Specification

Prepared: 29 September 2026
Target branch: `v2-development`
V2.1 baseline commit: `4dc772eee6961e5d453b1fe1b11c7a75a5c2da08`
V2.1 Alembic head: `b56ab54c4f90`

## 1. Objective

Implement **V2.2 — Real Document Management**.

The purpose of V2.2 is to turn documents from an upload side effect into first-class product resources.

The implementation must establish one stable document identity connecting:

- database metadata
- durable source artifact
- document chunks
- vector/index metadata
- ingestion job state

Do not rewrite Rorak V1/V2.1. Do not add V2.3 memory, V3 agents, LangGraph, streaming, web search, or a new vector database.

---

## 2. Current V2.1 Problems To Fix

The current repository has these relevant conditions:

### `backend/models/db/document.py`

Current fields:

- `id`
- `workspace_id`
- `filename`
- `original_filename`
- `file_type`
- `file_size`
- `page_count`
- `status`
- `created_at`
- `updated_at`

V2.2 needs additional document metadata and lifecycle information.

### `backend/routes/documents.py`

Current upload flow:

1. validate PDF
2. save a temporary file
3. ingest
4. add chunks to FAISS
5. optionally persist a DB row when `workspace_id` is supplied
6. delete the file in `finally`

This is V1-style behavior and must be changed so the uploaded artifact becomes durable.

Current `/documents/clear` clears the global vector store. This must not be used as the normal V2.2 document deletion mechanism.

### `backend/services/document_service.py`

Current `delete_document()` deletes DB chunks, ingestion jobs, and the document row, but does not coordinate:

- FAISS/index cleanup
- durable source-artifact cleanup

Current `ingest_document()` creates the DB document during processing, but document metadata and artifact lifecycle are not yet complete.

### `backend/rag/vector_store.py`

FAISS is currently a runtime/persisted search representation. V2.2 must keep FAISS behind a service boundary and make document identity discoverable in vector metadata.

Do not replace FAISS just for novelty.

---

# 3. V2.2 Scope

Implement only these capabilities:

1. Document metadata
2. Durable source-artifact storage
3. Document lifecycle states
4. Chunk/document relationship consistency
5. Document-to-index discoverability
6. List documents
7. Get document
8. Rename document
9. Delete document
10. Retry/reindex foundation where already supported by the ingestion-job model
11. Automated lifecycle/deletion tests
12. API contract tests
13. V1 regression verification

Frontend is secondary. Backend contract must be stable first.

---

# 4. Document Data Model

Modify:

`backend/models/db/document.py`

Keep the existing stable fields and add the following fields.

## Required V2.2 fields

```python
display_name: Mapped[str]
```

User-facing document name. It can be initialized from `original_filename`.

```python
storage_key: Mapped[str]
```

Stable relative identifier for the stored artifact.

Do NOT store an absolute filesystem path as the durable identifier.

```python
mime_type: Mapped[str]
```

Store the validated MIME type.

```python
chunk_count: Mapped[int]
```

Number of successfully persisted document chunks.

```python
checksum_sha256: Mapped[str | None]
```

SHA-256 checksum of the uploaded source artifact.

```python
failure_reason: Mapped[str | None]
```

Human-readable processing failure information.

Do not expose internal stack traces through the public API.

Optional lifecycle timestamp:

```python
deleted_at: Mapped[datetime | None]
```

Only add this if the chosen V2.2 deletion implementation uses soft-delete state. Do not introduce soft deletion merely for convenience.

## Recommended string lengths

Use explicit SQLAlchemy limits:

```text
display_name        VARCHAR(255)
storage_key         VARCHAR(500)
mime_type           VARCHAR(100)
checksum_sha256     VARCHAR(64)
failure_reason      TEXT
```

Keep `filename` and `original_filename` for compatibility where existing code depends on them.

---

# 5. Status Lifecycle

Current enum values:

```python
UPLOADED
PROCESSING
INDEXED
FAILED
```

Use these consistently.

Recommended lifecycle:

```text
upload request
     |
     v
UPLOADED
     |
     v
PROCESSING
   /     \
  v       v
INDEXED  FAILED
```

Deletion is an operation, not a normal ingestion state.

If a transient deletion state is required internally, introduce it only when the implementation genuinely needs transactional cleanup/retry semantics. Do not expand the public status enum unnecessarily.

---

# 6. Database Relationships

The existing relationships must remain coherent:

```text
Workspace
   |
   +-- Document
          |
          +-- DocumentChunk
          |
          +-- IngestionJob
```

Every `DocumentChunk.document_id` must point to its owning document.

No orphan chunks.

Document deletion must not leave chunks or ingestion jobs behind.

Use database foreign-key behavior and explicit service-level cleanup deliberately. Do not rely on accidental ORM behavior.

---

# 7. Artifact Storage Design

Create a durable storage convention under `DOCUMENTS_DIR`.

Do not use:

```text
temp_<timestamp>_<filename>.pdf
```

as the permanent artifact identity.

Use a stable document-scoped storage key such as:

```text
documents/<document_id>/original/<sanitized_filename>
```

The exact physical base directory may remain `DOCUMENTS_DIR`.

The important invariant is:

```text
document.storage_key
        |
        v
one durable source artifact
```

### Storage rules

- Never trust the client path.
- Use `Path(filename).name` or an equivalent safe normalization.
- Do not allow `..` path traversal.
- Store the file before processing can finish.
- Do not delete the source artifact after successful ingestion.
- Cleanup must be safe to retry.
- Physical storage must be derived from the trusted `storage_key`.

---

# 8. Upload Flow

Refactor:

`POST /documents/upload`

to use this logical sequence:

```text
1. Validate filename
2. Validate extension
3. Validate MIME policy
4. Read file / enforce upload limit
5. Generate document UUID
6. Generate durable storage_key
7. Persist source artifact
8. Create Document row with UPLOADED
9. Create IngestionJob
10. Move Document -> PROCESSING
11. Parse / chunk
12. Attach document_id + source/page metadata to every chunk
13. Add chunks to FAISS
14. Persist document_chunks
15. Update page_count
16. Update chunk_count
17. Update checksum
18. Move Document -> INDEXED
19. Mark IngestionJob -> SUCCEEDED
20. Return document resource response
```

On failure:

```text
Document -> FAILED
IngestionJob -> FAILED
failure_reason <- safe failure message
artifact remains available when useful for retry
```

Do not silently swallow database persistence failures anymore.

A database failure in the V2.2 durable path is a real upload/processing failure.

---

# 9. Page Count Semantics

Do not calculate page count from chunk count.

For PDF ingestion:

- page count = number of source pages when known
- chunk count = number of chunk records produced

These are different measurements.

The existing V2.1 upload persistence path incorrectly used:

```python
page_count=len(chunks)
```

Replace that behavior.

---

# 10. Checksum

Calculate:

```text
SHA-256(source artifact bytes)
```

and store it as `checksum_sha256`.

This provides deterministic file identity information and supports future deduplication/reprocessing work.

Do not make deduplication a V2.2 feature unless the existing architecture already supports it cleanly.

---

# 11. Vector Metadata Contract

Every indexed chunk must carry enough metadata for the vector layer to identify its document.

At minimum include:

```python
{
    "document_id": str(document.id),
    "workspace_id": str(document.workspace_id),
    "source": original_filename,
    "page": page_number,
    "chunk_index": chunk_index,
}
```

The vector layer must not become the system of record.

PostgreSQL remains authoritative for document/resource state.

FAISS remains a search representation.

---

# 12. Vector Deletion Requirement

Add a document-scoped deletion capability behind the vector-store abstraction.

Target behavior:

```python
delete_documents_by_document_id(document_id)
```

The implementation must remove all FAISS entries belonging to the document.

Do not expose raw FAISS mutation logic from routes.

Do not delete the complete FAISS store when deleting one document.

If the current FAISS implementation cannot safely remove individual vectors, implement a controlled rebuild path from the surviving indexed documents rather than silently leaving stale entries.

The final implementation must satisfy:

```text
DELETE document
        |
        +-- no DB document
        +-- no DB chunks
        +-- no ingestion jobs for deleted resource
        +-- no source artifact
        +-- no vector records
```

---

# 13. Repository Layer Changes

Modify:

```text
backend/repositories/document_repository.py
backend/repositories/document_chunk_repository.py
backend/repositories/ingestion_job_repository.py
```

Required capabilities:

### DocumentRepository

Add/update methods for:

```text
get_by_id
get_by_workspace_paginated
count_by_workspace
create
update
update_status
delete
```

The repository must remain limited to database access.

Do not put:

- HTTPException
- FastAPI Request handling
- authorization policy
- filesystem operations
- FAISS logic

inside repositories.

### DocumentChunkRepository

Add:

```text
get_by_document
count_by_document
delete_by_document
bulk_create
```

### IngestionJobRepository

Add:

```text
get_by_document
get_latest_by_document
create
update_status
delete_by_document
```

Use bulk deletion where it is safe and clear.

---

# 14. Service Layer

Modify:

`backend/services/document_service.py`

The service is the coordination boundary.

It should expose operations equivalent to:

```text
create_document(...)
get_document(...)
get_workspace_documents(...)
rename_document(...)
delete_document(...)
ingest_document(...)
retry_document(...)
```

Do not make routes coordinate:

- repositories
- filesystem
- FAISS
- transaction boundaries

The service coordinates those pieces.

---

# 15. Rename API

Add:

```http
PATCH /documents/{document_id}
```

Request:

```json
{
  "display_name": "My Research Notes"
}
```

Validation:

- 1 to 255 characters
- reject blank/whitespace-only names
- trim surrounding whitespace

Renaming changes the user-facing display name.

It must NOT:

- rename the permanent storage key automatically
- change the source checksum
- recreate chunks
- re-embed the document

---

# 16. Get Document API

Keep:

```http
GET /documents/{document_id}
```

Return the complete V2.2 resource metadata.

The public response should expose:

```json
{
  "id": "...",
  "workspace_id": "...",
  "filename": "...",
  "original_filename": "...",
  "display_name": "...",
  "file_type": "...",
  "mime_type": "application/pdf",
  "file_size": 12345,
  "page_count": 10,
  "chunk_count": 24,
  "status": "INDEXED",
  "failure_reason": null,
  "created_at": "...",
  "updated_at": "..."
}
```

Do not expose:

- absolute server filesystem paths
- secrets
- internal stack traces
- database credentials

---

# 17. List Documents API

Keep:

```http
GET /documents/?workspace_id=<uuid>&page=1&page_size=20
```

Return:

```text
documents
pagination
```

Ordering should remain deterministic, preferably newest first as in V2.1.

---

# 18. Delete API

Keep:

```http
DELETE /documents/{document_id}
```

The service must coordinate all cleanup.

Logical sequence:

```text
1. Find document
2. Confirm requested workspace boundary when applicable
3. Identify storage artifact
4. Remove vector entries
5. Remove chunk records
6. Remove ingestion jobs
7. Remove artifact
8. Remove document record
9. Commit
```

The implementation must be safe against already-missing physical files.

A missing artifact should not automatically make the database delete fail if all authoritative metadata/index cleanup can still complete.

The deletion invariant is absolute:

```text
After successful DELETE:
- metadata lookup -> not found
- chunk lookup -> no chunks
- ingestion-job lookup -> no jobs
- vector search -> document cannot be retrieved
- artifact path -> absent
```

---

# 19. Workspace Boundary

V2.2 must preserve the existing workspace/resource boundary.

Every document belongs to a workspace.

Do not implement the full V2.6 authentication system here.

Do not invent user authentication while implementing V2.2.

However, document operations must not accidentally operate across workspaces.

The route/service contract should carry enough workspace context to prevent an unintended cross-workspace document operation.

Full authenticated authorization belongs to V2.6.

---

# 20. Pydantic Schemas

Modify:

`backend/models/schemas.py`

Add/update:

```python
class RenameDocumentRequest(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=255)
```

Extend `DocumentResponse` with:

```text
display_name
mime_type
chunk_count
failure_reason
```

Keep:

```text
id
workspace_id
filename
original_filename
file_type
file_size
page_count
status
created_at
updated_at
```

Use:

```python
model_config = ConfigDict(from_attributes=True)
```

for ORM responses.

Consider whether `DocumentUploadResponse` should return the complete document resource. Prefer a stable resource response for V2.2 rather than keeping upload as a special V1-only response.

---

# 21. Alembic Migration

Create one additive V2.2 migration.

Do not modify the V2.1 migration file:

```text
alembic/versions/b56ab54c4f90_create_v2_1_foundation_schema.py
```

The migration should add the new document lifecycle columns required by the implementation.

Before migration:

```powershell
alembic current
```

After migration:

```powershell
alembic upgrade head
alembic current
```

Verify downgrade behavior when practical.

Do not manually edit migration history to hide schema changes.

---

# 22. Tests To Add

Add focused V2.2 tests.

## Model/schema tests

Test:

- new document fields
- enum serialization
- rename request validation
- document response serialization

## Repository tests

Test:

- create document
- list workspace documents
- rename/update
- get chunks
- delete chunks by document
- ingestion-job cleanup

## Service tests

Test:

- document creation
- rename
- successful ingestion
- failed ingestion state
- deletion coordination
- missing physical artifact handling
- workspace mismatch handling

## API tests

Test:

```text
POST /documents/upload
GET /documents/{id}
GET /documents/?workspace_id=...
PATCH /documents/{id}
DELETE /documents/{id}
```

## Deletion invariant test

Create a document with:

- source artifact
- chunks
- ingestion job
- vector entries

Delete it.

Assert all four storage layers are gone.

This is one of the most important V2.2 tests.

## Regression

The existing V1 chat flow must remain functional.

Run the complete suite after implementation.

---

# 23. Frontend Changes

Only after backend tests pass.

Modify:

```text
frontend/index.html
frontend/script.js
frontend/style.css
```

Add:

- document library
- document list/grid
- Processing / Ready / Failed badges
- display-name rename
- delete confirmation
- document details
- upload progress
- retry action
- thicker, more comfortable scrollbar

Do not redesign the entire UI.

Do not break the existing chat interface.

---

# 24. Remove/Change V1 Behavior Carefully

The following V1 behaviors must not remain as the normal V2.2 resource workflow:

```text
temporary source file immediately deleted after processing
optional DB persistence
single global document clear used as normal deletion
page_count == chunk_count
database persistence failure silently ignored
```

The existing `/documents/clear` endpoint may remain temporarily for compatibility/testing, but it must not be used by the V2.2 document library to delete individual resources.

---

# 25. Implementation Order

Execute in this order:

### Phase A — Contract

1. Inspect current model imports/usages.
2. Inspect current schema usages.
3. Define new document fields.
4. Define lifecycle behavior.
5. Define upload/get/list/rename/delete contracts.

### Phase B — Database

6. Update `Document`.
7. Create Alembic migration.
8. Upgrade database.
9. Add/update model tests.

### Phase C — Storage

10. Add durable artifact storage helper.
11. Implement safe path handling.
12. Implement checksum calculation.
13. Add storage tests.

### Phase D — Vector identity

14. Ensure indexed chunks contain `document_id` and `workspace_id`.
15. Implement document-scoped vector deletion/rebuild behavior.
16. Add vector lifecycle tests.

### Phase E — Service

17. Refactor upload/ingestion coordination into `DocumentService`.
18. Implement rename.
19. Implement deletion coordination.
20. Implement retry semantics only where the existing ingestion-job model supports it safely.

### Phase F — API

21. Update upload.
22. Update get/list.
23. Add PATCH rename.
24. Update DELETE.
25. Update schemas/contracts.

### Phase G — Tests

26. Run focused tests.
27. Fix failures.
28. Run full regression suite.
29. Run health/readiness/OpenAPI checks.

### Phase H — Frontend

30. Document library.
31. Rename.
32. Delete.
33. Status.
34. Detail metadata.
35. Upload progress.
36. Retry.
37. Scrollbar polish.

### Phase I — Checkpoint

38. `git diff --check`
39. `git status`
40. Full `pytest -q`
41. Verify Alembic head.
42. Commit a focused V2.2 checkpoint.

Suggested commit:

```text
feat: implement V2.2 document lifecycle foundation
```

---

# 26. Non-Negotiable Constraints

Do NOT:

- rewrite the application
- rewrite V2.1 migration history
- replace FAISS without evidence
- put RAG logic into repositories
- put filesystem logic into repositories
- put HTTPException into repositories
- add authentication as a V2.2 side project
- add LangGraph
- add agents
- add web search
- add streaming
- add general tool calling
- expose secrets
- silently swallow persistence errors
- claim completion without running the tests
- delete duplicate model files blindly

Keep V1 rollback-capable.

Keep V2 work on `v2-development`.

Use additive migrations.

---

# 27. Definition of Done

V2.2 is complete only when all of these are true:

```text
[ ] Documents have durable IDs and metadata
[ ] Source artifacts persist after successful ingestion
[ ] storage_key is stable and safe
[ ] SHA-256 checksum is stored
[ ] page_count and chunk_count are distinct
[ ] failures are represented explicitly
[ ] document_id exists in vector metadata
[ ] individual document vector cleanup works
[ ] list/get/rename/delete work
[ ] document deletion cleans DB + chunks + jobs + vectors + artifact
[ ] deletion invariant has automated tests
[ ] upload no longer silently ignores DB failures
[ ] API contracts are tested
[ ] V1 regression tests pass
[ ] full test suite passes
[ ] Alembic is at the new V2.2 head
[ ] git diff --check passes
[ ] working tree is clean after commit
[ ] focused V2.2 commit exists
```

---

# 28. First Coding Session

Do not edit everything at once.

Start with these files only:

```text
backend/models/db/document.py
backend/models/schemas.py
alembic/versions/<new_v2_2_revision>.py
```

First goal:

**Make the V2.2 document data contract correct.**

Then run the migration and model/schema tests before changing upload, FAISS, or frontend behavior.

The implementation should proceed one verified layer at a time.
