# Security

Use a dedicated ordinary customer account. v0.1 authenticates with an account login token,
not a separately scoped API key. Token files are access-restricted plaintext, not encrypted vaults.
Do not store them in this repository or a shared/synchronized directory. The client does not store passwords.

Never share passwords, access tokens, provider API keys, request headers or signed media URLs
in a public issue. Report a vulnerability through GitHub's private vulnerability reporting feature
when available; otherwise use the customer-support channel within the platform without attaching secrets.

API requests refuse redirects. Upload/download requests to object storage do not receive the platform
Authorization header. HTTPS is required except for loopback development deployments.
The CLI performs no automatic request replay. On interrupted creation, inspect the saved session first.
