import os, json, httpx
from datetime import datetime, timedelta
from typing import Optional

from fastapi import FastAPI, HTTPException, Depends, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr

from database import get_db, init_db, row_to_dict, rows_to_list
from auth import (
    hash_password, verify_password, create_token, decode_token,
    get_user_by_id, get_user_by_email, is_admin,
    DAILY_LIMITS, CACHE_TTL, TIERS, TOP15_LEAGUE_IDS, can_use_league,
    ADMIN_EMAIL
)

FOOTBALL_API_KEY  = os.environ.get("FOOTBALL_API_KEY", "9840d945cf9472498c43556397d6386f")
FOOTBALL_API_BASE = "https://v3.football.api-sports.io"
OWNER_AFFILIATE   = os.environ.get("OWNER_AFFILIATE", "https://t.me/t3n28football")

app = FastAPI(title="t3n28-football API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    init_db()

# ── Pydantic models ────────────────────────────────────────────
class RegisterIn(BaseModel):
    email:    EmailStr
    password: str
    name:     str
    whatsapp: Optional[str] = ""
    interested_tier: Optional[str] = "free"

class LoginIn(BaseModel):
    email:    EmailStr
    password: str

class SubRequestIn(BaseModel):
    tier:     str
    whatsapp: Optional[str] = ""

class RequestActionIn(BaseModel):
    request_id: int
    action:     str   # approve | reject
    note:       Optional[str] = ""

class TierChangeIn(BaseModel):
    user_id:  int
    new_tier: str
    note:     Optional[str] = ""

class UserStatusIn(BaseModel):
    user_id: int
    status:  str  # active | disabled

# ── Auth dependency ────────────────────────────────────────────
def get_current_user(authorization: Optional[str] = Header(None)) -> dict:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401, "Missing token")
    payload = decode_token(authorization.split(" ", 1)[1])
    if not payload:
        raise HTTPException(401, "Token expired or invalid — please log in again")
    user = get_user_by_id(int(payload["sub"]))
    if not user or user["status"] != "active":
        raise HTTPException(401, "Account not found or disabled")
    return user

def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if not is_admin(user["email"]):
        raise HTTPException(403, "Admin only")
    return user


# ══════════════════════════════════════════════════════════════
#  AUTH
# ══════════════════════════════════════════════════════════════

@app.get("/")
def root():
    return {"status": "ok", "app": "t3n28-football API v2"}

@app.post("/auth/register")
def register(body: RegisterIn):
    if get_user_by_email(body.email):
        raise HTTPException(400, "Email already registered")
    if len(body.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters")

    db  = get_db()
    cur = db.execute(
        "INSERT INTO users (email,name,whatsapp,password_hash,tier) VALUES (?,?,?,?,?)",
        (body.email.lower(), body.name.strip(), body.whatsapp or "", hash_password(body.password), "free")
    )
    uid = cur.lastrowid

    if body.interested_tier and body.interested_tier != "free":
        db.execute(
            "INSERT INTO sub_requests (user_id,email,name,whatsapp,requested_tier) VALUES (?,?,?,?,?)",
            (uid, body.email.lower(), body.name.strip(), body.whatsapp or "", body.interested_tier)
        )

    db.commit(); db.close()
    token = create_token(uid, body.email.lower(), "free")
    return _auth_response(uid, body.email.lower(), body.name.strip(), "free", token)


@app.post("/auth/login")
def login(body: LoginIn):
    user = get_user_by_email(body.email.lower())
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "Incorrect email or password")
    if user["status"] != "active":
        raise HTTPException(403, "Account disabled — contact admin")

    db = get_db()
    db.execute("UPDATE users SET last_login=? WHERE id=?", (datetime.utcnow().isoformat(), user["id"]))
    db.commit(); db.close()

    token = create_token(user["id"], user["email"], user["tier"])
    return _auth_response(user["id"], user["email"], user["name"], user["tier"], token)


@app.get("/auth/me")
def me(user: dict = Depends(get_current_user)):
    tier = user["tier"]
    return {
        **_user_public(user),
        "tier_config":   TIERS.get(tier, TIERS["free"]),
        "daily_limit":   DAILY_LIMITS.get(tier, 50),
        "cache_ttl":     CACHE_TTL.get(tier, 600),
        "owner_affiliate": OWNER_AFFILIATE,
        "top15_ids":     TOP15_LEAGUE_IDS,
    }

def _user_public(u):
    return {
        "id": u["id"], "email": u["email"], "name": u["name"],
        "whatsapp": u["whatsapp"], "tier": u["tier"],
        "is_admin": is_admin(u["email"]), "status": u["status"],
        "created_at": u["created_at"],
    }

