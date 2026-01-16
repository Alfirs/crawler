from typing import Dict, List

from app.services import comparison, pricing, project_store, reports


def prepare_final_report(project_id: str) -> Dict:
    discrepancy = comparison.compare_spec_vs_drawings(project_id)
    discrepancies = discrepancy.get("rows") if isinstance(discrepancy, dict) else []

    procurement = project_store.load_items(project_id, "procurement")
    supplier_summary = pricing.build_summary(project_id)
    supplier_rows: List[Dict] = supplier_summary.get("rows") if isinstance(supplier_summary, dict) else []

    if not procurement:
        return {
            "status": "missing_procurement",
            "discrepancies": discrepancies,
            "suppliers": supplier_rows,
        }

    artifact = reports.save_final_overview(
        project_id=project_id,
        discrepancies=discrepancies or [],
        procurement=procurement,
        supplier_rows=supplier_rows or [],
    )
    return {
        "status": "ready",
        "artifact": artifact,
        "discrepancies": discrepancies,
        "procurement": procurement,
        "suppliers": supplier_rows,
    }
