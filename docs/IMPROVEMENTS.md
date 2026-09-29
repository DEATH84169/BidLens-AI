# Changes in this fork

Baseline: upstream `f2977293a36a6806f7bc767fdfddce444f08833a`.

- Replaced fabricated registry passes with explicit evidence states and contract-configured API Setu transport.
- Removed keyword-based exemptions and GST cancellation inferences. Kept claims and source verification separate.
- Bound saved tender versions to evaluators; fixed warranty, EMD, budget and missing-quote errors.
- Added bidder attachment sets, evidence snippets and unread-page reporting; removed page sampling.
- Added SQLite snapshots, hash-linked events, hash checks and recalculation after overrides.
- Added officer-key authentication. This is a single-identity pilot, not individual SSO/RBAC.
- Connected the dashboard to source checks and persisted officer decisions; removed fabricated demo fallback.
- Corrected PDF tender identification and included every registry check without certification claims.
- Added official reference provenance and synthetic regression cases.
- Removed deployment routes to the upstream backend and expanded tests/CI.

The old UI's disconnected demo views were replaced by one connected review workflow. Precomputed value spotlights, signature images and fake live verification are not carried forward. Original source remains in Git history; existing synthetic sample documents remain available.

API v2 uses `file_ids` and `tender_version_id`, requires tender confirmation and protects downloads with the officer key. Old clients must migrate. The original project's repository and live deployment are untouched.