def _auth_response(uid, email, name, tier, token):
    return {
        "token":    token,
        "user_id":  uid,
        "email":    email,
        "name":     name,
        "tier":     tier,
        "is_admin": is_admin(email),
        "tier_config": TIERS.get(tier, TIERS["free"]),
        "daily_limit": DAILY_LIMITS.get(tier, 50),
        "owner_affiliate": OWNER_AFFILIATE,
        "top15_ids":   TOP15_LEAGUE_IDS,
    }


# ══════════════════════════════════════════════════════════════
#  FOOTBALL API PROXY  — shared cache + per-user counting
# ══════════════════════════════════════════════════════════════

@app.get("/football/{path:path}")
async def football_proxy(path: str, user: dict = Depends(get_current_user)):
    tier      = user["tier"]
    uid       = user["id"]
    today     = datetime.utcnow().strftime("%Y-%m-%d")
    ttl       = CACHE_TTL.get(tier, 600)
    limit     = DAILY_LIMITS.get(tier, 50)
    cache_key = path.replace("/","_")

    db = get_db()

    # 1. current usage
    usage_row = db.execute(
        "SELECT count FROM api_usage WHERE user_id=? AND date=?", (uid, today)
    ).fetchone()
    current = usage_row["count"] if usage_row else 0

    # 2. check cache
    cache_row   = db.execute("SELECT response,fetched_at FROM api_cache WHERE cache_key=?", (cache_key,)).fetchone()
    cache_hit   = False
    response_data = None

    if cache_row:
        age = (datetime.utcnow() - datetime.fromisoformat(cache_row["fetched_at"])).total_seconds()
        if age < ttl:
            response_data = json.loads(cache_row["response"])
            cache_hit     = True

    # 3. real API call if stale
    if not cache_hit:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.get(
                    f"{FOOTBALL_API_BASE}/{path}",
                    headers={"x-apisports-key": FOOTBALL_API_KEY}
                )
            if r.status_code != 200:
                db.close()
                raise HTTPException(r.status_code, f"Football API returned {r.status_code}")
            response_data = r.json()
        except httpx.TimeoutException:
            db.close()
            raise HTTPException(504, "Football API timeout — try again")

        db.execute("""
            INSERT INTO api_cache (cache_key,endpoint,response,fetched_at,fetched_by,fetched_tier)
            VALUES (?,?,?,?,?,?)
            ON CONFLICT(cache_key) DO UPDATE SET
                response=excluded.response, fetched_at=excluded.fetched_at,
                fetched_by=excluded.fetched_by, fetched_tier=excluded.fetched_tier
        """, (cache_key, "/"+path, json.dumps(response_data),
              datetime.utcnow().isoformat(), uid, tier))

    # 4. log usage (always)
    new_count = current + 1
    db.execute("""
        INSERT INTO api_usage (user_id,email,tier,date,count,cache_hits,real_calls,last_call)
        VALUES (?,?,?,?,1,?,?,?)
        ON CONFLICT(user_id,date) DO UPDATE SET
            count=count+1, cache_hits=cache_hits+?, real_calls=real_calls+?,
            last_call=excluded.last_call, tier=excluded.tier
    """, (uid, user["email"], tier, today,
          1 if cache_hit else 0, 0 if cache_hit else 1,
          datetime.utcnow().isoformat(),
          1 if cache_hit else 0, 0 if cache_hit else 1))

    # 5. daily total
    db.execute("""
        INSERT INTO api_daily_total (date,total,cache_hits,real_calls) VALUES (?,1,?,?)
        ON CONFLICT(date) DO UPDATE SET
            total=total+1, cache_hits=cache_hits+?, real_calls=real_calls+?
    """, (today,
          1 if cache_hit else 0, 0 if cache_hit else 1,
          1 if cache_hit else 0, 0 if cache_hit else 1))

    db.commit(); db.close()

    return {
        "data":      response_data,
        "cache_hit": cache_hit,
        "usage":     {"count": new_count, "limit": limit, "remaining": max(0, limit - new_count)},
        "warn":      new_count >= int(limit * 0.8),
        "over_limit": new_count > limit,
    }


# ══════════════════════════════════════════════════════════════
#  USAGE
# ══════════════════════════════════════════════════════════════

@app.get("/usage/me")
def usage_me(user: dict = Depends(get_current_user)):
    today = datetime.utcnow().strftime("%Y-%m-%d")
    db    = get_db()
    row   = db.execute("SELECT * FROM api_usage WHERE user_id=? AND date=?", (user["id"], today)).fetchone()
    db.close()
    data  = row_to_dict(row) or {"count": 0, "cache_hits": 0, "real_calls": 0}
    limit = DAILY_LIMITS.get(user["tier"], 50)
    count = data.get("count", 0)
    return {
        "count":      count,
        "cache_hits": data.get("cache_hits", 0),
        "real_calls": data.get("real_calls", 0),
        "limit":      limit,
        "remaining":  max(0, limit - count),
        "pct":        round(count / limit * 100, 1),
        "date":       today,
        "tier":       user["tier"],
    }


