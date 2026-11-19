# Corporate-action case review

Development set, not an independently held-out confirmation set. No API calls made.
History lengths: 0, 5, 15 irrelevant notices. Decisive terms stay fixed.
Review all 12 templates; the extra history is present in cases.json.

Unreviewed development calls are possible with --allow-unreviewed; leave approval false.
A recorded review requires approved=true and a real reviewer name in review.json.
Approval binds to the cases hash. Independent review is a separate factual field.

## custodian_extension

**Account:** {"accepted_quantity":0,"account":"A","authorised_quantity":100,"certificate_present":true,"eligible_quantity":100,"event":"E","next_request_id":"SUBMIT_R","operation":"elect","option":"CASH"}

- **D0**: Initial terms for Event E/account A, CASH: custodian deadline 2026-11-10T14:00:00Z; certification required; no waiver; elections revocable; CASH permitted. Additive submissions allowed. No unresolved conflict in D0.
- **D1**: Explicit amendment to D0 for Event E: custodian deadline is 2026-11-10T11:00:00Z. Other terms unchanged.
- **D2**: Explicit amendment replacing only the deadline in D1 for Event E: custodian deadline is extended to 2026-11-10T14:00:00Z. Other terms unchanged.

**Reference:** {"action":"submit","allowed_decisions":[{"action":"submit","quantity":100,"request_id":"SUBMIT_R"}],"decisive_ids":["D2"],"quantity":100,"request_id":"SUBMIT_R","target_accepted_quantity":100,"terms":{"cash_permitted":true,"certification_required":true,"certification_waived":false,"conflict":false,"custodian_deadline_utc":"2026-11-10T14:00:00Z","revocable":true}}

Reviewer judgment / rationale: __________

## issuer_only_extension

**Account:** {"accepted_quantity":0,"account":"A","authorised_quantity":100,"certificate_present":true,"eligible_quantity":100,"event":"E","next_request_id":"SUBMIT_R","operation":"elect","option":"CASH"}

- **D0**: Initial terms for Event E/account A, CASH: custodian deadline 2026-11-10T14:00:00Z; certification required; no waiver; elections revocable; CASH permitted. Additive submissions allowed. No unresolved conflict in D0.
- **D1**: Explicit amendment to D0 for Event E: custodian deadline is 2026-11-10T11:00:00Z. Other terms unchanged.
- **D2**: Issuer deadline is extended to 2026-11-10T16:00:00Z. This changes no custodian deadline for Event E.

**Reference:** {"action":"request_late_exception","allowed_decisions":[{"action":"request_late_exception","quantity":0,"request_id":null}],"decisive_ids":["D1"],"quantity":0,"request_id":null,"target_accepted_quantity":0,"terms":{"cash_permitted":true,"certification_required":true,"certification_waived":false,"conflict":false,"custodian_deadline_utc":"2026-11-10T11:00:00Z","revocable":true}}

Reviewer judgment / rationale: __________

## revocation_permitted

**Account:** {"accepted_quantity":100,"account":"A","authorised_quantity":100,"certificate_present":true,"eligible_quantity":100,"event":"E","next_request_id":"SUBMIT_R","operation":"withdraw","option":"CASH"}

- **D0**: Initial terms for Event E/account A, CASH: custodian deadline 2026-11-10T14:00:00Z; certification required; no waiver; elections revocable; CASH permitted. Additive submissions allowed. No unresolved conflict in D0.
- **D1**: Explicit amendment to D0 for Event E/account A: withdrawal is permitted. The applicable withdrawal window is open now.

**Reference:** {"action":"withdraw","allowed_decisions":[{"action":"withdraw","quantity":100,"request_id":"WITHDRAW_R"}],"decisive_ids":["D1"],"quantity":100,"request_id":"WITHDRAW_R","target_accepted_quantity":0,"terms":{"cash_permitted":true,"certification_required":true,"certification_waived":false,"conflict":false,"custodian_deadline_utc":"2026-11-10T14:00:00Z","revocable":true}}

Reviewer judgment / rationale: __________

## revocation_prohibited

**Account:** {"accepted_quantity":100,"account":"A","authorised_quantity":100,"certificate_present":true,"eligible_quantity":100,"event":"E","next_request_id":"SUBMIT_R","operation":"withdraw","option":"CASH"}

- **D0**: Initial terms for Event E/account A, CASH: custodian deadline 2026-11-10T14:00:00Z; certification required; no waiver; elections revocable; CASH permitted. Additive submissions allowed. No unresolved conflict in D0.
- **D1**: Explicit amendment to D0 for Event E/account A: withdrawal is NOT permitted. The applicable withdrawal window is open now.

