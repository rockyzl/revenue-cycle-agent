# Runtime verification — 2026-11-13

This record documents bounded engineering checks, not a patient study or independent human review. /root used automation to operate the public synthetic patient and reviewer accounts.

## Current portal

- Unit/integration tests: **35 passed**, one upstream Starlette/AnyIO deprecation warning. Covers account/issuer mapping, patient and proxy grants, denied cross-patient reads, revoked grants between tools, CSRF/role checks, idempotent intake, scoped callbacks, wrong-job task exclusion and withholding replies until Maestro completion.
- Real Google Cloud Identity Platform login and Firestore reads verified for Anna, Ben and the financial reviewer. Anna sees A100/A101 plus authorized C300, not Ben's B200. No model call occurs for an unauthorized bill request.
- Actual Vertex AI tool-call draft verified; two tools return the authorized synthetic bill and insurance/payment events. Tool/source and dollar checks passed for the inspected cases.
- Official SDK-authored Maestro Flow compiled/validated/formatted, packaged as RevenueCycle 0.3.0 and deployed to the dedicated RevenueCycleDemo folder.

| Run | Actual job/instance | Result |
|---|---|---|
| SDK runtime debug, balance explanation | `124db4ee-8ae6-4e50-a996-3c2afb8e3267` | Completed; real Quick Form task, API verification decision, completion callback |
| Deployed approval, already-paid statement A101 | `fe382bfc-21b8-40c7-8db4-7621f12b4cde` | Completed; reviewer browser edited draft and approved task 100320326; Anna then saw the edited reply, balance $0 |
| Deployed rejection, possible duplicate B200 | `d09bfff4-3291-409c-ad6a-6c2bbf72594e` | Completed; reviewer browser rejected draft; Ben saw rejected status with no published reply |

For the approval run, every selected node including staffReview, publishReply and end completed. For rejection, staffReview, closeWithoutReply and end2 completed. Verification replies are explicitly labeled in Chinese as demo/test records. These clicks were executed by the coding assistant through browser automation; they are not Lu's substantive approval of clinical or financial content.

The rejection example exposed a useful limitation: the generated draft said it had already referred the case to a specialist, while no specialist assignment integration exists. That draft was rejected. Numeric/citation checks cannot detect every unsupported operational claim; review is still necessary. This project does not report perfect answer accuracy.

Desktop 1440 px and mobile 390 px screens inspected. No horizontal overflow at 390 px. Both patient ownership denial and role switch were checked. A rapid switch initially exposed the send button before the new account's bill list loaded; v5 hides that work area until the authorized list is ready and clears previous selection on logout. The backend had rejected the premature invalid request.

Approval/rejection ran on Cloud Run revision revenue-cycle-agent-00005-bb4 (image 20261113-v4). The v5 image changes client loading behavior, the rejection timeline and the console link, preserving the verified backend and Maestro package. See deployment notes for prototype limits.

## Separate earlier CMS evidence

The six public CMS/Vertex cases and legacy coded-agent Action Center smoke run remain in artifacts/eval-cms-live.json and artifacts/uipath-cloud-verification.json. They do not substitute for the new patient-inbox verification. CMS averages remain separate from synthetic personal records.

Full debug exports and credentials are excluded from version control. This public record omits worker credentials, OAuth tokens and private cloud authentication material.
