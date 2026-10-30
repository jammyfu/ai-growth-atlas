# Security Policy

## Reporting a vulnerability

Please **do not** open a public issue for security problems.
Use GitHub's private reporting: **Security → Report a vulnerability** at
<https://github.com/jammyfu/github-risers/security/advisories/new>

We aim to acknowledge reports within 7 days. Only the latest `main` is supported.

## Scope
This repository contains scripts, data and documentation. The scheduled workflow uses the repository's built-in `GITHUB_TOKEN`; an optional `CURSOR_API_KEY` secret is read only by the translation step. Never commit tokens or keys.
