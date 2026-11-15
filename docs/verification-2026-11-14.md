# Unified demo and cloud database verification — 2026-11-14

The redesign has one public homepage and separate `/billing` and `/integration` workspaces. Design research and actual Paper exports are in [design/research.md](design/research.md).

## Verified before traffic migration

- Billing unit/integration suite: 37 passed. Added bounded gateway routing, cross-origin mutation rejection, required custom header, request-size limit, and unconfigured-backend behavior.
- Integration suite with actual local SQL Server / Oracle: 18 passed. Added private-service token identity checks and unauthenticated cloud API rejection.
- Desktop 1440px and mobile 390px checks: no JavaScript errors, no horizontal overflow; source/records/agent navigation, insurance expansion and record selection remain functional.
- Actual GCP VM engines: SQL Server 16.0.4325.4 and Oracle AI Database 26ai Free 23.26.3.0.0.
- Public Synthea fixture: 1 Patient, 3 Encounter, 3 ExplanationOfBenefit records. Live SMART FHIR: 1 Patient, 23 Encounter, no ExplanationOfBenefit. Both independently hashed database copies matched.
- Real Vertex `gemini-3.8-flash` called both tools, produced a draft with all six bounded evidence checks passing, and did not infer a final personal balance from the EOB records.
- A review explicitly labeled `[Demo verification]` was saved; repeat review returned 409. The approved response persisted across API-container restart. This is automated demonstration verification, not independent human review.
- A direct private API request without a gateway identity returned 401. SQL Server and Oracle use separate persistent Docker volumes and expose database ports only on VM loopback.

Detailed cloud evidence is in the [integration repository](https://github.com/rockyzl/healthcare-integration-lab/blob/main/reports/cloud-verification-2026-11-14.json). The frontend gateway exposes only known operations, with shared daily budgets of 40 model requests and 200 other mutations. This remains a public synthetic-data learning lab.

## Cloud deployment

The existing Cloud Run service connects to the dedicated VM over Direct VPC egress. Environment/secret bindings for the original Identity Platform, Firestore, Vertex and UiPath integrations are preserved. The model was not changed. See [database deployment and cost notes](https://github.com/rockyzl/healthcare-integration-lab/blob/main/docs/cloud/deployment.md).

## Public-site browser validation

The canonical public URL was exercised in Chromium after migration: source import, actual Vertex draft, shared review and reload; Anna account sign-in, cross-patient access denial, real Maestro task, Action Center approval, and approved reply back in the patient role. Reviewer edits were captured in the actual review request and confirmed in the delivered reply. Desktop and 390px mobile had no script errors or horizontal overflow. See [browser report](design/live-browser-check.json).

The final check also exposed an edit-loss edge case during refresh. Unsaved reviewer text is now retained across manual/poll refreshes and cleared on logout or completion. The focused browser regression in `tests/browser/review_refresh.py` uses mocked portal responses to change the server snapshot and verifies the edited text survives repeated refresh. Run it against a running app with Playwright and optional `CHROMIUM_EXECUTABLE` / `DEMO_URL`.
