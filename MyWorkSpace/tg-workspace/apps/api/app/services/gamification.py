"""
Gamification Service
XP, levels, badges, streaks, and goals management
"""
from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
import logging

from app.db.models import (
    UserProgress, Badge, DailyGoal, WeeklyGoal, MonthlyGoal,
    Lead, Outreach, LeadStatus, GoalMode
)

logger = logging.getLogger(__name__)

# XP Rewards
XP_REWARDS = {
    "outreach_sent": 5,
    "followup_sent": 3,
    "reply_received": 10,
    "call_scheduled": 20,
    "deal_won": 50,
    "funnel_move": 5,
    "daily_goal_complete": 25,
    "weekly_goal_complete": 100,
}

# Level thresholds (XP needed for each level)
LEVEL_THRESHOLDS = [
    0,      # Level 1
    100,    # Level 2
    250,    # Level 3
    500,    # Level 4
    800,    # Level 5
    1200,   # Level 6
    1700,   # Level 7
    2300,   # Level 8
    3000,   # Level 9
    4000,   # Level 10
    5200,   # Level 11
    6600,   # Level 12
    8200,   # Level 13
    10000,  # Level 14
    12500,  # Level 15
    15500,  # Level 16
    19000,  # Level 17
    23000,  # Level 18
    28000,  # Level 19
    35000,  # Level 20
]

# Badge definitions
BADGE_DEFINITIONS = [
    {"name": "Первый клиент", "icon": "🥇", "condition_type": "won", "condition_value": 1, 
     "description": "Закрыть первую сделку"},
    {"name": "5 клиентов", "icon": "🏆", "condition_type": "won", "condition_value": 5,
     "description": "Закрыть 5 сделок"},
    {"name": "10 клиентов", "icon": "👑", "condition_type": "won", "condition_value": 10,
     "description": "Закрыть 10 сделок"},
    {"name": "7 дней подряд", "icon": "🔥", "condition_type": "streak", "condition_value": 7,
     "description": "Выполнять цели 7 дней подряд"},
    {"name": "14 дней подряд", "icon": "💪", "condition_type": "streak", "condition_value": 14,
     "description": "Выполнять цели 14 дней подряд"},
    {"name": "30 дней подряд", "icon": "⚡", "condition_type": "streak", "condition_value": 30,
     "description": "Выполнять цели 30 дней подряд"},
    {"name": "50 сообщений", "icon": "💬", "condition_type": "outreach", "condition_value": 50,
     "description": "Отправить 50 сообщений"},
    {"name": "100 сообщений", "icon": "📨", "condition_type": "outreach", "condition_value": 100,
     "description": "Отправить 100 сообщений"},
    {"name": "500 сообщений", "icon": "📬", "condition_type": "outreach", "condition_value": 500,
     "description": "Отправить 500 сообщений"},
    {"name": "10 ответов", "icon": "🎯", "condition_type": "replies", "condition_value": 10,
     "description": "Получить 10 ответов"},
    {"name": "50 ответов", "icon": "🎪", "condition_type": "replies", "condition_value": 50,
     "description": "Получить 50 ответов"},
    {"name": "30k за 14 дней", "icon": "💰", "condition_type": "revenue_14d", "condition_value": 30000,
     "description": "Заработать 30,000 за 14 дней"},
    {"name": "100k за месяц", "icon": "💎", "condition_type": "revenue_month", "condition_value": 100000,
     "description": "Заработать 100,000 за месяц"},
]

# Goal mode settings
GOAL_MODES = {
    GoalMode.LITE: {
        "daily_messages": 10,
        "daily_followups": 3,
        "daily_moves": 1,
        "weekly_messages": 50,
        "weekly_followups": 15,
        "weekly_calls": 2,
    },
    GoalMode.NORMAL: {
        "daily_messages": 20,
        "daily_followups": 5,
        "daily_moves": 1,
        "weekly_messages": 100,
        "weekly_followups": 25,
        "weekly_calls": 3,
    },
    GoalMode.HARD: {
        "daily_messages": 40,
        "daily_followups": 10,
        "daily_moves": 3,
        "weekly_messages": 200,
        "weekly_followups": 50,
        "weekly_calls": 7,
    },
}


