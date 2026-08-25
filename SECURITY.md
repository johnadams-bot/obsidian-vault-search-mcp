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
- Example templates use placeholder values

### Code Security
- User input is properly escaped using `escapeHtml()`
- No `eval()`, `document.write()`, or dynamic function execution
- Minimal permission principle for workspace access

### Dependency Security
- Regular `npm audit` and `pip audit` checks
- Dependencies kept up to date
- No known vulnerable packages

## Compliance

This project follows these security best practices:
- [ ] OWASP Top 10 mitigation
- [ ] Secret scanning enabled
- [ ] Dependency review enabled
- [ ] Code scanning (where applicable)

---

*Last updated: 2026-08-25*