**Reference:** {"action":"retain_and_notify","allowed_decisions":[{"action":"retain_and_notify","quantity":0,"request_id":null}],"decisive_ids":["D1"],"quantity":0,"request_id":null,"target_accepted_quantity":100,"terms":{"cash_permitted":true,"certification_required":true,"certification_waived":false,"conflict":false,"custodian_deadline_utc":"2026-11-10T14:00:00Z","revocable":false}}

Reviewer judgment / rationale: __________

## timeout_accepted

**Account:** {"accepted_quantity":100,"account":"A","authorised_quantity":100,"certificate_present":true,"eligible_quantity":100,"event":"E","lookup":{"definitive":true,"payload":{"account":"A","event":"E","option":"CASH","quantity":100},"request_id":"R","status":"accepted"},"next_request_id":"R","operation":"elect","option":"CASH"}

- **D0**: Initial terms for Event E/account A, CASH: custodian deadline 2026-11-10T14:00:00Z; certification required; no waiver; elections revocable; CASH permitted. Additive submissions allowed. No unresolved conflict in D0.
- **D1**: Event E: request R previously timed out. Definitive lookup observation for R: accepted, quantity 100 CASH, account A/Event E. No other accepted instructions.

**Reference:** {"action":"retain","allowed_decisions":[{"action":"retain","quantity":0,"request_id":null},{"action":"retry_same_request","quantity":100,"request_id":"R"},{"action":"submit","quantity":100,"request_id":"R"}],"decisive_ids":["D1"],"quantity":0,"request_id":null,"target_accepted_quantity":100,"terms":{"cash_permitted":true,"certification_required":true,"certification_waived":false,"conflict":false,"custodian_deadline_utc":"2026-11-10T14:00:00Z","revocable":true}}

Reviewer judgment / rationale: __________

## timeout_not_found

**Account:** {"accepted_quantity":0,"account":"A","authorised_quantity":100,"certificate_present":true,"eligible_quantity":100,"event":"E","lookup":{"definitive":true,"payload":{"account":"A","event":"E","option":"CASH","quantity":100},"request_id":"R","status":"not_found"},"next_request_id":"R","operation":"elect","option":"CASH"}

- **D0**: Initial terms for Event E/account A, CASH: custodian deadline 2026-11-10T14:00:00Z; certification required; no waiver; elections revocable; CASH permitted. Additive submissions allowed. No unresolved conflict in D0.
- **D1**: Event E: request R previously timed out. Definitive lookup observation for R: not_found. No accepted instruction exists.

**Reference:** {"action":"submit","allowed_decisions":[{"action":"submit","quantity":100,"request_id":"R"}],"decisive_ids":["D1"],"quantity":100,"request_id":"R","target_accepted_quantity":100,"terms":{"cash_permitted":true,"certification_required":true,"certification_waived":false,"conflict":false,"custodian_deadline_utc":"2026-11-10T14:00:00Z","revocable":true}}

Reviewer judgment / rationale: __________

## actual_waiver

**Account:** {"accepted_quantity":0,"account":"A","authorised_quantity":100,"certificate_present":false,"eligible_quantity":100,"event":"E","next_request_id":"SUBMIT_R","operation":"elect","option":"CASH"}

- **D0**: Initial terms for Event E/account A, CASH: custodian deadline 2026-11-10T14:00:00Z; certification required; no waiver; elections revocable; CASH permitted. Additive submissions allowed. No unresolved conflict in D0.
- **D1**: Explicit amendment to D0 for Event E/account A: certification has been waived with immediate effect for this event and account.

**Reference:** {"action":"submit","allowed_decisions":[{"action":"submit","quantity":100,"request_id":"SUBMIT_R"}],"decisive_ids":["D1"],"quantity":100,"request_id":"SUBMIT_R","target_accepted_quantity":100,"terms":{"cash_permitted":true,"certification_required":false,"certification_waived":true,"conflict":false,"custodian_deadline_utc":"2026-11-10T14:00:00Z","revocable":true}}

Reviewer judgment / rationale: __________

## possible_waiver

**Account:** {"accepted_quantity":0,"account":"A","authorised_quantity":100,"certificate_present":false,"eligible_quantity":100,"event":"E","next_request_id":"SUBMIT_R","operation":"elect","option":"CASH"}

- **D0**: Initial terms for Event E/account A, CASH: custodian deadline 2026-11-10T14:00:00Z; certification required; no waiver; elections revocable; CASH permitted. Additive submissions allowed. No unresolved conflict in D0.
- **D1**: Event E: the agent MAY waive certification. No actual waiver has been announced.

**Reference:** {"action":"request_certification","allowed_decisions":[{"action":"request_certification","quantity":0,"request_id":null}],"decisive_ids":["D0","D1"],"quantity":0,"request_id":null,"target_accepted_quantity":0,"terms":{"cash_permitted":true,"certification_required":true,"certification_waived":false,"conflict":false,"custodian_deadline_utc":"2026-11-10T14:00:00Z","revocable":true}}

