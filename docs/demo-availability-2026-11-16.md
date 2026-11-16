# One-week integration demo window

The owner requested that the real SQL Server / Oracle demo remain available for one week, then show a clear temporary-closure notice. The window ends at `2026-11-23T17:46:37Z` (11:46 AM America/Chicago).

`INTEGRATION_CLOSES_AT` controls the gateway. After expiry, both read and write operations return a structured 503 before acquiring a cloud token, reserving a model budget, or contacting the database VM. `/integration/api/availability` stays readable with `Cache-Control: no-store`. Invalid or timezone-less configuration fails closed. The UI checks availability on load and every minute while open; after closure it hides the live controls and offers the project walkthrough and billing demo links.

Compute Engine independently has a seven-day maximum runtime with termination action STOP, beginning at its 2026-11-16 17:46:37 UTC start. No separate always-running scheduler is required. The VM disk remains retained and billed unless the owner separately authorizes its removal. Reopening later requires both a deliberate VM start and an updated gateway deadline; starting the VM alone does not bypass the closed gateway.

Validation:

- 41 unit/integration tests passed, including closure enforcement before credentials/budget calls, allowed routing, no-cache availability and invalid-deadline handling.
- Browser checks with controlled local responses covered open state, transition to closed, a fresh closed-page load, hidden database controls, visible project link, mobile width and no script errors.
- Local UI checks simulate future closure; the actual seven-day cloud expiration has not elapsed.
- Cloud Build `5953d91a-ef87-406c-8553-6967d2bf452c` produced image digest `sha256:2755c254f568edce56559e96d4ee555980fa66394b2effa9b823425f63bb3288`.
- The service had traffic pinned to the prior revision. Deployment requires explicitly routing traffic to `revenue-cycle-agent-00013-z85`; updating the image alone did not change the public endpoint.
- After routing 100% of traffic to revision `revenue-cycle-agent-00013-z85`, the public availability endpoint returned the intended cutoff, both SQL Server and Oracle reported connected, the two existing test patients remained present, and the actual browser showed the open-window banner without script errors. These checks did not call a model or write a new record.

The underlying integration dataset was backed up privately to the owner's Drive, including every application row and review record, a native SQL Server backup, source, restore utility and checksums. Restoration into isolated SQL/Oracle namespaces and unchanged-source checks passed. No backup data, passwords, API keys or private Drive links belong in this public repository.