# ══════════════════════════════════════════════════════════════
#  SUBSCRIPTIONS
# ══════════════════════════════════════════════════════════════

@app.post("/subscriptions/request")
def sub_request(body: SubRequestIn, user: dict = Depends(get_current_user)):
    if body.tier not in ("starter", "pro", "premium"):
        raise HTTPException(400, "Invalid tier")
    if user["tier"] == body.tier:
        raise HTTPException(400, "Already on this tier")

    db = get_db()
    existing = db.execute(
        "SELECT id FROM sub_requests WHERE user_id=? AND status='pending'", (user["id"],)
    ).fetchone()
    if existing:
        db.close()
        raise HTTPException(400, "You already have a pending request")

    db.execute(
        "INSERT INTO sub_requests (user_id,email,name,whatsapp,requested_tier) VALUES (?,?,?,?,?)",
        (user["id"], user["email"], user["name"], body.whatsapp or user["whatsapp"], body.tier)
    )
    db.commit(); db.close()
    return {"ok": True, "message": "Request submitted. Admin will review soon."}


@app.get("/subscriptions/mine")
def my_sub(user: dict = Depends(get_current_user)):
    db  = get_db()
    row = db.execute(
        "SELECT * FROM sub_requests WHERE user_id=? ORDER BY created_at DESC LIMIT 1", (user["id"],)
    ).fetchone()
    db.close()
    return row_to_dict(row) or {}


# ══════════════════════════════════════════════════════════════
#  NOTIFICATIONS
# ══════════════════════════════════════════════════════════════

@app.get("/notifications")
def get_notifs(user: dict = Depends(get_current_user)):
    db   = get_db()
    rows = db.execute(
        "SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC LIMIT 20", (user["id"],)
    ).fetchall()
    db.close()
    return rows_to_list(rows)

@app.post("/notifications/{nid}/read")
def mark_read(nid: int, user: dict = Depends(get_current_user)):
    db = get_db()
    db.execute("UPDATE notifications SET read=1 WHERE id=? AND user_id=?", (nid, user["id"]))
    db.commit(); db.close()
    return {"ok": True}

@app.post("/notifications/read-all")
def mark_all_read(user: dict = Depends(get_current_user)):
    db = get_db()
    db.execute("UPDATE notifications SET read=1 WHERE user_id=?", (user["id"],))
    db.commit(); db.close()
    return {"ok": True}


# ══════════════════════════════════════════════════════════════
#  ADMIN
# ══════════════════════════════════════════════════════════════

@app.get("/admin/stats")
def admin_stats(admin: dict = Depends(require_admin)):
    today = datetime.utcnow().strftime("%Y-%m-%d")
    db    = get_db()
    total_users    = db.execute("SELECT COUNT(*) as n FROM users").fetchone()["n"]
    tier_counts    = rows_to_list(db.execute("SELECT tier, COUNT(*) as n FROM users GROUP BY tier").fetchall())
    pending_reqs   = db.execute("SELECT COUNT(*) as n FROM sub_requests WHERE status='pending'").fetchone()["n"]
    new_today      = db.execute("SELECT COUNT(*) as n FROM users WHERE date(created_at)=?", (today,)).fetchone()["n"]
    api_today      = db.execute("SELECT * FROM api_daily_total WHERE date=?", (today,)).fetchone()
    unread_notifs  = db.execute("SELECT COUNT(*) as n FROM notifications WHERE read=0").fetchone()["n"]
    db.close()

    tiers = {r["tier"]: r["n"] for r in tier_counts}
    mrr   = (tiers.get("starter",0)*3 + tiers.get("pro",0)*5 + tiers.get("premium",0)*10)
    return {
        "total_users":   total_users,
        "new_today":     new_today,
        "pending_reqs":  pending_reqs,
        "unread_notifs": unread_notifs,
        "mrr":           mrr,
        "tiers":         tiers,
        "api_today":     row_to_dict(api_today) or {"total":0,"cache_hits":0,"real_calls":0},
    }

@app.get("/admin/users")
def admin_users(admin: dict = Depends(require_admin)):
    db   = get_db()
    rows = db.execute(
        "SELECT id,email,name,whatsapp,tier,status,created_at,last_login FROM users ORDER BY created_at DESC"
    ).fetchall()
    db.close()
    return rows_to_list(rows)

