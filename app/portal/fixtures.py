"""Entirely fictional patients, bills, insurance/payment events, and messages.

These records are independent of CMS public aggregate data. No actual patient
identity, insurance policy or hospital transaction is represented.
"""
import hashlib

DEMO_ACCOUNTS = [
    {'id': 'anna', 'name': 'Anna Lin (Demo patient A)', 'email': 'anna@patient.demo.example', 'password': 'Anna-Demo-2026!', 'uid': 'rc-demo-anna', 'role': 'patient'},
    {'id': 'ben', 'name': 'Ben Chen (Demo patient B)', 'email': 'ben@patient.demo.example', 'password': 'Ben-Demo-2026!', 'uid': 'rc-demo-ben', 'role': 'patient'},
    {'id': 'reviewer', 'name': 'Financial reviewer (Demo)', 'email': 'reviewer@patient.demo.example', 'password': 'Review-Demo-2026!', 'uid': 'rc-demo-reviewer', 'role': 'reviewer'},
]


def identity_key(issuer, subject):
    return hashlib.sha256(f'{issuer}\0{subject}'.encode()).hexdigest()


def grant_key(account_id, patient_id):
    return hashlib.sha256(f'{account_id}\0{patient_id}'.encode()).hexdigest()


BILLS = [
    {'id': 'BILL-A100', 'patient_id': 'patient-anna', 'patient_name': 'Anna Lin', 'service': 'Outpatient imaging', 'service_date': '2026-10-20', 'charge': '1200.00', 'adjustment': '200.00', 'allowed': '1000.00', 'insurance_paid': '700.00', 'deductible': '200.00', 'coinsurance': '100.00', 'patient_responsibility': '300.00', 'patient_paid': '0.00', 'balance': '300.00', 'statement_date': '2026-11-05', 'insurance_status': 'Processed', 'payment_status': 'No patient payment recorded', 'sample_question': 'My insurance already paid. Why do I still owe $300 for this test?', 'lines': [{'id': 'A100-L1', 'description': 'Outpatient imaging', 'amount': '1200.00'}], 'events': [{'date': '2026-10-28', 'type': 'insurance_adjudication', 'note': 'Allowed amount $1000.00; insurance paid $700.00; deductible $200.00; coinsurance $100.00.'}, {'date': '2026-11-05', 'type': 'statement', 'note': 'Statement issued with a patient balance of $300.00.'}]},
    {'id': 'BILL-A101', 'patient_id': 'patient-anna', 'patient_name': 'Anna Lin', 'service': 'Follow-up visit', 'service_date': '2026-10-25', 'charge': '250.00', 'adjustment': '50.00', 'allowed': '200.00', 'insurance_paid': '150.00', 'deductible': '0.00', 'coinsurance': '50.00', 'patient_responsibility': '50.00', 'patient_paid': '50.00', 'balance': '0.00', 'statement_date': '2026-11-05', 'insurance_status': 'Processed', 'payment_status': 'Payment of $50.00 posted on 2026-11-07', 'sample_question': 'I already paid $50 last week. Why did I receive this statement? Do I need to pay again?', 'lines': [{'id': 'A101-L1', 'description': 'Follow-up visit', 'amount': '250.00'}], 'events': [{'date': '2026-11-01', 'type': 'insurance_adjudication', 'note': 'Insurance paid $150.00; patient responsibility $50.00.'}, {'date': '2026-11-05', 'type': 'statement', 'note': 'Statement issued with a balance of $50.00.'}, {'date': '2026-11-07', 'type': 'patient_payment', 'note': 'Payment of $50.00 posted; current balance $0.00.'}]},
    {'id': 'BILL-B200', 'patient_id': 'patient-ben', 'patient_name': 'Ben Chen', 'service': 'Possible duplicate lab charge', 'service_date': '2026-11-02', 'charge': '800.00', 'adjustment': '200.00', 'allowed': '600.00', 'insurance_paid': '360.00', 'deductible': '0.00', 'coinsurance': '240.00', 'patient_responsibility': '240.00', 'patient_paid': '0.00', 'balance': '240.00', 'statement_date': '2026-11-10', 'insurance_status': 'Processed; charge details need staff review', 'payment_status': 'No patient payment recorded', 'sample_question': 'I visited once on November 2. Why is the same lab test listed twice? Was I charged twice?', 'lines': [{'id': 'B200-L1', 'description': 'Lab test LAB-17', 'amount': '400.00'}, {'id': 'B200-L2', 'description': 'Lab test LAB-17', 'amount': '400.00'}], 'events': [{'date': '2026-11-08', 'type': 'insurance_adjudication', 'note': 'Insurance paid $360.00; patient responsibility $240.00.'}, {'date': '2026-11-10', 'type': 'statement', 'note': 'Two charges share the same description. Complete order and performed-service records are missing, so duplicate billing cannot be confirmed.'}]},
    {'id': 'BILL-C300', 'patient_id': 'patient-child', 'patient_name': 'Alex Lin (Demo family member)', 'service': 'Pediatric follow-up', 'service_date': '2026-11-01', 'charge': '180.00', 'adjustment': '60.00', 'allowed': '120.00', 'insurance_paid': '100.00', 'deductible': '0.00', 'coinsurance': '20.00', 'patient_responsibility': '20.00', 'patient_paid': '0.00', 'balance': '20.00', 'statement_date': '2026-11-08', 'insurance_status': 'Processed', 'payment_status': 'No patient payment recorded', 'sample_question': 'What is the $20 balance on the bill for my child after the follow-up visit?', 'lines': [{'id': 'C300-L1', 'description': 'Pediatric follow-up', 'amount': '180.00'}], 'events': [{'date': '2026-11-05', 'type': 'insurance_adjudication', 'note': 'Insurance paid $100.00; patient responsibility $20.00.'}]},
]


def seed(store, issuer):
    """Run explicitly during provisioning; never reset grants on app startup."""
    for a in DEMO_ACCOUNTS:
        store.put('accounts', a['id'], {k: a[k] for k in ('id', 'name', 'role')} | {'active': True})
        store.put('identity_links', identity_key(issuer, a['uid']), {'issuer': issuer, 'subject': a['uid'], 'account_id': a['id']})
    for bill in BILLS:
        store.put('patients', bill['patient_id'], {'id': bill['patient_id'], 'name': bill['patient_name'], 'synthetic': True})
        store.put('bills', bill['id'], bill | {'synthetic': True, 'source_id': 'demo-bill:' + bill['id']})
    for account, patient, relation in [('anna', 'patient-anna', 'self'), ('anna', 'patient-child', 'authorized_proxy'), ('ben', 'patient-ben', 'self')]:
        store.put('access_grants', grant_key(account, patient), {'account_id': account, 'patient_id': patient, 'relationship': relation, 'active': True, 'expires_at': 4102444800})
