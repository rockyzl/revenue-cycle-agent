# Upstream provenance and changes

This is an independently adapted prototype, not a from-scratch platform.

| Upstream | Pinned commit | Reused material | License |
|---|---|---|---|
| https://github.com/google/agents-cli | 6eedbdc2f44c388cbfc5f305eb83b9924cfefebb | LangChain project scaffold, Gemini create_agent pattern, FastAPI/A2A serving, telemetry, Dockerfile and development scripts | Apache-2.0 |
| https://github.com/UiPath/uipath-langchain-python | 3fd7a6a1ee6f170c341ce22f9f7ca6b04f0d924f | Ticket classification StateGraph, structured triage, CreateTask interruption and local suspend/resume pattern | MIT |

Original reference files and full licenses are in references/upstream. Source copyright headers are retained. User-specific additions are synthetic billing tools/cases, domain schema, bounded human review, replay checks, a small demo interface, and platform verification artifacts. See README for what was actually run. No UiPath, GCP or healthcare production experience is implied by merely generating these files.

## Real-data workbench added 2026-11-13

Added live CMS retrieval, a separate cost-inquiry agent/graph, deterministic amount
and citation checks, specialist routing, a workflow UI with tool traces, editable
human review, and six real-model evaluation cases. The earlier fabricated billing
records remain separate legacy fixtures and are not the main demo's data source.

Data: [CMS Medicare Outpatient Hospitals by Provider and Service](https://data.cms.gov/provider-summary-by-type-of-service/medicare-outpatient-hospitals/medicare-outpatient-hospitals-by-provider-and-service),
data year 2024, dataset UUID `771e94a2-cd8f-4702-a9d7-8f777f363938`.
Definitions are paraphrased from the [official CMS data dictionary](https://data.cms.gov/sites/default/files/2020-12/Medicare%20Outpatient%20Hospitals%20-%20by%20Provider%20and%20Service%20Data%20Dictionary.pdf).
Each tool result records the actual source URL, provider/APC, year and retrieval time.
The demo provider is Mayo Clinic Hospital Rochester (CCN 240010); no affiliation
or endorsement is implied. Example inquiry text is authored, not actual patient correspondence.
