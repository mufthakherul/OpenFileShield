# Security Policy

## Supported Versions

This is an early-stage project. Security fixes are applied on the `main` branch.

## Reporting A Vulnerability

Please do not open public issues for critical vulnerabilities.
Instead, send a private report to your designated project security contact.

## Hardening Recommendations

- Keep ClamAV signatures updated.
- Put the app behind HTTPS only.
- Restrict upload size and allowed file types when possible.
- Rotate admin token regularly.
- Back up the SQLite database and upload metadata securely.
- Add rate limiting and bot protection at reverse proxy level.
