from typing import Dict, List

from app.services import project_store, reports


def _normalize_name(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum() or ch.isspace()).strip()


def _aggregate(items: List[Dict]) -> Dict[str, Dict]:
    agg: Dict[str, Dict] = {}
    for item in items:
        name = str(item.get("name") or item.get("material") or "")
        if not name:
            continue
        key = _normalize_name(name)
        quantity = item.get("quantity")
        try:
            qty_val = float(quantity)
        except (TypeError, ValueError):
            qty_val = 0.0
        entry = agg.setdefault(
            key,
            {
                "display_name": name.strip(),
                "quantity": 0.0,
                "unit": item.get("unit") or "",
            },
        )
        entry["quantity"] += qty_val
    return agg


def compare_spec_vs_drawings(project_id: str) -> Dict:
    spec_items = project_store.load_items(project_id, "spec")
    drawing_items = project_store.load_items(project_id, "drawing")
    if not spec_items or not drawing_items:
        return {"status": "pending", "rows": []}

    spec = _aggregate(spec_items)
    drawing = _aggregate(drawing_items)
    keys = set(spec.keys()) | set(drawing.keys())
    rows: List[Dict] = []
    for key in sorted(keys):
        spec_entry = spec.get(key, {})
        drawing_entry = drawing.get(key, {})
        spec_qty = round(spec_entry.get("quantity", 0.0), 3)
        drawing_qty = round(drawing_entry.get("quantity", 0.0), 3)
        delta = round(drawing_qty - spec_qty, 3)
        rows.append(
            {
                "position": spec_entry.get("display_name") or drawing_entry.get("display_name") or key,
                "spec": spec_qty,
                "drawings": drawing_qty,
                "delta": delta,
                "unit": spec_entry.get("unit") or drawing_entry.get("unit"),
            }
        )

    artifact = reports.save_discrepancy_report(project_id, rows)
    return {"status": "ready", "rows": rows, "artifact": artifact}