@app.get("/admin/requests")
def admin_requests(status: str = "pending", admin: dict = Depends(require_admin)):
    db   = get_db()
    rows = db.execute(
        "SELECT * FROM sub_requests WHERE status=? ORDER BY created_at DESC", (status,)
    ).fetchall()
    db.close()
    return rows_to_list(rows)

@app.post("/admin/requests/action")
def request_action(body: RequestActionIn, admin: dict = Depends(require_admin)):
    if body.action not in ("approve", "reject"):
        raise HTTPException(400, "action must be approve or reject")

    db  = get_db()
    req = row_to_dict(db.execute("SELECT * FROM sub_requests WHERE id=?", (body.request_id,)).fetchone())
    if not req:
        db.close(); raise HTTPException(404, "Request not found")

    now = datetime.utcnow().isoformat()
    db.execute("UPDATE sub_requests SET status=?,admin_note=?,resolved_at=? WHERE id=?",
               (body.action + "d", body.note or "", now, body.request_id))

    if body.action == "approve":
        user = row_to_dict(db.execute("SELECT tier FROM users WHERE id=?", (req["user_id"],)).fetchone())
        old  = user["tier"] if user else "free"
        db.execute("UPDATE users SET tier=? WHERE id=?", (req["requested_tier"], req["user_id"]))
        db.execute("INSERT INTO tier_changes (user_id,old_tier,new_tier,changed_by,note) VALUES (?,?,?,?,?)",
                   (req["user_id"], old, req["requested_tier"], admin["email"], body.note or ""))
        db.execute("INSERT INTO notifications (user_id,type,message) VALUES (?,?,?)",
                   (req["user_id"], "tier_approved",
                    f"🎉 Your {req['requested_tier'].title()} plan is now active! Enjoy your new features."))

    else:
        db.execute("INSERT INTO notifications (user_id,type,message) VALUES (?,?,?)",
                   (req["user_id"], "tier_rejected",
                    f"Your {req['requested_tier'].title()} request was not approved. {body.note or 'Contact admin for details.'}"))

    db.commit(); db.close()
    return {"ok": True}

@app.post("/admin/users/change-tier")
def change_tier(body: TierChangeIn, admin: dict = Depends(require_admin)):
    if body.new_tier not in TIERS:
        raise HTTPException(400, f"Invalid tier. Choose from {list(TIERS)}")
    db   = get_db()
    user = row_to_dict(db.execute("SELECT * FROM users WHERE id=?", (body.user_id,)).fetchone())
    if not user:
        db.close(); raise HTTPException(404, "User not found")
    db.execute("UPDATE users SET tier=? WHERE id=?", (body.new_tier, body.user_id))
    db.execute("INSERT INTO tier_changes (user_id,old_tier,new_tier,changed_by,note) VALUES (?,?,?,?,?)",
               (body.user_id, user["tier"], body.new_tier, admin["email"], body.note or ""))
    db.execute("INSERT INTO notifications (user_id,type,message) VALUES (?,?,?)",
               (body.user_id, "tier_changed", f"Your plan has been updated to {body.new_tier.title()}."))
    db.commit(); db.close()
    return {"ok": True}

@app.post("/admin/users/status")
def change_status(body: UserStatusIn, admin: dict = Depends(require_admin)):
    if body.status not in ("active", "disabled"):
        raise HTTPException(400, "status must be active or disabled")
    db = get_db()
    db.execute("UPDATE users SET status=? WHERE id=?", (body.status, body.user_id))
    db.commit(); db.close()
    return {"ok": True}

@app.get("/admin/usage/daily")
def admin_daily(days: int = 7, admin: dict = Depends(require_admin)):
    db, rows = get_db(), []
    for i in range(days):
        d   = (datetime.utcnow() - timedelta(days=i)).strftime("%Y-%m-%d")
        row = db.execute("SELECT * FROM api_daily_total WHERE date=?", (d,)).fetchone()
        rows.append(row_to_dict(row) or {"date": d, "total": 0, "cache_hits": 0, "real_calls": 0})
    db.close()
    return rows

@app.get("/admin/usage/users")
def admin_usage_users(date: str = None, admin: dict = Depends(require_admin)):
    date = date or datetime.utcnow().strftime("%Y-%m-%d")
    db   = get_db()
    rows = db.execute(
        "SELECT * FROM api_usage WHERE date=? ORDER BY count DESC LIMIT 50", (date,)
    ).fetchall()
    db.close()
    return rows_to_list(rows)

@app.delete("/admin/cache")
def clear_cache(admin: dict = Depends(require_admin)):
    db = get_db()
    db.execute("DELETE FROM api_cache")
    db.commit(); db.close()
    return {"ok": True, "message": "Cache cleared"}
