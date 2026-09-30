# API Setu integration: readiness and access

API Setu is a sensible replacement for hardcoded verification after approved access. It is a marketplace with publisher-specific subscriptions and contracts, not one open endpoint for all statutory checks. Official documentation discusses organization PAN, GST verification and consent-based document services.

## Current fork status

- A contract-configured transport is implemented and tested with HTTP mocks.
- No approved subscription, key, publisher endpoint or schema was supplied. No live verification has been performed or certified.
- The example configuration intentionally contains invalid placeholders. No production endpoint or response schema was invented.
- Responses must match the requested identifier and an explicitly configured status. Only the named check is verified: PAN does not prove Income Tax filing, and GST registration does not prove return filing.
- Set BIDLENS_VERIFICATION_MODE to live, sandbox or demo on the backend. Sandbox/demo never establishes source verification or automatic shortlisting; the original officer review UI is preserved. Missing access, errors and unknown responses remain `NOT_VERIFIED`.
- On 29 September 2026 the official PAN sandbox collection displayed “Selected API Coming Soon in Sandbox.” The sandbox also states that requests do not use live data.

## Obtain access

1. Register an eligible organization at the partner portal using an authorized representative. Students should coordinate with their institution/incubator or sponsor rather than invent a company identity.
2. Request the exact publisher service for vendor verification. Confirm permitted use, any pricing, volume and retention terms.
3. Obtain approval, credentials and the current specification. Confirm the environment and which claims the service establishes.
4. Implement consent/OAuth for user-specific services. This fork does **not** implement DigiLocker OAuth. Do not manufacture consent flags or treat API credentials as bidder consent.
5. Store provider keys in the backend secret environment, never in the browser or repository.

## Configure the adapter

Copy `backend/integrations/apisetu.example.json` outside Git as `apisetu.private.json`. Replace every placeholder from the approved specification:

- `url`: exact HTTPS lookup endpoint. Redirects are disabled. Only API Setu government domains are currently accepted. Publisher-owned hosts require a reviewed adapter/host policy.
- `method`: documented GET or POST. Supported transport is flat JSON POST or GET query parameters with environment-supplied auth headers. Signed/encrypted requests, nested bodies, OAuth and file responses need publisher-specific implementation.
- `headers_from_env`: documented header names mapped to environment-variable names. Values do not belong in JSON.
- `identifier_parameter`: documented request subject field.
- `fixed_parameters`: approved non-secret scope such as an exact filing period. Never fabricate consent here.
- `response_identifier_pointer`, `response_status_pointer`: exact RFC 6901 response pointers.
- `verified_values`, `failed_values`: explicit documented statuses. HTTP success or a missing record does not itself establish compliance or failure.
- `environment`: `sandbox` or `production`. Never relabel sandbox as production.

Set `APISETU_CONFIG_PATH` to the absolute private config path, supply the named secrets and restart. Validate the provider's approved cases, identity, status, period, freshness and adverse outcomes. Disable checks whose contracts cannot substantiate the claim. Filing-period/certificate-validity semantics beyond this generic transport must be implemented for each publisher before production use.

The existing six verification cards are preserved. Configuration keys are `gst`, `pan`, `mca`, `udyam`, `epfo_esic` and `debarment`. Current document extraction supplies PAN, GSTIN and Udyam; dedicated MCA and labour identifiers still need extraction support. Do not map a single EPFO response to combined EPFO/ESIC compliance. Leave that combined card unconfigured unless a reviewed contract covers both. A debarment no-match is not a universal clearance.

The original `/audit/run` request uses `file_id` and `tender_id`. An optional `tender_requirements` object now passes the active RFP thresholds from the existing UI. This is a local prototype: original in-memory assessments and officer controls remain, with no new authentication or SQLite migration.

## Evidence and limitations

Configured lookups record environment, source, timestamp, HTTP status where available and response SHA-256. Provider bodies and keys are not returned to the UI. A response hash is trace metadata, not an issuer signature or complete source archive. Production retention needs permitted, encrypted source evidence.

Tests cover success/adverse status, subject mismatch, malformed/unmapped responses, authorization errors, rate limits, server errors, timeout, missing keys, invalid hosts and sandbox isolation. These are mock contract tests, not live API Setu tests.

## Primary sources checked

- [Marketplace and access flow](https://docs.apisetu.gov.in/document-central/explore-apisetu/Overview.html)
- [Official onboarding SOP](https://www.apisetu.gov.in/sop)
- [Permitted use](https://docs.apisetu.gov.in/document-central/terms-of-use/Permitted%20Use%20and%20Access.html)
- [Official sandbox](https://sandbox.api-setu.in/)
- [PAN sandbox collection](https://sandbox.api-setu.in/org-collections/pan)

API Setu (`apisetu.gov.in`) and commercial Setu (`setu.co`) are different services.
