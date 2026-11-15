# Revenue Cycle Lab design research — 2026-11-14

The user selected one public entrance with two working demo pages. All product copy is English. The goal is understandable task flow with inspectable source records, not a long technical summary.

## Official references reviewed

- [NHS typography](https://service-manual.nhs.uk/design-system/styles/typography): clear hierarchy and legible service content. We use open fonts, not NHS branding or licensed Frutiger.
- [IBM Carbon data tables](https://www.carbondesignsystem.com/building-blocks/core/components/data-table/guidelines): consistent records and progressive disclosure. The implementation uses a selected visit and a detail pane, with insurance records expanded individually.
- [Linear UI redesign](https://linear.app/now/how-we-redesigned-the-linear-ui): calm navigation and distinct workspace hierarchy. Applied to shared navigation and action placement.

## Paper design

[Editable Paper file](https://app.paper.design/file/01M7EQ8SVTVEHQZSKH9TTX8PH2/p-1-0)

Three desktop artboards: Overview, Patient billing, Data integration. Created through the official Paper MCP, inspected by screenshots, then exported using get_jsx and get_computed_styles. The JSX snapshots and computed styles in this directory document the design, not a second runtime frontend.

Direction: wayfinding. White #FFFFFF, navy #172337, action blue #2458D3, section gray #F3F5F8, lines #DDE3EC, review amber #9A6500. IBM Plex Sans headings, Source Sans 3 body, IBM Plex Mono codes and amounts. Header 80px, desktop page gutters 48px (overview 72px), 24px column gaps. Responsive layout collapses to one column; controls remain keyboard accessible.

Overview offers two concrete example questions. Billing preserves real identity checks, LangGraph/Vertex draft generation, and UiPath Maestro/Action Center review. Integration separates source selection, record inspection, and agent review. It shows actual retained FHIR fields; no missing amount is fabricated. Database comparison remains distinct from billing accuracy.

## Runtime adaptation

The HTML/JS implementation retains existing API hooks and adds semantics, responsive styles, live status, and error states absent from static artboards. History is expandable. Imported visits have a selected list/detail view; EOB records and raw JSON expand on demand. Real database state supplies all badges and counts.
