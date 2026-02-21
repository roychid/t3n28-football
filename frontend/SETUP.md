# t3n28-football — Setup Guide

## Stack
- **Backend:** Python + FastAPI + SQLite → hosted on **Render**
- **Frontend:** HTML/CSS/JS → hosted on **Render Static Site** (or Vercel)
- **No Firebase. No complex config.**

---

## 1. Deploy Backend to Render

1. Push the `backend/` folder to a GitHub repo
2. Go to https://render.com → New → **Web Service**
3. Connect your GitHub repo
4. Settings:
   - **Name:** t3n28-football-api
   - **Root Directory:** backend
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Plan:** Free
5. Add Environment Variables:
   - `SECRET_KEY` → click Generate (random string)
   - `FOOTBALL_API_KEY` → `9840d945cf9472498c43556397d6386f`
   - `ADMIN_EMAIL` → `chidhungwanaroy4@gmail.com`
   - `OWNER_AFFILIATE` → `https://t.me/t3n28football`
   - `DB_PATH` → `/data/t3n28.db`
6. Add a **Disk** (under Advanced):
   - Name: t3n28-db
   - Mount Path: /data
   - Size: 1 GB
7. Click **Deploy**
8. Copy your Render URL e.g. `https://t3n28-football-api.onrender.com`

---

## 2. Update Frontend API URL

Open `frontend/api.js` and update line 6:
```js
const API_BASE = 'https://t3n28-football-api.onrender.com'; // ← your URL here
```

---

## 3. Deploy Frontend to Render

1. Go to Render → New → **Static Site**
2. Connect same GitHub repo
3. Settings:
   - **Root Directory:** frontend
   - **Build Command:** (leave empty)
   - **Publish Directory:** .
4. Click **Deploy**
5. Your app is live!

---

## 4. First Login (Admin)

1. Go to your frontend URL → click **Register**
2. Register with `chidhungwanaroy4@gmail.com`
3. You'll be redirected to the **Admin Panel** automatically

---

## Tier Daily Request Limits

| Tier    | Requests/day | Cache TTL |
|---------|-------------|-----------|
| Free    | 50          | 10 min    |
| Starter | 200         | 5 min     |
| Pro     | 500         | 2 min     |
| Premium | 2,000       | 60 sec    |

API limit: **75,000/day** — shared cache keeps real calls minimal.

---

## File Structure

```
backend/
  main.py          ← FastAPI routes
  database.py      ← SQLite setup
  auth.py          ← JWT + tier logic
  requirements.txt
  render.yaml

frontend/
  api.js           ← all backend calls (replaces Firebase)
  sidebar.js       ← sidebar with tier-gating
  style.css
  login.html
  register.html
  dashboard.html
  admin.html
  live.html
  standings.html
  messages.html
  channels.html
  leagues.html
  analytics.html
  settings.html
  affiliate.html
  schedule.html
  news.html
  videos.html
  notifications.html
  pricing.html
```
