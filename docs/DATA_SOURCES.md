# Datasets and test evidence

## Real public reference added

`backend/data/nic2008_selected.json` contains **11 selected MoSPI NIC 2008 division labels**, transcribed from the [official Sixth Economic Census classification page](https://www.mospi.gov.in/sites/default/files/6ec_dirEst/ec6_nic_2008_code.html) on 29 September 2026. Publisher, source URL, edition, extraction method and coverage limitations are retained. The authenticated `/system/reference/nic2008/{code}` endpoint and dashboard expose the lookup.

This is a historical classification reference, not the latest NIC edition, not a full code list and not bidder verification data. Use only for documents explicitly using NIC 2008. The project's MIT license does not relicense government source material. No personal data is included.

## Udyam catalogue discovered, not downloaded

The [OGD List of MSME Registered Units under UDYAM](https://www.data.gov.in/resource/list-msme-registered-units-under-udyam) offers state/district filters and says download requires login. No authorized export was supplied, so no firm records were added. Future imports must preserve source, time, coverage and identity. Historical matches cannot prove current status; missing matches cannot disqualify bidders.

## Synthetic cases

`data/test_cases/compliance_regressions.json` describes synthetic regression scenarios, not government data. `backend/tests/test_core.py` exercises these categories with generated PDFs and mocked HTTP responses. Existing sample bids are demonstration material, not authentic certificates. The new dashboard has no precomputed-result fallback.

Aggregate MSME statistics may support analytics, but cannot replace authorized, current verification of an individual bidder. No dataset obtained in this work establishes all PS checks.
