# Security Policy

ARGO is local-first and treats your machine as the trust boundary. Security is a
core feature, not an afterthought (see the full Italian report in
[`SICUREZZA_REPORT.md`](SICUREZZA_REPORT.md)).

## What ARGO guarantees

- **Local only.** The API binds to `127.0.0.1`. No data leaves the machine.
- **Sensitive data is never touched.** Files and content matching secret/credential
  patterns are detected and skipped — never read, indexed, or moved.
- **Tamper-evident audit.** Every action is recorded in a hash-chained log that can
  be exported and verified (`/audit`, `/audit/export`).
- **Key protection.** The local key is protected via Windows DPAPI; encryption at
  rest is available when the optional `cryptography` package is installed.
- **Governed actions.** A runtime policy engine and role-based access control gate
  what ARGO may do; every action is reversible via rollback.

## Reporting a vulnerability

Please **do not** open a public issue for security problems.

Instead, report privately via GitHub's "Report a vulnerability" (Security advisories)
on the repository, or contact the maintainer directly. Include:

- a description and impact assessment,
- steps to reproduce or a proof of concept,
- affected version / commit.

We aim to acknowledge reports within a few days and to coordinate a fix and
disclosure timeline with you.

## Supported versions

ARGO is in active alpha development; security fixes target the `main` branch.
