# Datasets and test evidence

## Real public reference added

`backend/data/nic2008_selected.json` contains **11 selected MoSPI NIC 2008 division labels**, transcribed from the [official Sixth Economic Census classification page](https://www.mospi.gov.in/sites/default/files/6ec_dirEst/ec6_nic_2008_code.html) on 29 September 2026. Publisher, source URL, edition, extraction method and coverage limitations are retained. The additive `/system/reference/nic2008/{code}` endpoint exposes the lookup (for example `/system/reference/nic2008/26`).

This is a historical classification reference, not the latest NIC edition, not a full code list and not bidder verification data. Use only for documents explicitly using NIC 2008. The project's MIT license does not relicense government source material. No personal data is included.

## Udyam catalogue discovered, not downloaded

The [OGD List of MSME Registered Units under UDYAM](https://www.data.gov.in/resource/list-msme-registered-units-under-udyam) offers state/district filters and says download requires login. No authorized export was supplied, so no firm records were added. Future imports must preserve source, time, coverage and identity. Historical matches cannot prove current status; missing matches cannot disqualify bidders.

## Synthetic cases

Existing sample bids and the existing offline sample cache remain available. They are synthetic demonstration material. Cached government outcomes are relabelled SIMULATED and cannot automatically shortlist a bidder. Tests in `backend/tests` cover the adapter with mocked HTTP responses and the original workflow with synthetic examples.

Aggregate MSME statistics may support analytics, but cannot replace authorized, current verification of an individual bidder. No dataset obtained in this work establishes all PS checks.
