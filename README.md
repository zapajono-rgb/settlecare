# Settlemate Australia

A class action settlement finder for Australian users. Search Federal Court and state court class actions, check your eligibility, and find claim portals.

## Architecture

```
frontend/ (React 18)        backend/ (Flask + SQLAlchemy)
├── src/App.jsx              ├── app.py          — API endpoints
├── src/App.css              ├── models.py       — Database models
└── public/index.html        ├── scraper.py      — Court data scraper
                             └── requirements.txt
```

## Quick Start

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python scraper.py          # Populate database with demo cases
python app.py              # Start API on localhost:5000
```

### Frontend

```bash
cd frontend
npm install
npm start                  # Opens localhost:3000
```

## Features

- **Search** — Find class actions by case name, defendant, or keyword
- **Eligibility Checker** — Enter company/product details to find matching cases
- **Case Details** — Full case information with law firm contacts and claim portals
- **Urgent Deadlines** — Highlighted cases with approaching claim deadlines
- **Responsive** — Mobile, tablet, and desktop layouts

## Data Sources

- Federal Court of Australia class actions registry
- Demo data for development (6 realistic cases)

## API

See [docs/API.md](docs/API.md) for full endpoint documentation.

Key endpoints:
- `GET /api/class-actions` — List/search cases
- `POST /api/check-eligibility` — Match user to cases
- `GET /api/stats` — Database statistics
- `GET /api/deadlines/urgent` — Approaching deadlines

## Deployment

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for Vercel + Railway setup.

## Legal Disclaimer

Settlemate Australia is an informational tool only. The information provided does not constitute legal advice. Always consult a qualified legal professional before making decisions about class action participation. Case data is sourced from publicly available court records.
