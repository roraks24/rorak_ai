# Contributing to Rorak AI

Thanks for your interest in improving Rorak AI! This guide explains how to set up a development environment and get a change merged.

## Ground rules

- Be respectful — this project follows the [Code of Conduct](CODE_OF_CONDUCT.md).
- For anything larger than a small fix, please [open an issue](https://github.com/roraks24/rorak_ai/issues) first so we can agree on the approach.
- Never commit secrets, `.env` files, or uploaded documents.

## Development setup

Prerequisites: Python 3.12+, PostgreSQL 14+, and a [Groq API key](https://console.groq.com/keys). Alternatively use Docker Compose (see the [README](README.md#getting-started)).

```bash
git clone https://github.com/<your-username>/rorak_ai.git
cd rorak_ai
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install --extra-index-url https://download.pytorch.org/whl/cpu -r requirements-dev.txt
cp .env.example .env                                   # set DATABASE_URL, GROQ_API_KEY, JWT_SECRET_KEY
alembic upgrade head
pytest -q
```

## Making changes

1. Create a branch from `main`: `git checkout -b feat/short-description`.
2. Keep the existing layering: **routes → services → repositories**. Routes handle HTTP only; database access goes through repositories; every query that returns user data must be scoped to the authenticated user.
3. Add or update tests for your change. Tests run against a real PostgreSQL database.
4. If you change a SQLAlchemy model, add a migration:
   ```bash
   alembic revision --autogenerate -m "describe the change"
   alembic upgrade head
   ```
   Review the generated file before committing.
5. Update documentation (`README.md`, `docs/ARCHITECTURE.md`, `.env.example`) when behaviour or configuration changes, and add an entry under *Unreleased* in `CHANGELOG.md`.

### Adding a document format

Implement `DocumentParser` in `backend/parsers/adapters/`, register it in `backend/parsers/registry.py`, add the extension to `ALLOWED_EXTENSIONS` in `backend/core/config.py`, and add parser tests.

## Code style

- Python: follow PEP 8, use type hints on public functions, and prefer small, focused functions.
- Use `logging`, not `print`. Never log message contents, tokens, or file contents.
- Frontend: plain ES5/ES6 JavaScript with no build step; escape any user-provided content inserted into the DOM.

## Commit messages

We use [Conventional Commits](https://www.conventionalcommits.org/):

```
feat(parsers): add XLSX adapter
fix(auth): reject expired tokens with 401
docs: clarify docker setup
test(memory): cover duplicate detection
```

## Pull requests

- Fill in the [pull request template](.github/PULL_REQUEST_TEMPLATE.md) and link related issues (`Fixes #123`).
- Keep PRs focused on one change.
- CI must pass before review.

## Questions

Open a [GitHub issue](https://github.com/roraks24/rorak_ai/issues) with the `question` label.
