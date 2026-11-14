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


Final browser smoke: v5 revision `revenue-cycle-agent-00006-zgm` served the updated page; role switching loaded Anna's three authorized bills, cross-patient lookup returned the expected denial, and the previously approved reply survived redeployment. The session was logged out after verification. GitHub CI passed on implementation commit `245a4a7c8a46230140f793b1c732543416a69b28`: https://github.com/rockyzl/revenue-cycle-agent/actions/runs/43522867177.

## English interface release — November 13 evening (November 14 UTC)

The portal, sample questions, new model drafts and Action Center form labels now use English. Existing messages and approved responses retain their original wording. The public page no longer includes the interview notes or the UiPath administrative console link. These removals do not change authentication, permissions or review requirements.

RevenueCycle 0.3.1 successfully upgraded the existing Maestro deployment, preserving its folder and release key. On Cloud Run revision `revenue-cycle-agent-00007-nss`, a new English A101 inquiry (`ef08f729a3c14c5a8ab2972ce4536e34`) called both authorized tools and passed the reference/amount checks. The draft correctly distinguished the November 5 statement from the November 7 payment and the current $0 balance. Browser automation prefixed the reply with `[Demo verification]` and approved Action Center task `100322451`. Maestro job `f907d354-333a-4be2-9e97-922d692e8015` completed, including staffReview, publishReply and end. Anna then received the edited English reply. This was an automated engineering check, not Lu's independent human review.

The pre-existing user inquiry `1a83af99e4cc49b6a484507be30ab460` remained awaiting review. No existing inquiry, permission or session was reseeded. Only known fixture text and account display names were translated in Firestore.

Desktop 1440 px and mobile 390 px screenshots were inspected; mobile document width remained 390 px. No UiPath administrative links or interview-note panel were present. A cached copy of the old JavaScript was discovered during browser verification; the HTML now requests a versioned script URL so returning visitors load the English interface. The existing unit/integration suite passed again: **35 tests**. CI passed for the English implementation: https://github.com/rockyzl/revenue-cycle-agent/actions/runs/43561825478.

The cache fix is deployed in revision `revenue-cycle-agent-00008-hc7` (image `20261114-en2`, implementation commit `1d65d6b`). Cloud Build and GitHub CI succeeded. This revision changes only the script URL from the English runtime check above.
