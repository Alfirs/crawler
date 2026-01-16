from typing import Dict, List, Optional

from app.services import comparison, llm_utils, neuroapi, project_store, unstructured_client


async def process_upload(
    project_id: str,
    file_links: List[str],
    is_specification: bool,
    is_drawing: bool,
    notes: Optional[str],
) -> Dict:
    """
    Entry point for intake processing:
    - run OCR/parse via Unstructured.io
    - extract structured data with GPT-4o
    - persist spec/drawing items and trigger comparison reports
    """
    parsed_docs = []
    for link in file_links:
        parsed = await unstructured_client.parse_document(link)
        parsed_docs.append({"link": link, "parsed": parsed})

    extraction = await neuroapi.extract_structured_data(
        project_id=project_id,
        documents=parsed_docs,
        tags={"specification": is_specification, "drawing": is_drawing},
        notes=notes,
    )
    items = llm_utils.extract_list(extraction, "items")

    saved: Dict[str, int] = {}
    if items:
        if is_specification:
            project_store.save_items(project_id, "spec", items)
            saved["spec"] = len(items)
        if is_drawing:
            project_store.save_items(project_id, "drawing", items)
            saved["drawing"] = len(items)

    project_store.save_metadata(
        project_id,
        {
            "last_upload": file_links,
            "last_notes": notes,
        },
    )

    discrepancy = None
    if project_store.has_items(project_id, "spec") and project_store.has_items(project_id, "drawing"):
        discrepancy = comparison.compare_spec_vs_drawings(project_id)

    return {
        "parsed": parsed_docs,
        "extraction": extraction,
        "items": items,
        "saved": saved,
        "discrepancy": discrepancy,
    }
