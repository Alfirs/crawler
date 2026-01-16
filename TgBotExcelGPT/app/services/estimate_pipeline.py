from typing import Dict, List

from app.services import llm_utils, neuroapi, project_store, reports


async def validate_final_estimate(project_id: str, drive_link: str) -> Dict:
    """
    Call out to LLM to validate structure (missing names/units/quantities).
    """
    response = await neuroapi.validate_estimate(project_id=project_id, file_link=drive_link)
    issues = llm_utils.extract_list(response, "issues")
    return {"issues": issues, "raw": response}


async def normalize_materials(project_id: str, drive_link: str) -> Dict:
    """
    Normalize naming and filter to materials/equipment only.
    Generates procurement Excel/JSON artifacts.
    """
    response = await neuroapi.normalize_procurement_list(project_id=project_id, file_link=drive_link)
    items = llm_utils.extract_list(response, "items")
    artifacts = None
    if items:
        project_store.save_items(project_id, "procurement", items)
        artifacts = reports.save_procurement_report(project_id, items)
    return {"items": items, "artifacts": artifacts, "raw": response}
