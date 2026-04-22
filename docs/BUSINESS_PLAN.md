# SettleCare — Business Plan

## What it is
SettleCare helps everyday Australians discover class action settlements they're eligible for and guides them to file claims. We automatically track 70+ active settlements across Federal, state, and territory courts.

## The Problem
- Billions of dollars in class action settlements go unclaimed every year in Australia
- Most Australians have no idea they're eligible — they don't follow legal news
- Finding and understanding eligibility criteria is painful (scattered across law firm websites, written in legalese)
- No single, consumer-friendly tool exists to check eligibility across all active settlements

## The Solution
A simple web app that:
1. **Scans** law firm and court websites automatically for new settlements
2. **Screens** users with a 2-minute quiz to identify potential matches
3. **Checks** eligibility through detailed question flows per case
4. **Connects** users directly to official claim portals — no middleman

## Revenue Model

### 1. Freemium Subscriptions (Primary — Immediate)
| Tier | Price | Includes |
|------|-------|---------|
| Free | $0 | Browse cases, quiz, 3 eligibility checks |
| Premium Monthly | $4.99/mo | Unlimited checks, email alerts, priority support |
| Premium Yearly | $29.99/yr | Everything in Premium, save 50% |

**Why it converts:** Users discover they might be owed money (e.g., $200–$2,000). Paying $5 to confirm eligibility is a no-brainer when the potential payout is 40–400x the cost.

**Target conversion:** 5–10% free → paid (typical for high-intent tools)

### 2. Law Firm Referral Fees (Secondary — Month 2+)
- Law firms running class actions want to reach eligible plaintiffs
- Charge law firms for **featured listings** ($200–500/month per case)
- Or charge **per qualified lead** ($5–20 per user who clicks through to claim portal)
- This is the real scale revenue — law firms already spend heavily on plaintiff acquisition

### 3. Affiliate Commissions (Passive)
- Partner with legal services (will-writing, small claims, legal insurance)
- Add a "related services" section for users who complete checks
- 10–30% commission on referrals

## Go-To-Market Strategy

### Phase 1: Launch (Week 1–2)
1. Deploy to Render (free tier for MVP)
2. Set up Stripe for payments
3. Post on r/AusFinance, r/AusLegal, r/australia
4. Share in Facebook groups (Australian consumer rights, money-saving groups)
5. Submit to Product Hunt

### Phase 2: Growth (Month 1–3)
1. SEO content: "Am I eligible for [company] class action?" pages
2. Google Ads targeting "[company name] class action" (very high intent, moderate CPC)
3. Partner with consumer advocacy sites (CHOICE, consumer affairs)
4. Press release to Australian tech/finance media

### Phase 3: Scale (Month 3+)
1. Launch law firm partnerships and featured listings
2. Add email alerts for new cases matching user profiles
3. Expand scraper to cover more sources
4. Consider NZ expansion (similar legal system)

## Financials

### Costs (Monthly)
| Item | Free Tier | Scaled |
|------|-----------|--------|
| Hosting (Render) | $0 | $25–50 |
| Domain | $1.50 | $1.50 |
| Stripe fees | 2.9% + 30c per txn | 2.9% + 30c |
| Total fixed | ~$2 | ~$52 |

### Revenue Projections
| Metric | Month 1 | Month 3 | Month 6 |
|--------|---------|---------|---------|
| Users | 200 | 2,000 | 10,000 |
| Paid subscribers | 10 | 150 | 750 |
| MRR (subscriptions) | $50 | $750 | $3,750 |
| Law firm listings | $0 | $500 | $2,000 |
| **Total MRR** | **$50** | **$1,250** | **$5,750** |

### Key Metrics to Track
- Signup → quiz completion rate
- Quiz → eligibility check conversion
- Free → paid conversion rate
- Claim portal click-through rate (proves value)
- Churn rate

## Competitive Advantage
- **First mover** in AU class action consumer tools
- **Automated scraping** keeps data fresh without manual work
- **SEO moat** — first to rank for "[company] class action eligibility" searches
- **Network effect** — more users = more valuable to law firms = more revenue

## Steps to Go Live TODAY

### 1. Create Stripe Account (10 minutes)
- Go to https://dashboard.stripe.com/register
- Create two Products:
  - "SettleCare Premium Monthly" → $4.99/month recurring
  - "SettleCare Premium Yearly" → $29.99/year recurring
- Copy the `price_xxx` IDs into your `.env` file
- Copy your `sk_test_xxx` secret key into `.env`
- Set up a webhook endpoint pointing to `https://YOUR-API.onrender.com/api/billing/webhook`
  - Listen for: `checkout.session.completed`, `customer.subscription.deleted`

### 2. Deploy Backend to Render (15 minutes)
- Push code to GitHub
- Go to https://render.com → New Web Service
- Connect repo, set root to `backend/`
- Build: `pip install -r requirements.txt`
- Start: `gunicorn app:app --bind 0.0.0.0:$PORT --workers 2`
- Add env vars from `.env.example`
- Add a PostgreSQL database (free tier)

### 3. Deploy Frontend to Render (10 minutes)
- New Static Site → connect same repo
- Root: `frontend/`, Build: `npm install && npm run build`, Publish: `build`
- Add env var: `REACT_APP_API_URL=https://YOUR-API.onrender.com`

### 4. Custom Domain (Optional, $12/year)
- Buy `settlecare.com.au` from VentraIP or Namecheap
- Point DNS to Render

### 5. Seed Production Database
- Run `python scraper.py` on the deployed backend (or use the admin endpoint)
- Run `python auto_scraper.py` to pull live cases

### 6. Launch
- Post everywhere (Reddit, Facebook, Twitter/X)
- Monitor Stripe dashboard for first conversions
