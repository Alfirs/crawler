from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.config import get_settings, resolve_media_path
from app.services.wheel_fit import WheelFitService
from app.wheels import Wheel, WheelStore

settings = get_settings()
app = FastAPI(title="WheelSwap API", version="0.1.0")
app.mount("/media", StaticFiles(directory=settings.base_media_dir), name="media")

wheel_store = WheelStore()
wheel_fit_service = WheelFitService()


class ImageResultResponse(BaseModel):
    request_id: str
    result_url: str


class WheelsResponse(BaseModel):
    items: List[Wheel]


@app.on_event("shutdown")
async def shutdown_event() -> None:
    await wheel_fit_service.close()


@app.get("/api/wheels", response_model=WheelsResponse)
def list_wheels() -> WheelsResponse:
    return WheelsResponse(items=wheel_store.list_wheels())


@app.post("/api/render-catalog", response_model=ImageResultResponse, status_code=status.HTTP_200_OK)
async def render_catalog_endpoint(
    file: UploadFile = File(...),
    wheel_id: str = Form(...),
    wheel_reference: UploadFile | None = File(None),
) -> ImageResultResponse:
    wheel = wheel_store.get_wheel(wheel_id)
    if not wheel:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="wheel_id not found")

    car_bytes = await file.read()
    wheel_ref_bytes = await wheel_reference.read() if wheel_reference else None
    result_path = await wheel_fit_service.render_catalog(
        car_photo_bytes=car_bytes,
        wheel_photo_bytes=wheel_ref_bytes,
        wheel_prompt=wheel.style_prompt or wheel.short_description,
        wheel_metadata=wheel,
    )
    return _build_image_response(result_path)


def _build_image_response(result_path: Path) -> ImageResultResponse:
    relative_url = f"/media/results/{result_path.name}"
    return ImageResultResponse(request_id=result_path.stem, result_url=relative_url)
