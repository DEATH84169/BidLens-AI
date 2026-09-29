# Security scope

This is a single-officer pilot. Data endpoints require X-BidLens-Key; the key and officer identity are server-configured. Health output does not claim certification.

Never commit real keys, bidder documents, databases or private publisher configuration. Use TLS for remote deployments and persistent protected storage. Provider keys belong only on the server.

Hashes detect some evidence changes, not administrator replacement, truncation or source forgery. Production requires independent log anchoring, individual SSO/RBAC, tenant isolation, retention/encryption policies, malware controls and resource limits. Uploaded signatures are not treated as cryptographic signatures.

Report issues privately to the fork maintainer using an available private GitHub reporting channel. Do not publish identifiers or credentials in issues.
