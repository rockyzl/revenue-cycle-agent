# Cloud deployment

The demo runs a FastAPI container on Google Cloud Run in `us-central1`, with
Vertex AI credentials supplied by a dedicated runtime service account. Public
requests select one of six authored cases; they cannot supply arbitrary prompts.
Actual CMS retrieval and model invocation occur on each run.

Runtime settings:

```text
BILLING_MODE=vertex
GOOGLE_CLOUD_PROJECT=your-project-id
GOOGLE_CLOUD_LOCATION=global
GOOGLE_GENAI_USE_VERTEXAI=True
PUBLIC_DEMO=true
BILLING_ENABLE_TELEMETRY=false
GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY=false
```

Settings for this bounded demonstration: minimum instances 0, maximum instances 1,
1 CPU, 1 GiB memory, concurrency 4, timeout 240 seconds. The runtime service
account needs Vertex AI invocation permission; it has no billing-system access.
The app limits concurrent model calls to two. Rate/session limits are per process,
not a durable spending limit. Builds, image storage, compute and model calls
can incur charges. In-memory reviews reset on restart.

Build the supplied Dockerfile using Cloud Build, store the image in Artifact
Registry, then deploy with these environment settings. Never copy a local `.env`
or token into the container. `.dockerignore` permits only build and app files.
`.gcloudignore` excludes credentials, state, artifacts and development files.

Validate the deployed health endpoint, a real inquiry, tool/source/amount checks,
and review resumption. UIPath cloud configuration is a separate integration:
it requires the organization, tenant, folder, deployment and a compatible review
app. The public UI states its actual integration status.
