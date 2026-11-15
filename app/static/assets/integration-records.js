// Display source-recorded fields. Labels are not generated or inferred by an LLM.
let downloadableRecords = new Map();

function conceptLabel(concept) {
  return concept?.text || concept?.coding?.map(code => code.display || code.code).filter(Boolean).join('; ') || 'Not provided';
}

function sourceLink(url) {
  try {
    const parsed = new URL(url);
    if (parsed.protocol === 'https:' && ['r4.smarthealthit.org', 'raw.githubusercontent.com'].includes(parsed.hostname)) {
      return `<a href="${esc(parsed.href)}" target="_blank" rel="noopener noreferrer">Open original source ↗</a>`;
    }
  } catch {}
  return '';
}

function codesMarkup(concepts) {
  const codes = concepts.flatMap(concept => concept?.coding || []);
  if (!codes.length) return '<span class="small">No coded value provided.</span>';
  return codes.map(code => `<div class="coded-value"><code>${esc(code.code || 'No code')}</code> ${esc(code.display || '')}<span class="small">${esc(code.system || 'Code system not provided')}</span></div>`).join('');
}

function rawRecord(record, type) {
  const key = `${type}/${record.id}`;
  downloadableRecords.set(key, record.imported_resource);
  return `<details class="source-json"><summary>View imported FHIR JSON</summary><p class="small">Source fields retained by this demo. Names, identifiers, addresses and free-text clinical narrative are omitted.</p><pre>${esc(JSON.stringify(record.imported_resource, null, 2))}</pre><button class="secondary" data-download-record="${esc(key)}">Download this record</button></details>${sourceLink(record.source_url)}`;
}

function bindDownloads() {
  document.querySelectorAll('[data-download-record]').forEach(button => button.onclick = () => {
    const record = downloadableRecords.get(button.dataset.downloadRecord);
    const url = URL.createObjectURL(new Blob([JSON.stringify(record, null, 2)], { type: 'application/fhir+json' }));
    const link = document.createElement('a');
    link.href = url;
    link.download = `${record.resourceType}-${record.id}.json`;
    link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
}

function renderVisitDetail(visit, preview) {
  document.querySelectorAll('[data-visit-id]').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.visitId === visit.id)));
  const reasons = visit.reasons.length ? visit.reasons.map(conceptLabel).join('; ') : 'Not provided in this visit record';
  const linked = preview.insurance.filter(record => record.linked_visit_ids.includes(visit.id));
  $('#visit-detail').innerHTML = `<p class="eyebrow">SOURCE VISIT RECORD</p><h4>${esc(visit.types.map(conceptLabel).join('; ') || 'Visit type not provided')}</h4>
    <dl class="record-fields"><div><dt>Recorded reason</dt><dd>${esc(reasons)}</dd></div><div><dt>Visit class / status</dt><dd>${esc(visit.class.display || visit.class.code || 'Not provided')} · ${esc(visit.status || 'Not provided')}</dd></div><div><dt>Visit start</dt><dd>${esc(visit.period.start || 'Not provided')}</dd></div><div><dt>Visit end</dt><dd>${esc(visit.period.end || 'Not provided')}</dd></div></dl>
    <h5>Service / visit codes</h5>${codesMarkup(visit.types)}${visit.reasons.length ? `<h5>Recorded reason codes</h5>${codesMarkup(visit.reasons)}` : ''}
    <p class="small">Visit ID: <code>${esc(visit.id)}</code></p><p class="small">${linked.length ? `${linked.length} insurance record(s) below reference this visit.` : 'No imported insurance record references this visit.'}</p>
    ${rawRecord(visit, 'Encounter')}`;
  bindDownloads();
}

function lineAmount(amount) {
  return amount && amount.value !== undefined ? money(amount) : 'Not provided';
}

function adjudicationMarkup(items) {
  if (!items?.length) return '<span class="small">No line-level adjudication provided.</span>';
  return items.map(item => `<div>${esc(conceptLabel(item.category))}: ${item.amount ? lineAmount(item.amount) : item.value !== undefined ? esc(item.value) : 'Not provided'}${item.reason ? ` · ${esc(conceptLabel(item.reason))}` : ''}</div>`).join('');
}

function serviceLineMarkup(item) {
  const serviceDate = item.servicedDate || item.servicedPeriod?.start;
  return `<article class="service-line"><div class="case-top"><b>Line ${esc(item.sequence ?? '—')}: ${esc(conceptLabel(item.productOrService))}</b><span class="small">${date(serviceDate)}</span></div>
    ${codesMarkup([item.productOrService])}<dl class="line-fields"><div><dt>Category</dt><dd>${esc(conceptLabel(item.category))}</dd></div><div><dt>Place of service</dt><dd>${esc(conceptLabel(item.locationCodeableConcept))}</dd></div><div><dt>Quantity</dt><dd>${item.quantity?.value !== undefined ? esc(item.quantity.value) : 'Not provided'}</dd></div><div><dt>Unit price</dt><dd>${lineAmount(item.unitPrice)}</dd></div><div><dt>Line amount</dt><dd>${lineAmount(item.net)}</dd></div></dl>
    <div class="line-adjudication"><b>Insurance processing for this line</b><br>${adjudicationMarkup(item.adjudication)}</div>
    ${(item.detail || []).map(serviceLineMarkup).join('')}${(item.subDetail || []).map(serviceLineMarkup).join('')}</article>`;
}

