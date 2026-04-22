# Settlemate Australia - Deployment Guide

## Architecture

```
[React Frontend]  →  [Flask API]  →  [SQLite/PostgreSQL]
   Vercel              Railway
```

---

## Frontend - Vercel

### Setup

1. Push frontend code to a Git repository
2. Go to [vercel.com](https://vercel.com) and import the repository
3. Set the **Root Directory** to `frontend`
4. Framework preset: **Create React App**

### Environment Variables

Set in Vercel dashboard → Settings → Environment Variables:

| Variable            | Value                                      |
|---------------------|--------------------------------------------|
| REACT_APP_API_URL   | https://api-settlemate-au.railway.app      |

### Build Settings

- Build Command: `npm run build`
- Output Directory: `build`
- Install Command: `npm install`

### Custom Domain (optional)

1. Go to Settings → Domains
2. Add your domain
3. Update DNS records as instructed

---

## Backend - Railway

### Setup

1. Go to [railway.app](https://railway.app) and create a new project
2. Deploy from GitHub or use the Railway CLI:
   ```bash
   npm install -g @railway/cli
   railway login
   cd backend
   railway init
   railway up
   ```

### Environment Variables

Set in Railway dashboard → Variables:

| Variable       | Value                                              |
|----------------|----------------------------------------------------|
| FLASK_ENV      | production                                         |
| DATABASE_URL   | sqlite:///class_actions.db (or PostgreSQL URI)     |
| CORS_ORIGINS   | https://settlemate-au.vercel.app                   |
| RATE_LIMIT     | 100/hour                                           |
| PORT           | 5000                                               |

### Procfile

Create `backend/Procfile`:
```
web: gunicorn app:app --bind 0.0.0.0:$PORT
```

### Database (PostgreSQL upgrade)

For production, upgrade to PostgreSQL:

1. In Railway, add a PostgreSQL plugin
2. Copy the `DATABASE_URL` from the plugin
3. Set it in your backend environment variables
4. The SQLAlchemy code works with both SQLite and PostgreSQL

---

## Post-Deployment Checks

### Health Check
```bash
curl https://api-settlemate-au.railway.app/api/health
```
Expected: `{"status": "healthy", "timestamp": "..."}`

### Populate Database
```bash
# SSH into Railway or run locally with production DATABASE_URL
python scraper.py
```

### Verify Frontend
1. Visit https://settlemate-au.vercel.app
2. Confirm cases load
3. Test search functionality
4. Test eligibility checker
5. Test modal popups
6. Test on mobile viewport

---

## Monitoring

- **Railway:** Built-in logs at railway.app dashboard
- **Vercel:** Analytics and logs at vercel.com dashboard
- **Scraper logs:** `GET /api/health` for uptime; check ScraperLog table for scraper health
