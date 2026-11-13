"""Read-only access to real, public CMS hospital/service aggregates."""

import re
from datetime import UTC, datetime
from decimal import Decimal

import httpx

DATASET_ID = "771e94a2-cd8f-4702-a9d7-8f777f363938"
DATA_YEAR = 2024
DATASET_PAGE = "https://data.cms.gov/provider-summary-by-type-of-service/medicare-outpatient-hospitals/medicare-outpatient-hospitals-by-provider-and-service"
API_URL = f"https://data.cms.gov/data-api/v1/dataset/{DATASET_ID}/data"
DICTIONARY_URL = "https://data.cms.gov/sites/default/files/2020-12/Medicare%20Outpatient%20Hospitals%20-%20by%20Provider%20and%20Service%20Data%20Dictionary.pdf"
MONEY_FIELDS = {
    "average_submitted_charge": "Avg_Tot_Sbmtd_Chrgs",
    "average_medicare_allowed": "Avg_Mdcr_Alowd_Amt",
    "average_medicare_payment": "Avg_Mdcr_Pymt_Amt",
}


def money(value):
    """A blank CMS cell stays unavailable; never turn it into zero."""
    return str(Decimal(str(value)).quantize(Decimal("0.01"))) if value else None


async def lookup_cms_costs(provider_ccn: str, apc_code: str) -> dict:
    """Fetch actual 2024 CMS hospital/APC average charges and payments. Not a personal bill, quote or coverage decision. Blank cells are unavailable."""
    if not re.fullmatch(r"\d{6}", provider_ccn) or not re.fullmatch(r"\d{4}", apc_code):
        raise ValueError("Expected a six-digit CCN and four-digit APC code")
    # CMS returned 503s for several combined CCN/APC filters. Fetch the bounded
    # provider page and select the APC locally; never substitute mock records.
    params = {"size": 100, "filter[Rndrng_Prvdr_CCN]": provider_ccn}
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.get(API_URL, params=params)
        response.raise_for_status()
    rows = response.json()
    # Fail closed if the API ignores filters or changes its schema.
    if not isinstance(rows, list) or len(rows) >= 100:
        raise ValueError("Unexpected or potentially truncated CMS response")
    if any(row.get("Rndrng_Prvdr_CCN") != provider_ccn for row in rows):
        raise ValueError("CMS returned a different provider")
    rows = [row for row in rows if row.get("APC_Cd") == apc_code]
    if len(rows) > 1:
        raise ValueError("CMS returned duplicate service rows")
    result = {
        "source_id": f"cms:{DATA_YEAR}:{provider_ccn}:{apc_code}",
        "source_url": str(response.url),
        "dataset_url": DATASET_PAGE,
        "data_year": DATA_YEAR,
        "retrieved_at": datetime.now(UTC).isoformat(),
        "provider_ccn": provider_ccn,
        "apc_code": apc_code,
        "data_kind": "Real public hospital/service aggregates; not patient-level data",
        "found": bool(rows),
    }
    if not rows:
        return result
    row = rows[0]
    if row.get("Rndrng_Prvdr_CCN") != provider_ccn or row.get("APC_Cd") != apc_code:
        raise ValueError("CMS returned a different provider or service")
    result.update(
        {
            "provider": row["Rndrng_Prvdr_Org_Name"],
            "service": row["APC_Desc"],
            "city": row["Rndrng_Prvdr_City"],
            "state": row["Rndrng_Prvdr_State_Abrvtn"],
            "beneficiaries": row.get("Bene_Cnt") or None,
            "services": row.get("CAPC_Srvcs") or None,
            **{name: money(row.get(field)) for name, field in MONEY_FIELDS.items()},
        }
    )
    return result


def get_cost_definitions() -> dict:
    """Explain the CMS amounts and the limits of using aggregate data for an individual inquiry."""
    return {
        "source_id": "cms:definitions:v1",
        "source_url": DICTIONARY_URL,
        "definitions": {
            "average_submitted_charge": "Average estimated hospital charge submitted for services covered by the APC; not what a patient owes.",
            "average_medicare_allowed": "Average regular payment received, including Medicare payment and beneficiary copayment/deductible; excludes separately reported outlier payments.",
            "average_medicare_payment": "Average regular payment directly from Medicare; excludes separately reported outlier payments.",
        },
        "project_rules": [
            "These are historical 2024 aggregates, not current quotes or patient balances.",
            "Never calculate a person's liability from the difference between two averages.",
            "Blank or absent CMS values are unavailable, not zero.",
            "Personal estimates need the actual service details, insurance benefits and provider estimate; request staff review.",
            "Drafts require human review. No email, referral, claim, refund or payment action is performed.",
        ],
    }
