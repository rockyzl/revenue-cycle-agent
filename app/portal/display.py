"""English display translations of the original fictional demo history.

Exact matches preserve original database/audit records and do not translate or
rewrite newly submitted content. Rejected drafts remain rejected, including
their original unsupported claims; translation is not a new approval.
"""
import json
from pathlib import Path

_HISTORY = json.loads(Path(__file__).with_name('history_en.json').read_text())


def english_history(value):
    if isinstance(value, str):
        return _HISTORY.get(value, value)
    if isinstance(value, dict):
        return {key: english_history(item) for key, item in value.items()}
    if isinstance(value, list):
        return [english_history(item) for item in value]
    return value
