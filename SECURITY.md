# Security Policy

The **Rorak AI** project prioritizes data security, LLM safety, and secure system design. This document outlines our security measures and how to report vulnerabilities.

---

## 🛡️ Built-in Security Architecture

Rorak AI incorporates defense-in-depth safety controls across the stack:

1. **Prompt Injection Hardening & Data Sandboxing**:
   - Document context is strictly encapsulated within `<context>` XML blocks and treated as **UNTRUSTED DATA**.
   - System instructions explicitly forbid the LLM from executing commands or instructions discovered inside user-uploaded documents.
   - System prompts, secrets, and internal variables are guarded against extraction attempts.

2. **File Ingestion Protection**:
   - **Extension Validation**: Strictly enforces `.pdf` file format validation.
   - **Payload Size Limits**: Enforces a strict 10 MB maximum upload size limit (`MAX_UPLOAD_SIZE_BYTES`).
   - **Ephemeral Storage**: Uploaded files are processed and indexed into vector representations, then immediately removed (`unlink`) from disk storage.
   - **Corrupt File Handling**: Safely catches corrupt or encrypted PDF streams without crashing worker processes.

3. **Abuse Prevention & Rate Limiting**:
   - Built-in sliding-window in-memory rate limiter protects endpoints against automated scraping and denial-of-service attempts.

4. **Credential & Secret Protection**:
   - Safe log formatter automatically detects and redacts sensitive API key patterns (e.g. `gsk_...`) from output logs.
   - `.env` and local credential files are ignored by `.gitignore`.

---

## 🚨 Reporting a Vulnerability

If you discover a security vulnerability or prompt security concern within Rorak AI, please **do not open a public GitHub issue**.

Instead, please report the vulnerability privately by contacting the maintainer via email:
- **Email**: [rohitsaini11100@gmail.com](mailto:rsaini2407@gmail.com)

### What to include in your report:
- Type of issue (e.g., prompt injection leak, buffer overflow, SSRF, denial of service).
- Step-by-step instructions or sample payloads to reproduce the issue.
- Impact assessment.

We will acknowledge receipt of your vulnerability report within 48 hours and provide updates on resolution.
