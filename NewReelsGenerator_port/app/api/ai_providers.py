"""
API endpoints для диагностики и мониторинга NeuroAPI провайдера
"""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Dict, Any, Optional
import os

from app.core.database import get_db
from app.services.image_gen import get_selected_model

router = APIRouter()


@router.get("/providers/neuroapi/health")
async def neuroapi_health() -> Dict[str, Any]:
    """
    Проверка здоровья и конфигурации NeuroAPI провайдера.
    """
    NEUROAPI_API_KEY = os.getenv("NEUROAPI_API_KEY")
    NEUROAPI_BASE_URL = os.getenv("NEUROAPI_BASE_URL", "https://neuroapi.host/v1")
    
    try:
        selected_model = get_selected_model()
    except Exception as e:
        selected_model = "gpt-image-1"
    
    return {
        "provider": "NeuroAPI",
        "base_url": NEUROAPI_BASE_URL,
        "selected_model": selected_model,
        "text_model": "gpt-4o-mini",
        "image_model": "gpt-image-1",
        "api_key_configured": bool(NEUROAPI_API_KEY),
        "status": "healthy" if NEUROAPI_API_KEY else "no_api_key"
    }


# Backward compatibility endpoint
@router.get("/providers/aitunnel/health")
async def aitunnel_health_redirect() -> Dict[str, Any]:
    """Редирект для обратной совместимости."""
    return await neuroapi_health()