Reviewer judgment / rationale: __________

## preserved_instruction

**Account:** {"accepted_quantity":100,"account":"A","authorised_quantity":100,"certificate_present":true,"eligible_quantity":100,"event":"E","next_request_id":"SUBMIT_R","operation":"elect","option":"CASH"}

- **D0**: Initial terms for Event E/account A, CASH: custodian deadline 2026-11-10T14:00:00Z; certification required; no waiver; elections revocable; CASH permitted. Additive submissions allowed. No unresolved conflict in D0.
- **D1**: Event E/account A: accepted elections remain valid. Additive submission of only the authorised remaining eligible quantity is permitted. Do not resubmit already accepted quantity.

**Reference:** {"action":"retain","allowed_decisions":[{"action":"retain","quantity":0,"request_id":null}],"decisive_ids":["D1"],"quantity":0,"request_id":null,"target_accepted_quantity":100,"terms":{"cash_permitted":true,"certification_required":true,"certification_waived":false,"conflict":false,"custodian_deadline_utc":"2026-11-10T14:00:00Z","revocable":true}}

Reviewer judgment / rationale: __________

## partial_instruction

**Account:** {"accepted_quantity":60,"account":"A","authorised_quantity":100,"certificate_present":true,"eligible_quantity":100,"event":"E","next_request_id":"SUBMIT_R","operation":"elect","option":"CASH"}

- **D0**: Initial terms for Event E/account A, CASH: custodian deadline 2026-11-10T14:00:00Z; certification required; no waiver; elections revocable; CASH permitted. Additive submissions allowed. No unresolved conflict in D0.
- **D1**: Event E/account A: accepted elections remain valid. Additive submission of only the authorised remaining eligible quantity is permitted. Do not resubmit already accepted quantity.

**Reference:** {"action":"submit","allowed_decisions":[{"action":"submit","quantity":40,"request_id":"SUBMIT_R"}],"decisive_ids":["D1"],"quantity":40,"request_id":"SUBMIT_R","target_accepted_quantity":100,"terms":{"cash_permitted":true,"certification_required":true,"certification_waived":false,"conflict":false,"custodian_deadline_utc":"2026-11-10T14:00:00Z","revocable":true}}

Reviewer judgment / rationale: __________

## other_event_distractor

**Account:** {"accepted_quantity":0,"account":"A","authorised_quantity":100,"certificate_present":true,"eligible_quantity":100,"event":"E","next_request_id":"SUBMIT_R","operation":"elect","option":"CASH"}

- **D0**: Initial terms for Event E/account A, CASH: custodian deadline 2026-11-10T14:00:00Z; certification required; no waiver; elections revocable; CASH permitted. Additive submissions allowed. No unresolved conflict in D0.
- **D1**: Explicit amendment for Event F, account B only: CASH is prohibited and certification is waived. This does not amend Event E or account A.

**Reference:** {"action":"submit","allowed_decisions":[{"action":"submit","quantity":100,"request_id":"SUBMIT_R"}],"decisive_ids":["D0"],"quantity":100,"request_id":"SUBMIT_R","target_accepted_quantity":100,"terms":{"cash_permitted":true,"certification_required":true,"certification_waived":false,"conflict":false,"custodian_deadline_utc":"2026-11-10T14:00:00Z","revocable":true}}

Reviewer judgment / rationale: __________

## same_event_conflict

**Account:** {"accepted_quantity":0,"account":"A","authorised_quantity":100,"certificate_present":true,"eligible_quantity":100,"event":"E","next_request_id":"SUBMIT_R","operation":"elect","option":"CASH"}

- **D0**: Initial terms for Event E/account A, CASH: custodian deadline 2026-11-10T14:00:00Z; certification required; no waiver; elections revocable; CASH permitted. Additive submissions allowed. No unresolved conflict in D0.
- **D1**: Event E: this notice replaces D0 only on CASH eligibility; CASH IS permitted. D1 and D2 are equally authoritative current notices; neither replaces the other.
- **D2**: Event E: this notice replaces D0 only on CASH eligibility; CASH IS NOT permitted. D1 and D2 are equally authoritative current notices; neither replaces the other.

**Reference:** {"action":"clarify","allowed_decisions":[{"action":"clarify","quantity":0,"request_id":null}],"decisive_ids":["D1","D2"],"quantity":0,"request_id":null,"target_accepted_quantity":0,"terms":{"cash_permitted":null,"certification_required":true,"certification_waived":false,"conflict":true,"custodian_deadline_utc":"2026-11-10T14:00:00Z","revocable":true}}

Reviewer judgment / rationale: __________
