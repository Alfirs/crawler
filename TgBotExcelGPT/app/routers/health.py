from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["health"])


@router.get("/")
async def healthcheck() -> dict:
    return {"status": "ok"}
