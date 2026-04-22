# Settlemate Australia - API Documentation

**Base URL:** `http://localhost:5000` (dev) | `https://api-settlemate-au.railway.app` (prod)

---

## Endpoints

### Health Check

```
GET /api/health
```

**Response:**
```json
{ "status": "healthy", "timestamp": "2024-01-15T10:30:00" }
```

---

### List Class Actions

```
GET /api/class-actions
```

**Query Parameters:**

| Param       | Type   | Default     | Description                          |
|-------------|--------|-------------|--------------------------------------|
| search      | string | —           | Search case name, defendant, keywords |
| status      | string | —           | Filter: Active, Settlement Pending, Settlement Approved, Closed |
| court       | string | —           | Filter by court name (partial match) |
| sort_by     | string | updated_at  | Sort field: case_name, defendant, status, claim_deadline, updated_at, created_at |
| sort_order  | string | desc        | asc or desc                          |
| page        | int    | 1           | Page number                          |
| per_page    | int    | 20          | Results per page (max 100)           |

**Response:**
```json
{
  "cases": [
    {
      "id": 1,
      "case_name": "Thompson v Meta Platforms, Inc.",
      "file_number": "NSD 1234/2024",
      "defendant": "Meta Platforms, Inc.",
      "applicant": "Sarah Thompson",
      "court": "Federal Court of Australia",
      "status": "Settlement Pending",
      "description": "...",
      "eligibility_criteria": "...",
      "claim_deadline": "2025-12-31T00:00:00",
      "settlement_amount": "$50,000,000 AUD",
      "law_firm": "Maurice Blackburn Lawyers",
      "law_firm_contact": "1800 810 812",
      "law_firm_website": "https://www.mauriceblackburn.com.au",
      "claim_portal_url": "https://...",
      "keywords": "facebook,meta,privacy,data",
      "source_url": "https://...",
      "created_at": "2024-01-15T10:00:00",
      "updated_at": "2024-01-15T10:00:00"
    }
  ],
  "total": 6,
  "page": 1,
  "per_page": 20,
  "pages": 1
}
```

**Cache:** 1 hour TTL

---

### Get Single Case

```
GET /api/class-actions/<id>
```

**Response:** Single case object (same schema as above)

**Error (404):**
```json
{ "error": "Case not found" }
```

---

### Check Eligibility

```
POST /api/check-eligibility
```

**Rate Limit:** 30 requests/hour

**Request Body:**
```json
{
  "company": "Westpac",
  "products": ["savings account", "transaction account"],
  "keywords": ["fees", "overcharging"],
  "user_email": "optional@email.com"
}
```

At least one of `company`, `products`, or `keywords` is required.

**Response:**
```json
{
  "matches": [
    {
      "id": 2,
      "case_name": "Williams v Westpac Banking Corporation",
      "match_score": 80,
      "...": "full case object"
    }
  ],
  "total_matches": 1
}
```

**Scoring:**
- Company in defendant: +80 points (50 text + 30 defendant)
- Product in case text: +20 each
- Keyword in case text: +10 each

---

### List Courts

```
GET /api/courts
```

**Response:**
```json
{
  "courts": [
    { "name": "Federal Court of Australia", "case_count": 6 }
  ]
}
```

---

### Urgent Deadlines

```
GET /api/deadlines/urgent?days=30
```

**Query Parameters:**

| Param | Type | Default | Description                |
|-------|------|---------|----------------------------|
| days  | int  | 30      | Days ahead to check        |

**Response:**
```json
{
  "cases": [ "...cases with upcoming deadlines..." ],
  "total": 2
}
```

---

### Statistics

```
GET /api/stats
```

**Response:**
```json
{
  "total_cases": 6,
  "active_cases": 3,
  "settled_cases": 2,
  "urgent_deadlines": 1
}
```

---

## Error Responses

All errors return JSON:

| Code | Description                    |
|------|--------------------------------|
| 400  | Bad request / missing fields   |
| 404  | Resource not found             |
| 429  | Rate limit exceeded            |
| 500  | Internal server error          |

```json
{ "error": "Description of error" }
```

## Rate Limiting

- General: 100 requests/hour per IP
- Eligibility check: 30 requests/hour per IP
- Health check: exempt
