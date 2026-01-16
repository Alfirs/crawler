import asyncio
from typing import Dict, List

from app.config import settings
from app.services import google_sheets, project_store
from app.services.estimate_pipeline_utils import normalize_name


def _boolean(value: str) -> bool:
    return str(value or "").strip().lower() in {"yes", "да", "true", "1"}


async def load_suppliers() -> List[Dict]:
    sheet_id = settings.google_sheets_id
    if not sheet_id:
        return []
    rows = await google_sheets.fetch_rows(sheet_id, settings.suppliers_sheet_range)
    suppliers: List[Dict] = []
    for row in rows:
        if not row or not row[0]:
            continue
        suppliers.append(
            {
                "name": str(row[0]).strip(),
                "has_api": _boolean(row[1] if len(row) > 1 else ""),
                "api_url": str(row[2]) if len(row) > 2 else "",
                "email": str(row[3]) if len(row) > 3 else "",
                "contact": str(row[4]) if len(row) > 4 else "",
            }
        )
    return suppliers


def _quote_price(material_name: str, supplier_name: str) -> float:
    normalized = normalize_name(material_name)
    base = abs(hash((normalized, supplier_name))) % 5000
    return round((base / 100) + 50, 2)


async def _simulate_api_request(project_id: str, supplier: Dict, materials: List[Dict]) -> Dict:
    await asyncio.sleep(0)
    items = []
    for item in materials:
        name = item.get("material") or item.get("name")
        if not name:
            continue
        price = _quote_price(name, supplier["name"])
        quantity = item.get("quantity") or 0
        items.append(
            {
                "material": name,
                "unit_price": price,
                "quantity": quantity,
                "lead_time_days": 5,
            }
        )
    response = {
        "supplier": supplier["name"],
        "channel": "api",
        "status": "responded",
        "items": items,
    }
    project_store.append_supplier_response(project_id, response)
    return response


async def _simulate_email_request(project_id: str, supplier: Dict, materials: List[Dict]) -> Dict:
    await asyncio.sleep(0)
    items = []
    for item in materials:
        name = item.get("material") or item.get("name")
        if not name:
            continue
        price = _quote_price(name, supplier["name"]) * 1.05
        quantity = item.get("quantity") or 0
        items.append(
            {
                "material": name,
                "unit_price": round(price, 2),
                "quantity": quantity,
                "lead_time_days": 7,
            }
        )
    response = {
        "supplier": supplier["name"],
        "channel": "email",
        "status": "responded",
        "items": items,
    }
    project_store.append_supplier_response(project_id, response)
    return response


async def dispatch_requests(project_id: str, materials: List[Dict], max_api_suppliers: int = 3) -> Dict:
    suppliers = await load_suppliers()
    if not suppliers:
        return {"status": "no_suppliers"}

    responses: List[Dict] = []
    api_count = 0
    for supplier in suppliers:
        if supplier["has_api"] and api_count < max_api_suppliers:
            resp = await _simulate_api_request(project_id, supplier, materials)
            api_count += 1
        else:
            resp = await _simulate_email_request(project_id, supplier, materials)
        responses.append(resp)
    return {"status": "completed", "responses": responses}
