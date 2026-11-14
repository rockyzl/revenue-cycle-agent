# Cloud deployment

Live: https://revenue-cycle-agent-1038659864130.us-central1.run.app

The patient portal runs on Google Cloud Run, with Vertex AI inference, a named Cloud Firestore database and Google Cloud Identity Platform email/password authentication. UiPath Maestro Flow runs separately in Automation Cloud. Personal patient/billing/insurance data is synthetic.

## Server configuration

```text
BILLING_MODE=vertex
GOOGLE_CLOUD_PROJECT=<your-project>
GOOGLE_CLOUD_LOCATION=global
GOOGLE_GENAI_USE_VERTEXAI=true
PUBLIC_DEMO=true
PORTAL_STORE=firestore
PORTAL_DATABASE=<your-named-firestore-database>
PORTAL_ORIGIN=<your-https-cloud-run-url>
MAESTRO_FOLDER_KEY=<your-folder-guid>
MAESTRO_RELEASE_KEY=<your-published-flow-release-guid>
IDENTITY_API_KEY=<Secret Manager reference>
UIPATH_CLIENT_ID=<Secret Manager reference>
UIPATH_CLIENT_SECRET=<Secret Manager reference>
```

Enable Vertex AI, Firestore and Identity Platform. Create a dedicated Cloud Run service account with Vertex AI invocation, Firestore data access and access to only the three application secrets. Configure an Identity Platform API key restricted to Identity Toolkit/Secure Token APIs. Create the three fictional accounts defined in `app/portal/fixtures.py` with the matching `rc-demo-*` subjects, then call `fixtures.seed(store, 'https://securetoken.google.com/<project>')` once using an authorized provisioning identity. Do not reseed a running database: doing so resets demo records and grants.

Production runs use the runtime service account's ADC for Vertex AI and Firestore. A visitor never supplies or sees a Google model credential or UiPath access token. The UI intentionally publishes passwords for the three synthetic accounts. These are demonstration identities, not real staff authentication.

## Maestro deployment

The `RevenueCycle` directory is an official UiPath SDK-generated solution, with its editable source in `PatientInbox/.flow-sdk/PatientInbox.flow.ts`. Set the Cloud Run base URL and review assignment for your own tenant before deploying a fork. The authoring SDK uses emit-only mode; edit the TypeScript source, compile, validate, format and refresh resources before packaging.

```bash
uip maestro flow compile .flow-sdk/PatientInbox.flow.ts -o PatientInbox.flow
uip maestro flow validate PatientInbox.flow
uip maestro flow format PatientInbox.flow
# From the repository root:
uip solution resources refresh --solution-folder RevenueCycle
uip solution pack RevenueCycle artifacts/maestro-package --version 0.3.1
uip solution publish artifacts/maestro-package/RevenueCycle_0.3.1.zip
```

Deploy to a dedicated folder through `uip solution deploy run`, then configure the resulting folder and release GUIDs in Cloud Run. Authenticate the CLI interactively as an authorized developer. Do not copy that personal CLI refresh token into the runtime.

The portal uses a separate confidential external app with `OR.Jobs.Read OR.Jobs.Write OR.Execution.Read OR.Tasks.Read OR.Tasks.Write OR.Folders.Read`, stored in Secret Manager. An Automation User assignment exists only in the demo folder. Specific OAuth scopes can grant tenant-wide resource access, so backend operations are fixed to the configured process/folder and task resolution verifies both title and creator job. This is a personal demo tenant, not a hospital tenant. For production, review the service's current folder-scoped authorization model and use minimum privileges.

The modern-folder task listing is `Tasks/UiPath.Server.Configuration.OData.GetTasksAcrossFolders`; plain `/odata/Tasks` lists classic folders and misses these tasks. The portal does not use the Maestro PIMS API, which rejected the external app in this tenant. No personal access token fallback is installed.

Maestro calls the draft and completion endpoints with a random per-inquiry credential. Only its hash is stored by the portal. It is valid for one inquiry and 24 hours and is never exposed to the browser or model. UiPath execution inputs include this credential: restrict access to job inputs and never commit full debug exports.

## Build and operate

Build the Dockerfile with Cloud Build, store the image in Artifact Registry, and deploy to Cloud Run. Preserve runtime secrets and environment when changing images. `.dockerignore` allowlists app/dependency files; `.gcloudignore` excludes credentials, local state and workflow debug exports.

Demo capacity: min instances 0, max 1, 1 CPU, 1 GiB RAM, concurrency 4, request timeout 240 seconds. Portal sessions last 30 minutes; inquiries are capped at 12/account/day and 40 total/day in Firestore. These are application controls, not a cloud budget guarantee. Cloud compute, builds, storage and model requests can incur charges.

Run `uv run pytest tests/unit tests/integration -q` before deploy. Verify login, own/proxy visibility, cross-patient denial, an actual agent draft, reviewer approval/rejection, callback result and final Maestro state. Do not interpret a deployment success or task creation as end-to-end completion.

## Known prototype limits

- Shared public identities; no hospital SSO federation, real-patient enrollment, EHR, claims, refunds or payments.
- Firestore persists portal state; the separate legacy `/cms` workbench still uses in-memory sessions.
- A UI status can remain waiting if an external workflow faults. Operations must inspect UiPath; automated reconciliation/retry and timeout escalation are future work.
- A 24-hour callback expiry fails closed; prolonged approval needs credential renewal/reconciliation before production use.
- Authentication is checked at login; the 30-minute app session does not poll Identity Platform revocation. Local account deactivation and patient grant revocation are rechecked on every protected request.
- No clinical correctness claim. Evidence/dollar checks do not prove semantic accuracy. Staff must assess the draft.
