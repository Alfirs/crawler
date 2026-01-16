import os
import re
from typing import Any, Dict, List, Optional

import httpx

from app.config import settings

NEUROAPI_BASE_URL = os.getenv("NEUROAPI_BASE_URL", "https://neuroapi.host/v1")


async def _post_chat(messages: List[Dict[str, str]], tools: Optional[List[Dict[str, Any]]] = None) -> Dict:
    if not settings.neuroapi_key:
        return {"status": "disabled", "reason": "NEUROAPI_API_KEY is not set"}

    headers = {
        "Authorization": f"Bearer {settings.neuroapi_key}",
        "Content-Type": "application/json",
    }
    payload: Dict[str, Any] = {
        "model": settings.neuroapi_model,
        "messages": messages,
    }
    if tools:
        payload["tools"] = tools

    async with httpx.AsyncClient() as client:
        resp = await client.post(f"{NEUROAPI_BASE_URL}/chat/completions", json=payload, headers=headers, timeout=60)
        resp.raise_for_status()
        return resp.json()


def _fallback_structured_data(documents: List[Dict[str, Any]]) -> Dict:
    items = []
    for doc in documents:
        parsed = doc.get("parsed", {})
        tables = parsed.get("tables") or []
        for row in tables:
            if len(row) < 2:
                continue
            name = row[1] if isinstance(row[1], str) else str(row[1])
            quantity_raw = row[2] if len(row) > 2 else ""
            unit = row[3] if len(row) > 3 else ""
            try:
                quantity = float(str(quantity_raw).replace(",", "."))
            except ValueError:
                continue
            items.append(
                {
                    "name": name.strip(),
                    "quantity": quantity,
                    "unit": str(unit).strip(),
                    "source_link": doc.get("link"),
                }
            )
        if not tables:
            text = parsed.get("text", "")
            for line in text.splitlines():
                match = re.match(r"(?P<name>.+?)\s+(?P<qty>\d+(\.\d+)?)\s*(?P<unit>[A-Za-zА-Яа-я/%]+)?", line)
                if match:
                    items.append(
                        {
                            "name": match.group("name").strip(),
                            "quantity": float(match.group("qty")),
                            "unit": (match.group("unit") or "").strip(),
                            "source_link": doc.get("link"),
                        }
                    )
    return {"status": "fallback", "items": items}


async def extract_structured_data(
    project_id: str,
    documents: List[Dict[str, Any]],
    tags: Dict[str, Any],
    notes: Optional[str],
) -> Dict:
    """
    LLM prompt to extract materials/equipment and volumes from parsed docs.
    """
    prompt = (
        "You are extracting structured bill-of-material data from parsed project documents. "
        "Return JSON with items: name, quantity, unit, source_link, source_excerpt."
    )
    content = {
        "project_id": project_id,
        "tags": tags,
        "notes": notes,
        "documents": documents,
    }
    if not settings.neuroapi_key:
        return _fallback_structured_data(documents)
    return await _post_chat(
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": str(content)},
        ]
    )


def _fallback_validate_estimate(file_link: str) -> Dict:
    from app.services import estimate_pipeline_utils  # lazy import to avoid cycle

    issues = estimate_pipeline_utils.scan_estimate_issues(file_link)
    return {"status": "fallback", "issues": issues}


async def validate_estimate(project_id: str, file_link: str) -> Dict:
    prompt = (
        "Validate an Excel estimate. "
        "Report rows with empty name, missing quantity, or invalid unit. "
        "Respond with JSON {issues:[{row,problem}]}."
    )
    if not settings.neuroapi_key:
        return _fallback_validate_estimate(file_link)
    return await _post_chat(
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"project_id={project_id}, file_link={file_link}"},
        ]
    )


def _fallback_normalize_list(file_link: str) -> Dict:
    from app.services import estimate_pipeline_utils

    items = estimate_pipeline_utils.generate_procurement_list(file_link)
    return {"status": "fallback", "items": items}


async def normalize_procurement_list(project_id: str, file_link: str) -> Dict:
    prompt = (
        "From the estimate, keep only materials/equipment, drop labor/coefficients/overhead. "
        "Normalize naming so synonyms merge. "
        "Return JSON with items: material, characteristics, quantity, unit, note."
    )
    if not settings.neuroapi_key:
        return _fallback_normalize_list(file_link)
    return await _post_chat(
        messages=[
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"project_id={project_id}, file_link={file_link}"},
        ]
    )