class GamificationService:
    """Manage gamification features"""
    
    def __init__(self, db: Session):
        self.db = db
    
    def get_or_create_progress(self) -> UserProgress:
        """Get or create user progress record"""
        progress = self.db.query(UserProgress).first()
        
        if not progress:
            progress = UserProgress(xp=0, level=1, streak_days=0)
            self.db.add(progress)
            self.db.commit()
            self.db.refresh(progress)
            
            # Initialize badges
            self._initialize_badges()
        
        return progress
    
    def _initialize_badges(self):
        """Create badge records if they don't exist"""
        for badge_def in BADGE_DEFINITIONS:
            exists = self.db.query(Badge).filter(Badge.name == badge_def["name"]).first()
            if not exists:
                badge = Badge(
                    name=badge_def["name"],
                    description=badge_def["description"],
                    icon=badge_def["icon"],
                    condition_type=badge_def["condition_type"],
                    condition_value=badge_def["condition_value"],
                    is_earned=False
                )
                self.db.add(badge)
        
        self.db.commit()
    
    def add_xp(self, action: str, custom_amount: int = None) -> Dict[str, Any]:
        """Add XP for an action and check for level up"""
        progress = self.get_or_create_progress()
        
        xp_amount = custom_amount if custom_amount else XP_REWARDS.get(action, 0)
        old_level = progress.level
        
        progress.xp += xp_amount
        
        # Check for level up
        new_level = self._calculate_level(progress.xp)
        leveled_up = new_level > old_level
        
        if leveled_up:
            progress.level = new_level
        
        self.db.commit()
        
        return {
            "xp_earned": xp_amount,
            "total_xp": progress.xp,
            "level": progress.level,
            "leveled_up": leveled_up,
            "old_level": old_level if leveled_up else None,
            "xp_to_next_level": self._get_xp_to_next_level(progress.xp, progress.level)
        }
    
    def _calculate_level(self, xp: int) -> int:
        """Calculate level based on XP"""
        for level, threshold in enumerate(LEVEL_THRESHOLDS):
            if xp < threshold:
                return max(1, level)
        return len(LEVEL_THRESHOLDS)
    
    def _get_xp_to_next_level(self, current_xp: int, current_level: int) -> int:
        """Calculate XP needed for next level"""
        if current_level >= len(LEVEL_THRESHOLDS):
            return 0
        
        next_threshold = LEVEL_THRESHOLDS[current_level]
        return max(0, next_threshold - current_xp)
    
    def update_streak(self) -> Dict[str, Any]:
        """Update streak based on daily goal completion"""
        progress = self.get_or_create_progress()
        today = date.today()
        
        # Get today's goal
        daily_goal = self.get_or_create_daily_goal(today)
        goal_completed = self._is_daily_goal_complete(daily_goal)
        
        result = {
            "streak_days": progress.streak_days,
            "streak_updated": False,
            "streak_broken": False,
        }
        
        if progress.last_active_date:
            days_since_active = (today - progress.last_active_date).days
            
            if days_since_active == 0:
                # Same day, no change
                pass
            elif days_since_active == 1 and goal_completed:
                # Consecutive day with completed goal
                progress.streak_days += 1
                progress.last_active_date = today
                result["streak_updated"] = True
                
                # Update longest streak
                if progress.streak_days > progress.longest_streak:
                    progress.longest_streak = progress.streak_days
            elif days_since_active > 1:
                # Streak broken
                if goal_completed:
                    progress.streak_days = 1
                    progress.last_active_date = today
                else:
                    progress.streak_days = 0
                result["streak_broken"] = True
        else:
            # First day
            if goal_completed:
                progress.streak_days = 1
                progress.last_active_date = today
                result["streak_updated"] = True
        
        result["streak_days"] = progress.streak_days
        result["longest_streak"] = progress.longest_streak
        
        self.db.commit()
        return result
    
    def _is_daily_goal_complete(self, goal: DailyGoal) -> bool:
        """Check if daily goal is complete"""
        return (
            goal.messages_done >= goal.messages_target and
            goal.followups_done >= goal.followups_target and
            goal.moves_done >= goal.moves_target
        )
    
    def get_or_create_daily_goal(self, for_date: date = None) -> DailyGoal:
        """Get or create daily goal for a date"""
        if for_date is None:
            for_date = date.today()
        
        goal = self.db.query(DailyGoal).filter(DailyGoal.date == for_date).first()
        
        if not goal:
            # Get goal mode from settings
            mode = self._get_goal_mode()
            settings = GOAL_MODES[mode]
            
            goal = DailyGoal(
                date=for_date,
                messages_target=settings["daily_messages"],
                followups_target=settings["daily_followups"],
                moves_target=settings["daily_moves"],
            )
            self.db.add(goal)
            self.db.commit()
            self.db.refresh(goal)
        
        return goal
    
    def _get_goal_mode(self) -> GoalMode:
        """Get current goal mode from settings"""
        from app.db.models import Setting
        setting = self.db.query(Setting).filter(Setting.key == "goal_mode").first()
        
        if setting and setting.value in [m.value for m in GoalMode]:
            return GoalMode(setting.value)
        
        return GoalMode.NORMAL
    
    def check_and_award_badges(self) -> List[Dict[str, Any]]:
        """Check conditions and award new badges"""
        progress = self.get_or_create_progress()
        new_badges = []
        
        # Get stats
        stats = self._get_badge_stats()
        
        # Check each unearned badge
        unearned = self.db.query(Badge).filter(Badge.is_earned == False).all()
        
        for badge in unearned:
            earned = self._check_badge_condition(badge, stats)
            
            if earned:
                badge.is_earned = True
                badge.earned_at = datetime.utcnow()
                
                new_badges.append({
                    "name": badge.name,
                    "icon": badge.icon,
                    "description": badge.description,
                })
        
        self.db.commit()
        return new_badges
    
    def _get_badge_stats(self) -> Dict[str, Any]:
        """Get stats for badge condition checking"""
        progress = self.get_or_create_progress()
        
        # Count outreach
        total_outreach = self.db.query(Outreach).filter(
            Outreach.sent_at != None
        ).count()
        
        # Count replies
        total_replies = self.db.query(Outreach).filter(
            Outreach.result_status == 'replied'
        ).count()
        
        # Count won deals
        total_won = self.db.query(Lead).filter(
            Lead.status == LeadStatus.WON.value
        ).count()
        
        # Revenue last 14 days
        two_weeks_ago = datetime.utcnow() - timedelta(days=14)
        revenue_14d = self.db.query(func.sum(Lead.expected_revenue)).filter(
            Lead.status == LeadStatus.WON.value,
            Lead.status_changed_at >= two_weeks_ago
        ).scalar() or 0
        
        # Revenue this month
        month_start = date.today().replace(day=1)
        revenue_month = self.db.query(func.sum(Lead.expected_revenue)).filter(
            Lead.status == LeadStatus.WON.value,
            Lead.status_changed_at >= month_start
        ).scalar() or 0
        
        return {
            "streak": progress.streak_days,
            "outreach": total_outreach,
            "replies": total_replies,
            "won": total_won,
            "revenue_14d": revenue_14d,
            "revenue_month": revenue_month,
        }
    
    def _check_badge_condition(self, badge: Badge, stats: Dict[str, Any]) -> bool:
        """Check if badge condition is met"""
        condition_type = badge.condition_type
        condition_value = badge.condition_value
        
        current_value = stats.get(condition_type, 0)
        return current_value >= condition_value
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """Get all gamification data for dashboard"""
        progress = self.get_or_create_progress()
        today = date.today()
        
        daily_goal = self.get_or_create_daily_goal(today)
        
        # Calculate daily progress percentages
        daily_progress = {
            "messages": {
                "done": daily_goal.messages_done,
                "target": daily_goal.messages_target,
                "percent": min(100, int(daily_goal.messages_done / daily_goal.messages_target * 100)) if daily_goal.messages_target > 0 else 0
            },
            "followups": {
                "done": daily_goal.followups_done,
                "target": daily_goal.followups_target,
                "percent": min(100, int(daily_goal.followups_done / daily_goal.followups_target * 100)) if daily_goal.followups_target > 0 else 0
            },
            "moves": {
                "done": daily_goal.moves_done,
                "target": daily_goal.moves_target,
                "percent": min(100, int(daily_goal.moves_done / daily_goal.moves_target * 100)) if daily_goal.moves_target > 0 else 0
            }
        }
        
        # Get earned badges
        earned_badges = self.db.query(Badge).filter(Badge.is_earned == True).all()
        
        # XP progress to next level
        xp_for_current = LEVEL_THRESHOLDS[progress.level - 1] if progress.level > 0 else 0
        xp_for_next = LEVEL_THRESHOLDS[progress.level] if progress.level < len(LEVEL_THRESHOLDS) else progress.xp
        xp_in_level = progress.xp - xp_for_current
        xp_needed = xp_for_next - xp_for_current
        
        return {
            "level": progress.level,
            "xp": progress.xp,
            "xp_progress": {
                "current": xp_in_level,
                "needed": xp_needed,
                "percent": min(100, int(xp_in_level / xp_needed * 100)) if xp_needed > 0 else 100
            },
            "streak": {
                "current": progress.streak_days,
                "longest": progress.longest_streak,
            },
            "daily_goals": daily_progress,
            "badges": [
                {"name": b.name, "icon": b.icon, "description": b.description}
                for b in earned_badges
            ],
            "badges_count": len(earned_badges),
            "total_badges": len(BADGE_DEFINITIONS),
        }
    
    def increment_daily_stat(self, stat_type: str, amount: int = 1):
        """Increment a daily goal stat"""
        today = date.today()
        goal = self.get_or_create_daily_goal(today)
        
        if stat_type == "messages":
            goal.messages_done += amount
        elif stat_type == "followups":
            goal.followups_done += amount
        elif stat_type == "moves":
            goal.moves_done += amount
        
        # Check if goal is now complete
        if self._is_daily_goal_complete(goal) and not goal.is_completed:
            goal.is_completed = True
            # Award bonus XP
            self.add_xp("daily_goal_complete")
        
        self.db.commit()
