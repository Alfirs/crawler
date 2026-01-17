"""
Gamification API routes
"""
from datetime import date
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.database import get_db
from app.db.models import Badge
from app.services.gamification import GamificationService
from app.services.llm import generate_daily_summary

router = APIRouter()


@router.get("/dashboard")
def get_dashboard(db: Session = Depends(get_db)):
    """Get gamification dashboard data"""
    service = GamificationService(db)
    return service.get_dashboard_data()


@router.get("/progress")
def get_progress(db: Session = Depends(get_db)):
    """Get user progress"""
    service = GamificationService(db)
    progress = service.get_or_create_progress()
    return {
        "xp": progress.xp,
        "level": progress.level,
        "streak_days": progress.streak_days,
        "longest_streak": progress.longest_streak,
        "total_outreach": progress.total_outreach,
        "total_replies": progress.total_replies,
        "total_won": progress.total_won,
        "total_revenue": progress.total_revenue,
    }


@router.get("/badges")
def get_badges(db: Session = Depends(get_db)):
    """Get all badges with earned status"""
    badges = db.query(Badge).all()
    return [{
        "id": b.id,
        "name": b.name,
        "icon": b.icon,
        "description": b.description,
        "is_earned": b.is_earned,
        "earned_at": b.earned_at,
    } for b in badges]


@router.get("/daily-goal")
def get_daily_goal(db: Session = Depends(get_db)):
    """Get today's goal progress"""
    service = GamificationService(db)
    goal = service.get_or_create_daily_goal(date.today())
    return {
        "date": goal.date,
        "messages": {"done": goal.messages_done, "target": goal.messages_target},
        "followups": {"done": goal.followups_done, "target": goal.followups_target},
        "moves": {"done": goal.moves_done, "target": goal.moves_target},
        "is_completed": goal.is_completed,
    }


@router.post("/update-streak")
def update_streak(db: Session = Depends(get_db)):
    """Update streak based on today's progress"""
    service = GamificationService(db)
    return service.update_streak()


@router.get("/daily-summary")
def get_daily_summary(db: Session = Depends(get_db)):
    """Get AI-generated daily summary"""
    service = GamificationService(db)
    goal = service.get_or_create_daily_goal(date.today())
    
    stats = {
        "messages_sent": goal.messages_done,
        "replies": 0,
        "funnel_moves": goal.moves_done,
        "new_leads": 0,
        "won": 0,
    }
    
    summary = generate_daily_summary(stats)
    return {"summary": summary, "stats": stats}
