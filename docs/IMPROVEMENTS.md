# Incremental improvements on the original application

The original upstream application at `f297729` is the baseline. The replacement workspace introduced in `424c099` has been removed following user feedback. All original screens, CSS, navigation, vendor comparison, sample loading, re-evaluation, shortlist, signature controls and PDF layout are retained.

Targeted additions and fixes:
- API Setu transport behind the existing six gateway cards. No fabricated ACTIVE, operative, labour clearance or debarment results.
- Unconfigured services are NOT_VERIFIED; cached offline samples are labelled synthetic and their registry outcomes SIMULATED.
- The existing RFP thresholds now travel with all five audit request paths. Warranty compares numeric years; EMD needs an explicit amount; claimed MSE exemptions require officer review.
- Missing source checks prevent automatic shortlisting. Existing manual officer workflows remain.
- Value comparison uses the selected tender budget and handles a missing quote.
- PDF includes the selected tender reference and all six gateway cards.
- Attributed NIC 2008 reference subset and lookup endpoint; not bidder verification data.
- Local proxy default, provider secret configuration, dependency security patches and regression tests.

No production API Setu approval or credentials were supplied. Live contracts still require publisher-specific validation. This is not a complete remediation of the earlier audit: original in-memory state, extraction heuristics and page sampling, unauthenticated local prototype routes, manual decisions, and several presentation/legal claims still need separate incremental work. Do not publicly deploy or treat it as an authoritative eligibility system. The previous 42-test report applied to the superseded rewrite; run the current suite for this version.
