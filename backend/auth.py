import os, bcrypt, jwt
from datetime import datetime, timedelta
from database import get_db, row_to_dict

SECRET_KEY   = os.environ.get("SECRET_KEY", "t3n28-football-secret-change-in-prod")
ALGORITHM    = "HS256"
TOKEN_DAYS   = 30
ADMIN_EMAIL  = os.environ.get("ADMIN_EMAIL", "chidhungwanaroy4@gmail.com")

DAILY_LIMITS = {"free": 50, "starter": 200, "pro": 500, "premium": 2000}
CACHE_TTL    = {"free": 600, "starter": 300, "pro": 120, "premium": 60}

TIERS = {
    "free":    {"label": "Free",    "price": 0,  "color": "#64748b",
                "telegram": False, "channels": 0, "league_type": "non-top15",
                "affiliate": "owner", "analytics": False, "schedule": False,
                "watermark": True, "max_leagues": 99, "football_news": False,
                "goal_videos": False, "highlights": False, "ads": True},
    "starter": {"label": "Starter", "price": 3,  "color": "#3b82f6",
                "telegram": True,  "channels": 1, "league_type": "top15",
                "affiliate": "own","analytics": "basic", "schedule": False,
                "watermark": False,"max_leagues": 5,  "football_news": False,
                "goal_videos": False, "highlights": False, "ads": False},
    "pro":     {"label": "Pro",     "price": 5,  "color": "#22c55e",
                "telegram": True,  "channels": 3, "league_type": "top15",
                "affiliate": "own","analytics": "full", "schedule": True,
                "watermark": False,"max_leagues": 15, "football_news": True,
                "goal_videos": False, "highlights": False, "ads": False},
    "premium": {"label": "Premium", "price": 10, "color": "#f59e0b",
                "telegram": True,  "channels": 999,"league_type": "all",
                "affiliate": "own","analytics": "full", "schedule": True,
                "watermark": False,"max_leagues": 999,"football_news": True,
                "goal_videos": True,"highlights": True,"ads": False},
}

TOP15_LEAGUE_IDS = [39,140,135,78,61,2,3,88,94,144,253,45,848,4,1]

def hash_password(pw: str) -> str:
    return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()

def verify_password(pw: str, hashed: str) -> bool:
    return bcrypt.checkpw(pw.encode(), hashed.encode())

def create_token(user_id: int, email: str, tier: str) -> str:
    return jwt.encode({
        "sub":   str(user_id),
        "email": email,
        "tier":  tier,
        "exp":   datetime.utcnow() + timedelta(days=TOKEN_DAYS),
    }, SECRET_KEY, algorithm=ALGORITHM)

def decode_token(token: str):
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except Exception:
        return None

def get_user_by_id(uid: int):
    db = get_db()
    row = db.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    db.close()
    return row_to_dict(row)

def get_user_by_email(email: str):
    db = get_db()
    row = db.execute("SELECT * FROM users WHERE email=?", (email.lower(),)).fetchone()
    db.close()
    return row_to_dict(row)

def is_admin(email: str) -> bool:
    return email.lower() == ADMIN_EMAIL.lower()

def can_use_league(league_id: int, tier: str) -> bool:
    cfg = TIERS.get(tier, TIERS["free"])
    if cfg["league_type"] == "all":
        return True
    if cfg["league_type"] == "top15":
        return league_id in TOP15_LEAGUE_IDS
    return league_id not in TOP15_LEAGUE_IDS
