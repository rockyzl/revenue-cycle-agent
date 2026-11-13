// Scaffold identity retained. Inputs are per-inquiry capabilities, not patient identifiers.
import { flow, http, hitl, input, out, types, tmpl } from '@uipath/maestro-builder-sdk';
const base = 'https://revenue-cycle-agent-1038659864130.us-central1.run.app/portal/api/worker/';
const headers = { Authorization: tmpl`Bearer ${input('workerToken')}` };
const finishUrl = tmpl`${base}${input('inquiryId')}/finish`;
export default flow('fbbb7f38-5570-4c47-897c-361bd52580fe')
  .schemaVersion('1.9')
  .name('PatientInbox')
  .input({ inquiryId: types.string, workerToken: types.string })
  .output({ status: types.string })
  .step('prepareDraft', http({ managed: true, method: 'POST', url: tmpl`${base}${input('inquiryId')}/draft`, headers, body: {}, contentType: 'application/json', timeout: 'PT4M', returns: { reply: 'string', evidence: 'string', message: 'string' } }))
  .stepSwitch('staffReview', hitl({ variant: 'quick-form', title: tmpl`RC ${input('inquiryId')}`, recipient: { channels: ['ActionCenter'], assignee: { type: 'user', value: 'zhanglu77@gmail.com' } }, fields: [
    { id: 'question', label: '患者消息（虚构演示）', type: 'string', direction: 'input', value: out('prepareDraft', 'body.message') },
    { id: 'evidence', label: '账单、保险记录与检查结果', type: 'string', direction: 'input', value: out('prepareDraft', 'body.evidence') },
    { id: 'approvedReply', label: '审核后回复', type: 'string', direction: 'inOut', value: out('prepareDraft', 'body.reply'), controlType: 'textarea', required: true },
  ], outcomes: ['Approve', 'Reject'] }), [
    { value: 'Approve', body: b => b.step('publishReply', http({ managed: true, method: 'POST', url: finishUrl, headers, contentType: 'application/json', body: { decision: 'approve', reply: out('staffReview', 'approvedReply') }, returns: { status: 'string', inquiryId: 'string' } })).return({ status: out('publishReply', 'body.status') }) },
    { value: 'Reject', body: b => b.step('closeWithoutReply', http({ managed: true, method: 'POST', url: finishUrl, headers, contentType: 'application/json', body: { decision: 'reject', reply: 'Rejected by reviewer' }, returns: { status: 'string', inquiryId: 'string' } })).return({ status: out('closeWithoutReply', 'body.status') }) },
  ])
  .build();
