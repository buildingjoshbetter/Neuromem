# Security Policy

## Reporting a Vulnerability

If you discover a security vulnerability in TrueMemory, please report it responsibly:

1. **Do not** open a public GitHub issue.
2. Email **security@sauronlabs.ai** with a description of the vulnerability.
3. Include steps to reproduce if possible.

We will acknowledge receipt within 48 hours and provide a fix timeline within 7 days.

## Scope

TrueMemory is a local-first memory system. The MCP server is single-tenant stdio — `user_id` is a tag for organizing memories, not an access control boundary. Do not expose the MCP server to untrusted clients or networks.
