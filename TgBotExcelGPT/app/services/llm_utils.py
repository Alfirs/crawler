import json
from typing import Dict, List


def extract_list(response: Dict, key: str) -> List[Dict]:
    """
    Extracts a list from LLM responses regardless of whether it is embedded directly
    or inside message content as JSON.
    """
    value = response.get(key)
    if isinstance(value, list):
        return value

    choices = response.get("choices")
    if not choices:
        return []

    content = choices[0].get("message", {}).get("content", "")
    try:
        parsed = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return []

    if isinstance(parsed, dict) and isinstance(parsed.get(key), list):
        return parsed[key]
    if isinstance(parsed, list):
        return parsed
    return []
