# Security Policy

## Supported versions

| Version | Supported |
| --- | --- |
| 2.x | ✅ |
| 1.x | ❌ |

## Reporting a vulnerability

**Please do not report security issues through public GitHub issues.**

Use GitHub's [private vulnerability reporting](https://github.com/roraks24/rorak_ai/security/advisories/new), or email **[rsaini2407@gmail.com](mailto:rsaini2407@gmail.com)** with:

- a description of the issue and its impact,
- steps or a proof of concept to reproduce it,
- the affected version or commit.

You can expect an acknowledgement within 72 hours. Once the issue is confirmed, we will work on a fix and coordinate disclosure with you. Reporters are credited in the release notes unless they prefer otherwise.

## In scope

- Authentication or authorization bypass (e.g. accessing another user's conversations, documents, or memories)
- Prompt injection that leaks system prompts, other users' data, or secrets
- Injection, path traversal, or unsafe file handling in document uploads
- Exposure of credentials or personal data in logs or responses

## Security design

An overview of the security controls (password hashing, JWT handling, ownership checks, untrusted-context prompting, memory secret screening, rate limiting) is in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md#security-model).

## Deployment checklist

- Set `ENVIRONMENT=production` and a strong, random `JWT_SECRET_KEY`.
- Serve the API over HTTPS only and restrict CORS origins to your frontend domains.
- Use a dedicated PostgreSQL user with least privilege and keep backups.
- Keep `GROQ_API_KEY` and other secrets in a secret manager, never in the image or repository.
