# Security Policy

## Supported Versions

| Version | Supported |
|---------|-----------|
| All versions | ✅ |

## Reporting a Vulnerability

We take security vulnerabilities seriously. If you discover a security issue, please follow these steps:

1. **DO NOT** open a public GitHub issue
2. Email the maintainers directly or use GitHub's private vulnerability reporting
3. Include details about the vulnerability and how to reproduce it
4. Allow time for the issue to be fixed before any disclosure

## Security Measures

### API Key Management
- All API keys are stored locally in `.env` files
- `.env` files are excluded from Git via `.gitignore`
- No hardcoded credentials in source code
- Example templates use placeholder values (`***`)

### Code Security
- Uses Python standard library only (zero dependencies)
- No `eval()`, `exec()`, or dynamic function execution
- User input is properly sanitized
- SQLite queries use parameterized statements

### Data Privacy
- All indexes stored locally (SQLite)
- No data sent to external servers without explicit LLM configuration
- Private by default - works offline without API keys

## Compliance

This project follows these security best practices:
- [x] No hardcoded credentials
- [x] Sensitive files excluded from Git
- [x] Local-first architecture
- [x] OpenAI-compatible API usage with user-provided keys

---

*Last updated: 2026-08-25*
