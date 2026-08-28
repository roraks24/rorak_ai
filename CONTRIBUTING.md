# Contributing to Rorak AI

Thank you for your interest in contributing to **Rorak AI**! We welcome contributions, bug fixes, feature suggestions, and documentation improvements.

---

## 📋 Code of Conduct

All contributors and maintainers are expected to adhere to our [Code of Conduct](CODE_OF_CONDUCT.md). Please read it before participating.

---

## 🛠️ Development Setup

### 1. Prerequisites
- **Python**: 3.11 or 3.12 (recommended)
- **Git**
- **Groq API Key**: Obtain from [Groq Console](https://console.groq.com/)

### 2. Fork & Clone
```bash
git clone https://github.com/roraks24/rorak_ai.git
cd rorak_ai
```

### 3. Create Virtual Environment
```bash
python -m venv .venv

# On Linux / macOS:
source .venv/bin/activate

# On Windows:
.venv\Scripts\activate
```

### 4. Install Dependencies
```bash
pip install -r requirements.txt
```

### 5. Configure Environment Variables
Copy `.env.example` to `.env` and configure your API key:
```bash
cp .env.example .env
```
Edit `.env`:
```env
GROQ_API_KEY=gsk_your_groq_api_key_here
```

### 6. Run the Test Suite
Ensure the existing tests pass before making any modifications:
```bash
pytest -v
```

---

## 🌿 Branching Strategy & Workflow

1. **Create a branch** for your work from `main`:
   ```bash
   git checkout -b feature/my-new-feature
   # or
   git checkout -b fix/issue-description
   ```
2. **Make your changes** following clean coding standards:
   - Follow **PEP 8** style guidelines for Python code.
   - Include descriptive docstrings and type annotations.
   - Keep functions focused and modular.
   - Ensure sensitive information (keys, passwords) is never committed.
3. **Write or update tests** in the `tests/` directory for any new logic or bug fixes.
4. **Run all tests** locally:
   ```bash
   pytest -v
   ```
5. **Commit your changes** using conventional commit messages:
   - `feat: add support for docx document ingestion`
   - `fix: resolve rate limiter sliding window edge case`
   - `docs: update quickstart instructions in README`
   - `test: add unit tests for reranker fallback`
6. **Push to your fork** and submit a **Pull Request**.

---

## 📝 Pull Request Guidelines

When submitting a PR:
- Fill out the provided [Pull Request Template](.github/PULL_REQUEST_TEMPLATE.md).
- Reference any related issues (e.g., `Fixes #12`).
- Ensure all CI tests pass.
- Keep PRs focused on a single change or cohesive feature.

---

## 💬 Questions & Community

Have questions or need assistance? Open a [Discussion](https://github.com/roraks24/rorak_ai/discussions) or create an [Issue](https://github.com/roraks24/rorak_ai/issues).
