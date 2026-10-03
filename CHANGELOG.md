# Changelog

All notable changes to this project are documented here.
The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project follows [Semantic Versioning](https://semver.org/).

## [2.0.0] — Unreleased

Rorak v2 turns the single-session PDF Q&A prototype into a multi-user assistant with persistent state.

### Added
- User accounts: registration (with display name), login, and JWT bearer authentication.
- Per-user isolation of conversations, documents, and memories.
- Persistent conversations and message history in PostgreSQL, with a bounded context window.
- Long-term memory: CRUD API plus automatic extraction of user facts and preferences from chat, with credential screening and de-duplication.
- Document library: list, rename, inspect, and delete uploaded files; documents are scoped to the conversation they were uploaded in.
- Pluggable parser registry with adapters for DOCX, TXT, Markdown, and table-aware CSV in addition to PDF.
- Alembic migrations, readiness probe with database status, Docker Compose stack, and CI against PostgreSQL.
- "Files in chat" drawer in the web client.

### Changed
- Prompt assembly now combines memory, recent history, and retrieved context in separate XML-delimited sections.
- Upload limit and supported types are enforced server-side for all formats.
- Container image runs as a non-root user and ships migrations.

### Removed
- Unauthenticated `/users` endpoints from the pre-auth prototype.
- Global `POST/DELETE /documents/clear` in favour of per-document deletion.

## [1.0.0] — 2026-09-07

Initial public release.

### Added
- Two-stage RAG pipeline: FAISS retrieval with cross-encoder reranking and Groq inference.
- Prompt-injection hardening via XML-sandboxed context.
- PDF upload and indexing; general-assistant fallback when no document is loaded.
- Dark-theme web client with sanitized Markdown rendering.
- Per-IP rate limiting, health/readiness probes, and GitHub Actions CI.

[2.0.0]: https://github.com/roraks24/rorak_ai/compare/main...v2-development
[1.0.0]: https://github.com/roraks24/rorak_ai/tree/main
