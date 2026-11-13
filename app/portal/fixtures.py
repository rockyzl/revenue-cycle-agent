"""Entirely fictional patients, bills, insurance/payment events, and messages.

These records are independent of CMS public aggregate data. No actual patient
identity, insurance policy or hospital transaction is represented.
"""
import hashlib

DEMO_ACCOUNTS = [
    {'id': 'anna', 'name': 'Anna Lin（演示患者 A）', 'email': 'anna@patient.demo.example', 'password': 'Anna-Demo-2026!', 'uid': 'rc-demo-anna', 'role': 'patient'},
    {'id': 'ben', 'name': 'Ben Chen（演示患者 B）', 'email': 'ben@patient.demo.example', 'password': 'Ben-Demo-2026!', 'uid': 'rc-demo-ben', 'role': 'patient'},
    {'id': 'reviewer', 'name': '财务审核员（演示）', 'email': 'reviewer@patient.demo.example', 'password': 'Review-Demo-2026!', 'uid': 'rc-demo-reviewer', 'role': 'reviewer'},
]


def identity_key(issuer, subject):
    return hashlib.sha256(f'{issuer}\0{subject}'.encode()).hexdigest()


def grant_key(account_id, patient_id):
    return hashlib.sha256(f'{account_id}\0{patient_id}'.encode()).hexdigest()


BILLS = [
    {'id': 'BILL-A100', 'patient_id': 'patient-anna', 'patient_name': 'Anna Lin', 'service': '门诊影像检查', 'service_date': '2026-10-20', 'charge': '1200.00', 'adjustment': '200.00', 'allowed': '1000.00', 'insurance_paid': '700.00', 'deductible': '200.00', 'coinsurance': '100.00', 'patient_responsibility': '300.00', 'patient_paid': '0.00', 'balance': '300.00', 'statement_date': '2026-11-05', 'insurance_status': '已处理', 'payment_status': '尚无患者付款记录', 'sample_question': '保险不是已经付钱了吗？为什么这次检查还要我再付 300 美元？', 'lines': [{'id': 'A100-L1', 'description': '门诊影像检查', 'amount': '1200.00'}], 'events': [{'date': '2026-10-28', 'type': 'insurance_adjudication', 'note': '允许金额 1000；保险支付 700；自付额 200；共同保险 100。'}, {'date': '2026-11-05', 'type': 'statement', 'note': '生成患者余额 300 的账单。'}]},
    {'id': 'BILL-A101', 'patient_id': 'patient-anna', 'patient_name': 'Anna Lin', 'service': '门诊复诊', 'service_date': '2026-10-25', 'charge': '250.00', 'adjustment': '50.00', 'allowed': '200.00', 'insurance_paid': '150.00', 'deductible': '0.00', 'coinsurance': '50.00', 'patient_responsibility': '50.00', 'patient_paid': '50.00', 'balance': '0.00', 'statement_date': '2026-11-05', 'insurance_status': '已处理', 'payment_status': '2026-11-07 付款 50 已入账', 'sample_question': '我上周已经付了 50 美元，今天怎么又收到这张账单？还要再付一次吗？', 'lines': [{'id': 'A101-L1', 'description': '门诊复诊', 'amount': '250.00'}], 'events': [{'date': '2026-11-01', 'type': 'insurance_adjudication', 'note': '保险支付 150，患者责任 50。'}, {'date': '2026-11-05', 'type': 'statement', 'note': '生成余额 50 的账单。'}, {'date': '2026-11-07', 'type': 'patient_payment', 'note': '付款 50 已入账，当前余额 0。'}]},
    {'id': 'BILL-B200', 'patient_id': 'patient-ben', 'patient_name': 'Ben Chen', 'service': '两条待核实的检查收费', 'service_date': '2026-11-02', 'charge': '800.00', 'adjustment': '200.00', 'allowed': '600.00', 'insurance_paid': '360.00', 'deductible': '0.00', 'coinsurance': '240.00', 'patient_responsibility': '240.00', 'patient_paid': '0.00', 'balance': '240.00', 'statement_date': '2026-11-10', 'insurance_status': '已处理；收费明细待人工核实', 'payment_status': '尚无患者付款记录', 'sample_question': '我 11 月 2 日只去了一次医院，为什么同一个检查在账单里出现了两行？是不是收了两次钱？', 'lines': [{'id': 'B200-L1', 'description': '检查项目 LAB-17', 'amount': '400.00'}, {'id': 'B200-L2', 'description': '检查项目 LAB-17', 'amount': '400.00'}], 'events': [{'date': '2026-11-08', 'type': 'insurance_adjudication', 'note': '保险支付 360，患者责任 240。'}, {'date': '2026-11-10', 'type': 'statement', 'note': '存在两条描述相同的收费；缺少完整医嘱/执行记录，不能据此确认重复收费。'}]},
    {'id': 'BILL-C300', 'patient_id': 'patient-child', 'patient_name': 'Alex Lin（演示家属）', 'service': '儿科复诊', 'service_date': '2026-11-01', 'charge': '180.00', 'adjustment': '60.00', 'allowed': '120.00', 'insurance_paid': '100.00', 'deductible': '0.00', 'coinsurance': '20.00', 'patient_responsibility': '20.00', 'patient_paid': '0.00', 'balance': '20.00', 'statement_date': '2026-11-08', 'insurance_status': '已处理', 'payment_status': '尚无患者付款记录', 'sample_question': '这是我孩子的复诊账单，这 20 美元是什么费用？', 'lines': [{'id': 'C300-L1', 'description': '儿科复诊', 'amount': '180.00'}], 'events': [{'date': '2026-11-05', 'type': 'insurance_adjudication', 'note': '保险支付 100；患者责任 20。'}]},
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