function renderInsurance(record, index) {
  const submitted = record.financial_facts.find(fact => fact.kind === 'EOB total' && fact.category === 'submitted');
  const payment = record.financial_facts.find(fact => fact.kind === 'EOB payment');
  return `<article class="insurance-record full-insurance"><div class="case-top"><div><span class="eyebrow">SOURCE INSURANCE RECORD ${index + 1}</span><h4>${esc(record.insurer.display || 'Insurer not provided')}</h4></div><span class="small">Created ${date(record.created)}</span></div>
    <dl class="insurance-totals"><div><dt>Submitted amount</dt><dd>${money(submitted)}</dd></div><div><dt>Recorded payment</dt><dd>${money(payment)}</dd></div></dl>
    <dl class="record-fields"><div><dt>Claim type / use</dt><dd>${esc(conceptLabel(record.type))} · ${esc(record.use || 'Not provided')}</dd></div><div><dt>Processing outcome / status</dt><dd>${esc(record.outcome || 'Not provided')} · ${esc(record.status || 'Not provided')}</dd></div><div><dt>Submitted billing period</dt><dd>${date(record.period.start)} – ${date(record.period.end)}</dd></div></dl>
    <h5>Recorded service line items (${record.items.length})</h5>${record.items.length ? record.items.map(serviceLineMarkup).join('') : '<p class="empty-records">This source does not provide service line items.</p>'}
    <p class="small">The claim total above is not allocated across lines when the source does not provide line amounts. Missing amounts are not treated as zero.</p>
    <p class="small">Insurance record ID: <code>${esc(record.id)}</code></p>${rawRecord(record, 'ExplanationOfBenefit')}</article>`;
}

function renderFullPreview(preview) {
  downloadableRecords = new Map();
  const visits = preview.visits;
  const visitContent = visits.length ? `<p class="small">Select a visit to read its service description, recorded reason and source codes.</p><div class="visit-browser"><div class="visit-list" role="group" aria-label="Select a visit">${visits.map(visit => `<button class="visit-choice" data-visit-id="${esc(visit.id)}" aria-pressed="false"><span>${date(visit.period.start)}</span><b>${esc(visit.types.map(conceptLabel).join('; ') || 'Visit type not provided')}</b><small>${esc(visit.reasons.length ? visit.reasons.map(conceptLabel).join('; ') : 'Reason not provided')}</small></button>`).join('')}</div><article id="visit-detail" class="visit-detail"></article></div>` : '<p class="empty-records">No visit records were returned for this test patient.</p>';
  const insuranceContent = preview.insurance.length ? `<div class="insurance-details">${preview.insurance.map((record, index) => `<details class="insurance-fold"><summary>${esc(record.insurer.display || 'Insurance record')} · ${date(record.created)} · ${record.items.length} service line(s)</summary>${renderInsurance(record,index)}</details>`).join('')}</div>` :
    '<div class="empty-records"><b>No insurance records returned</b><p>The import worked. This test patient has no insurance records in this snapshot, so there are no insurance amounts to display.</p><button class="secondary" id="load-example-from-results">Load the example with insurance amounts</button></div>';
  $('#record-preview').innerHTML = `<details class="patient-record"><summary>Test record identity and data provenance</summary><span>Patient ID: <code>${esc(preview.patient_id)}</code></span><span class="small">Public synthetic records. The clinical labels and billing items below come from the source data.</span></details><div class="record-view-tabs" role="group" aria-label="Record type"><button data-record-view="visits" aria-pressed="true">Visits (${visits.length})</button><button data-record-view="insurance" aria-pressed="false">Insurance (${preview.insurance.length})</button></div><section id="visits-view">${visitContent}</section><section id="insurance-view" hidden><p class="small">Explanation of Benefit (EOB). Expand a record to inspect the services and amounts supplied by the source.</p>${insuranceContent}</section>`;
  document.querySelectorAll('[data-record-view]').forEach(button => button.onclick = () => {
    const visitsVisible = button.dataset.recordView === 'visits';
    $('#visits-view').hidden = !visitsVisible; $('#insurance-view').hidden = visitsVisible;
    document.querySelectorAll('[data-record-view]').forEach(item => item.setAttribute('aria-pressed', String(item === button)));
  });
  document.querySelectorAll('[data-visit-id]').forEach(button => button.onclick = () => {
    renderVisitDetail(visits.find(visit => visit.id === button.dataset.visitId), preview);
    if (window.innerWidth <= 650) reveal($('#visit-detail'));
  });
  if (visits.length) renderVisitDetail(visits[0], preview);
  bindDownloads();
}
