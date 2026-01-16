from typing import Dict, List

from app.services import project_store, reports
from app.services.estimate_pipeline_utils import normalize_name


def build_summary(project_id: str) -> Dict:
    procurement = project_store.load_items(project_id, "procurement")
    if not procurement:
        return {"status": "no_procurement", "rows": []}

    responses = project_store.load_supplier_responses(project_id)
    if not responses:
        return {"status": "pending", "rows": []}

    materials: Dict[str, Dict] = {}
    for item in procurement:
        name = item.get("material") or item.get("name")
        if not name:
            continue
        key = normalize_name(name)
        materials[key] = {
            "material": name,
            "quantity": item.get("quantity") or 0,
            "unit": item.get("unit"),
            "quotes": [],
        }

    for response in responses:
        supplier = response.get("supplier")
        channel = response.get("channel")
        status = response.get("status", "responded")
        for quote in response.get("items", []):
            qname = quote.get("material")
            key = normalize_name(qname or "")
            entry = materials.get(key)
            if not entry:
                continue
            unit_price = float(quote.get("unit_price") or 0)
            lead_time = quote.get("lead_time_days")
            entry["quotes"].append(
                {
                    "supplier": supplier,
                    "channel": channel,
                    "status": status,
                    "unit_price": unit_price,
                    "lead_time_days": lead_time,
                }
            )

    rows: List[Dict] = []
    for entry in materials.values():
        quotes = entry["quotes"]
        if not quotes:
            rows.append(
                {
                    "material": entry["material"],
                    "quantity": entry["quantity"],
                    "unit": entry["unit"],
                    "supplier": None,
                    "unit_price": None,
                    "total": None,
                    "lead_time_days": None,
                    "channel": None,
                    "status": "no_response",
                    "best": False,
                }
            )
            continue
        best_quote = min(quotes, key=lambda q: q["unit_price"])
        for quote in quotes:
            total = None
            if quote["unit_price"] is not None and entry["quantity"]:
                total = round(quote["unit_price"] * float(entry["quantity"]), 2)
            rows.append(
                {
                    "material": entry["material"],
                    "quantity": entry["quantity"],
                    "unit": entry["unit"],
                    "supplier": quote["supplier"],
                    "unit_price": quote["unit_price"],
                    "total": total,
                    "lead_time_days": quote.get("lead_time_days"),
                    "channel": quote.get("channel"),
                    "status": quote.get("status"),
                    "best": quote is best_quote,
                }
            )

    artifact = reports.save_supplier_summary(project_id, rows) if rows else None
    return {"status": "ready" if rows else "pending", "rows": rows, "artifact": artifact}
