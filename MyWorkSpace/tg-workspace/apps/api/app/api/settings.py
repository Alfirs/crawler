"""
Settings API routes
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel

from app.db.database import get_db
from app.db.models import Setting, GoalMode
from app.services.antispam import AntiSpamService

router = APIRouter()


class SettingUpdate(BaseModel):
    value: str


DEFAULT_SETTINGS = {
    "daily_limit": "15",
    "followup_cooldown_hours": "48",
    "goal_mode": "normal",
    "gemini_api_key": "",
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
