"""
Settings API routes
"""
import json
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.database import get_db
from app.db.models import Setting, GoalMode, Profession
from app.services.antispam import AntiSpamService

router = APIRouter()


class SettingUpdate(BaseModel):
    value: str


DEFAULT_SETTINGS = {
    "daily_limit": "15",
    "followup_cooldown_hours": "48",
    "goal_mode": "normal",
    "gemini_api_key": "",
    "user_professions": "[]",  # JSON array of profession codes
    "onboarding_completed": "false",
}


def get_setting_value(db: Session, key: str, default: str = "") -> str:
    setting = db.query(Setting).filter(Setting.key == key).first()
    return setting.value if setting else DEFAULT_SETTINGS.get(key, default)


def set_setting_value(db: Session, key: str, value: str):
    setting = db.query(Setting).filter(Setting.key == key).first()
    if setting:
        setting.value = value
    else:
        setting = Setting(key=key, value=value)
        db.add(setting)
    db.commit()


@router.get("/")
def get_all_settings(db: Session = Depends(get_db)):
    settings = db.query(Setting).all()
    result = {**DEFAULT_SETTINGS}
    for s in settings:
        result[s.key] = s.value
    if result.get("gemini_api_key"):
        key = result["gemini_api_key"]
        if len(key) > 8:
            result["gemini_api_key"] = key[:4] + "..." + key[-4:]
    return result


@router.put("/{key}")
def update_setting(key: str, data: SettingUpdate, db: Session = Depends(get_db)):
    if key == "daily_limit":
        try:
            limit = int(data.value)
            antispam = AntiSpamService(db)
            is_valid, message = antispam.validate_new_limit(limit)
            if not is_valid:
                raise HTTPException(status_code=400, detail=message)
        except ValueError:
            raise HTTPException(status_code=400, detail="Must be a number")
    elif key == "goal_mode":
        valid_modes = [m.value for m in GoalMode]
        if data.value not in valid_modes:
            raise HTTPException(status_code=400, detail=f"Must be one of: {valid_modes}")
    
    set_setting_value(db, key, data.value)
    return {"key": key, "value": data.value}


@router.get("/quota/current")
def get_current_quota(db: Session = Depends(get_db)):
    antispam = AntiSpamService(db)
    return antispam.get_remaining_quota()


@router.get("/risk/assessment")
def get_risk_assessment(db: Session = Depends(get_db)):
    antispam = AntiSpamService(db)
    return antispam.get_risk_assessment()


# ============= PROFESSIONS =============

PROFESSION_LABELS = {
    "smm": "SMM-специалист",
    "designer": "Дизайнер",
    "targetolog": "Таргетолог",
    "reelsmaker": "Рилсмейкер / Монтажер",
    "techspec": "Техспец (GetCourse, боты)",
    "copywriter": "Копирайтер / Сценарист",
    "marketer": "Маркетолог",
    "ad_buyer": "Закупщик рекламы",
    "assistant": "Ассистент",
    "parsing": "Парсинг / Рассылки",
    "lawyer": "Юрист / Бухгалтер",
    "avitolog": "Авитолог",
    "producer": "Продюсер (запуски)",
    "other": "Другое",
}


@router.get("/professions/list")
def get_all_professions():
    """Get list of all available professions with labels"""
    return [
        {"code": p.value, "label": PROFESSION_LABELS.get(p.value, p.value)}
        for p in Profession
    ]


class ProfessionsUpdate(BaseModel):
    professions: List[str]


@router.get("/professions/user")
def get_user_professions(db: Session = Depends(get_db)):
    """Get current user's selected professions"""
    value = get_setting_value(db, "user_professions", "[]")
    try:
        professions = json.loads(value)
    except json.JSONDecodeError:
        professions = []
    
    return {
        "professions": professions,
        "onboarding_completed": get_setting_value(db, "onboarding_completed", "false") == "true"
    }


@router.put("/professions/user")
def set_user_professions(data: ProfessionsUpdate, db: Session = Depends(get_db)):
    """Set user's selected professions"""
    valid_codes = [p.value for p in Profession]
    
    # Validate profession codes
    for p in data.professions:
        if p not in valid_codes:
            raise HTTPException(status_code=400, detail=f"Invalid profession: {p}")
    
    set_setting_value(db, "user_professions", json.dumps(data.professions))
    set_setting_value(db, "onboarding_completed", "true")
    
    return {
        "professions": data.professions,
        "onboarding_completed": True
    }
