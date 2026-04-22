"""
Settlemate AU - Auto Scraper

Crawls Australian law firm websites to find class actions,
extracts case details, and auto-generates eligibility questions.

Usage:
  python auto_scraper.py                        # Run all scrapers
  python auto_scraper.py --source=mb            # Run specific source
  python auto_scraper.py --clean-existing       # Clean boilerplate from DB records (no network)
  python auto_scraper.py --rescrape             # Re-fetch & update all existing records
  python auto_scraper.py --rescrape --source=mb # Re-fetch only Maurice Blackburn records

Sources:
  mb  = Maurice Blackburn
  sg  = Slater and Gordon
  sh  = Shine Lawyers
  pfm = Phi Finney McDonald
  bl  = Bannister Law
  al  = Adero Law
"""

import re
import sys
import time
import logging
from datetime import datetime
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

from app import app
from models import db, ClassAction, EligibilityQuestion, ScraperLog

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-AU,en;q=0.9",
}

SESSION = requests.Session()
SESSION.headers.update(HEADERS)


def fetch(url, timeout=20):
    """Fetch a URL with error handling."""
    try:
        r = SESSION.get(url, timeout=timeout)
        r.raise_for_status()
        return BeautifulSoup(r.text, "html.parser")
    except Exception as e:
        logger.warning(f"Failed to fetch {url}: {e}")
        return None


# ─── QUESTION AUTO-GENERATION ────────────────────────────────────────────────

def generate_questions(case_name, defendant, description, eligibility_criteria):
    """Auto-generate eligibility questions from case details."""
    text = f"{description or ''} {eligibility_criteria or ''}".lower()
    defendant_short = defendant.split("(")[0].split("Limited")[0].split("Ltd")[0].split("Pty")[0].split("Inc")[0].split("Corporation")[0].strip()
    questions = []

    # 1. Always ask about being Australian
    questions.append(("Are you an Australian resident?", True))

    # 2. Customer/user relationship
    date_range = extract_date_range(text)
    if any(w in text for w in ["customer", "member", "user", "account holder", "client", "subscriber", "policyholder"]):
        period = f" between {date_range}" if date_range else ""
        rel_word = "customer"
        for w in ["member", "policyholder", "account holder", "subscriber"]:
            if w in text:
                rel_word = w
                break
        questions.append((
            f"Were you a {defendant_short} {rel_word}{period}?",
            True,
        ))
    elif any(w in text for w in ["owner", "purchased", "bought", "vehicle"]):
        questions.append((
            f"Did you purchase or own a product from {defendant_short}?",
            True,
        ))
    elif any(w in text for w in ["employee", "employed", "worker", "staff"]):
        period = f" between {date_range}" if date_range else ""
        questions.append((
            f"Were you employed by {defendant_short}{period}?",
            True,
        ))
    elif any(w in text for w in ["shareholder", "investor", "share"]):
        questions.append((
            f"Did you hold shares in or invest in {defendant_short}?",
            True,
        ))

    # 3. Harm-specific questions
    if any(w in text for w in ["data breach", "cyber", "hack", "personal information", "privacy"]):
        questions.append((
            "Was your personal information compromised or exposed in a data breach?",
            True,
        ))
        questions.append((
            "Did you experience negative consequences such as identity fraud, distress, or the need to replace identity documents?",
            True,
        ))
    elif any(w in text for w in ["fee", "overcharg", "underpay", "charge"]):
        questions.append((
            "Were you charged fees that you believe were excessive, unauthorised, or for services not received?",
            True,
        ))
    elif any(w in text for w in ["misleading", "deceptive", "false", "misrepresent"]):
        questions.append((
            "Were you misled by advertising, representations, or information provided by the company?",
            True,
        ))
    elif any(w in text for w in ["defect", "faulty", "malfunction", "recall"]):
        questions.append((
            "Did you experience product defects, malfunctions, or safety issues?",
            True,
        ))
        questions.append((
            "Did you incur costs for repairs, replacements, or suffer loss due to the defect?",
            True,
        ))
    elif any(w in text for w in ["cancel", "refund", "flight", "travel"]):
        questions.append((
            "Did you suffer financial loss or significant inconvenience as a result?",
            True,
        ))
    elif any(w in text for w in ["underpaid", "wage", "overtime", "entitlement"]):
        questions.append((
            "Were you paid less than your entitlements including overtime, penalty rates, or allowances?",
            True,
        ))
    elif any(w in text for w in ["insurance", "superannuation", "super fund"]):
        questions.append((
            "Were you charged for insurance or services you did not request or use?",
            True,
        ))

    # 4. Financial loss question (if not already covered)
    if len(questions) < 4 and any(w in text for w in ["loss", "damage", "cost", "expense", "harm"]):
        questions.append((
            "Did you suffer financial loss, out-of-pocket expenses, or other harm as a result?",
            True,
        ))

    # Ensure we have at least 3 questions
    if len(questions) < 3:
        questions.append((
            f"Were you directly affected by the conduct described in this class action against {defendant_short}?",
            True,
        ))

    return questions[:5]  # Cap at 5 questions


def extract_date_range(text):
    """Try to extract a date range like '2015 and 2022' or '2017 to 2023' from text."""
    patterns = [
        r'between\s+(?:january|february|march|april|may|june|july|august|september|october|november|december)?\s*(\d{4})\s+and\s+(?:january|february|march|april|may|june|july|august|september|october|november|december)?\s*(\d{4})',
        r'from\s+(\d{4})\s+to\s+(\d{4})',
        r'between\s+(\d{4})\s+and\s+(\d{4})',
        r'(\d{4})\s*[-–]\s*(\d{4})',
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            return f"{m.group(1)} and {m.group(2)}"
    return None


def extract_deadline(text):
    """Try to extract a claim deadline from text."""
    patterns = [
        r'deadline[:\s]+(\d{1,2})\s+(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{4})',
        r'(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{1,2}),?\s+(\d{4})',
        r'by\s+(\d{1,2})\s+(january|february|march|april|may|june|july|august|september|october|november|december)\s+(\d{4})',
    ]
    months = {
        "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
        "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    }
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            groups = m.groups()
            try:
                if groups[1].lower() in months:
                    return datetime(int(groups[2]), months[groups[1].lower()], int(groups[0]))
                elif groups[0].lower() in months:
                    return datetime(int(groups[2]), months[groups[0].lower()], int(groups[1]))
            except (ValueError, KeyError):
                pass
    return None


# ─── SOURCE SCRAPERS ─────────────────────────────────────────────────────────

def scrape_maurice_blackburn():
    """Scrape Maurice Blackburn class actions."""
    cases = []
    base = "https://www.mauriceblackburn.com.au"
    url = f"{base}/class-actions/current-class-actions"

    soup = fetch(url)
    if not soup:
        return cases

    # Look for case listing links
    for link in soup.select("a[href*='/class-actions/']"):
        href = link.get("href", "")
        title = link.get_text(strip=True)
        if not title or len(title) < 10 or "current" in href.lower() and href.endswith("current-class-actions"):
            continue
        if "/class-actions/" in href and href != "/class-actions/current-class-actions":
            full_url = urljoin(base, href)
            case = scrape_case_page(full_url, title, "Maurice Blackburn Lawyers", "1800 810 812", base)
            if case:
                cases.append(case)

    logger.info(f"Maurice Blackburn: found {len(cases)} cases")
    return cases


def scrape_slater_gordon():
    """Scrape Slater and Gordon class actions."""
    cases = []
    base = "https://www.slatergordon.com.au"
    url = f"{base}/class-actions/current-class-actions"

    soup = fetch(url)
    if not soup:
        return cases

    for link in soup.select("a[href*='/class-actions/']"):
        href = link.get("href", "")
        title = link.get_text(strip=True)
        if not title or len(title) < 10:
            continue
        if "/current-class-actions/" in href and not href.endswith("current-class-actions"):
            full_url = urljoin(base, href)
            case = scrape_case_page(full_url, title, "Slater and Gordon", "1800 555 777", base)
            if case:
                cases.append(case)

    logger.info(f"Slater and Gordon: found {len(cases)} cases")
    return cases


def scrape_shine_lawyers():
    """Scrape Shine Lawyers class actions."""
    cases = []
    base = "https://www.shine.com.au"
    url = f"{base}/class-actions"

    soup = fetch(url)
    if not soup:
        return cases

    for link in soup.select("a[href*='/class-actions/']"):
        href = link.get("href", "")
        title = link.get_text(strip=True)
        if not title or len(title) < 10:
            continue
        if href != "/class-actions" and href != "/class-actions/":
            full_url = urljoin(base, href)
            case = scrape_case_page(full_url, title, "Shine Lawyers", "1800 870 730", base)
            if case:
                cases.append(case)

    logger.info(f"Shine Lawyers: found {len(cases)} cases")
    return cases


def scrape_phi_finney():
    """Scrape Phi Finney McDonald class actions."""
    cases = []
    base = "https://www.phifinneymcdonald.com"
    url = f"{base}/current-claims"

    soup = fetch(url)
    if not soup:
        return cases

    for link in soup.select("a[href*='/current-claims/']"):
        href = link.get("href", "")
        title = link.get_text(strip=True)
        if not title or len(title) < 8:
            continue
        if href != "/current-claims" and href != "/current-claims/":
            full_url = urljoin(base, href)
            case = scrape_case_page(full_url, title, "Phi Finney McDonald", "(03) 9134 7100", base)
            if case:
                cases.append(case)

    logger.info(f"Phi Finney McDonald: found {len(cases)} cases")
    return cases


def scrape_bannister_law():
    """Scrape Bannister Law class actions."""
    cases = []
    base = "https://www.bannisterlaw.com.au"
    url = f"{base}/class-actions"

    soup = fetch(url)
    if not soup:
        return cases

    for link in soup.select("a[href*='/class-actions/']"):
        href = link.get("href", "")
        title = link.get_text(strip=True)
        if not title or len(title) < 8:
            continue
        if href != "/class-actions" and href != "/class-actions/":
            full_url = urljoin(base, href)
            case = scrape_case_page(full_url, title, "Bannister Law", "1800 011 581", base)
            if case:
                cases.append(case)

    logger.info(f"Bannister Law: found {len(cases)} cases")
    return cases


def scrape_adero_law():
    """Scrape Adero Law class actions."""
    cases = []
    base = "https://www.aderolaw.com.au"
    url = f"{base}/class-actions"

    soup = fetch(url)
    if not soup:
        return cases

    for link in soup.select("a[href*='/class-actions/']"):
        href = link.get("href", "")
        title = link.get_text(strip=True)
        if not title or len(title) < 8:
            continue
        if href != "/class-actions" and href != "/class-actions/":
            full_url = urljoin(base, href)
            case = scrape_case_page(full_url, title, "Adero Law", "(07) 3088 7937", base)
            if case:
                cases.append(case)

    logger.info(f"Adero Law: found {len(cases)} cases")
    return cases


def detect_court(body_text, file_number):
    """Detect the court and state from body text and file number."""
    text = (body_text or "").lower()
    fn = (file_number or "").upper()

    # File number prefixes map to states
    prefix_map = {
        "NSD": "Federal Court of Australia (NSW)",
        "VID": "Federal Court of Australia (VIC)",
        "QUD": "Federal Court of Australia (QLD)",
        "WAD": "Federal Court of Australia (WA)",
        "SAD": "Federal Court of Australia (SA)",
        "ACD": "Federal Court of Australia (ACT)",
        "TAD": "Federal Court of Australia (TAS)",
        "NTD": "Federal Court of Australia (NT)",
    }
    for prefix, court in prefix_map.items():
        if fn.startswith(prefix):
            return court

    # Try to detect from body text
    if "supreme court" in text:
        if "new south wales" in text or "nsw" in text: return "Supreme Court of NSW"
        if "victoria" in text or " vic " in text: return "Supreme Court of VIC"
        if "queensland" in text or " qld " in text: return "Supreme Court of QLD"
        if "western australia" in text: return "Supreme Court of WA"
        if "south australia" in text: return "Supreme Court of SA"
        if "tasmania" in text: return "Supreme Court of TAS"
        return "Supreme Court"
    if "high court" in text: return "High Court of Australia"
    if "nsw" in text or "new south wales" in text or "sydney" in text: return "Federal Court of Australia (NSW)"
    if "victoria" in text or "melbourne" in text: return "Federal Court of Australia (VIC)"
    if "queensland" in text or "brisbane" in text: return "Federal Court of Australia (QLD)"
    if "western australia" in text or "perth" in text: return "Federal Court of Australia (WA)"
    if "south australia" in text or "adelaide" in text: return "Federal Court of Australia (SA)"
    if "tasmania" in text or "hobart" in text: return "Federal Court of Australia (TAS)"
    if "canberra" in text or " act " in text: return "Federal Court of Australia (ACT)"
    if "darwin" in text or "northern territory" in text: return "Federal Court of Australia (NT)"
    return "Federal Court of Australia"


def scrape_case_page(url, fallback_title, law_firm, law_firm_contact, law_firm_website):
    """Scrape an individual case page for details."""
    soup = fetch(url)
    if not soup:
        return None

    # Extract main content
    title = fallback_title
    # Try to get a better title from the page
    h1 = soup.find("h1")
    if h1:
        title = h1.get_text(strip=True)

    # Get page text for extraction
    # Remove nav, footer, scripts
    for tag in soup.select("nav, footer, script, style, header"):
        tag.decompose()

    body_text = soup.get_text(" ", strip=True)

    # Extract paragraphs for description
    paragraphs = []
    for p in soup.find_all("p"):
        text = p.get_text(strip=True)
        if len(text) > 50:
            paragraphs.append(text)

    description = " ".join(paragraphs[:3]) if paragraphs else body_text[:500]
    description = clean_description(description)

    # Try to find defendant from title
    defendant = extract_defendant(title, body_text)
    if not defendant:
        return None  # Can't create a case without a defendant

    # Try to find file number
    file_number = extract_file_number(body_text)
    if not file_number:
        # Generate a synthetic one from the URL
        slug = url.rstrip("/").split("/")[-1]
        file_number = f"AUTO-{slug[:30].upper()}"

    # Extract eligibility criteria
    eligibility = extract_eligibility(soup, body_text)
    if eligibility:
        eligibility = clean_description(eligibility)

    # Extract deadline
    deadline = extract_deadline(body_text.lower())

    # Extract settlement amount
    settlement = extract_settlement(body_text)

    # Determine status
    status = determine_status(body_text)

    # Build keywords from title and description
    keywords = ",".join(extract_keywords(title, description, defendant))

    case = {
        "case_name": clean_title(title),
        "file_number": file_number,
        "defendant": defendant,
        "applicant": None,
        "court": detect_court(body_text, file_number),
        "status": status,
        "description": description[:2000],
        "eligibility_criteria": eligibility[:1000] if eligibility else None,
        "claim_deadline": deadline,
        "settlement_amount": settlement,
        "law_firm": law_firm,
        "law_firm_contact": law_firm_contact,
        "law_firm_website": law_firm_website,
        "claim_portal_url": url,
        "keywords": keywords,
        "source_url": url,
    }

    return case


# ─── EXTRACTION HELPERS ──────────────────────────────────────────────────────

def extract_defendant(title, body_text):
    """Extract defendant company name from title or body."""
    # Common pattern: "X v Y" or "X vs Y"
    m = re.search(r'v[s]?\s+(.+?)(?:\s*[-–|]|\s*class\s*action|$)', title, re.IGNORECASE)
    if m:
        defendant = m.group(1).strip()
        # Clean up
        defendant = re.sub(r'\s*class\s*action.*', '', defendant, flags=re.IGNORECASE).strip()
        if len(defendant) > 3:
            return defendant

    # Try to find company names in title
    # Look for words ending in Ltd, Limited, Inc, Pty, Corporation, Group, Bank
    m = re.search(
        r'([\w\s]+(?:Ltd|Limited|Inc|Pty|Corporation|Group|Bank|Insurance|Airlines|Airways|Telstra|Optus|Woolworths|Toyota|Qantas)[\w\s]*)',
        title, re.IGNORECASE
    )
    if m:
        return m.group(1).strip()

    # Try from body text first paragraph
    m = re.search(
        r'against\s+([\w\s]+(?:Ltd|Limited|Inc|Pty|Corporation|Group|Bank)\b[\w\s]*)',
        body_text[:1000], re.IGNORECASE
    )
    if m:
        return m.group(1).strip()

    # Fall back to title cleanup
    title_clean = re.sub(r'class\s*action.*', '', title, flags=re.IGNORECASE).strip()
    if len(title_clean) > 5:
        return title_clean

    return None


def extract_file_number(text):
    """Extract court file number like NSD 1234/2024 or VID 567/2024."""
    m = re.search(r'((?:NSD|VID|QUD|WAD|SAD|ACD)\s*\d+/\d{4})', text)
    if m:
        return m.group(1)
    # Also try "No." pattern
    m = re.search(r'(?:No\.?|File)\s*([\w]+\d+/\d{4})', text)
    if m:
        return m.group(1)
    return None


def extract_eligibility(soup, body_text):
    """Extract eligibility criteria section."""
    # Look for headings containing "eligib" or "who can"
    for heading in soup.find_all(["h2", "h3", "h4", "strong"]):
        text = heading.get_text(strip=True).lower()
        if any(w in text for w in ["eligib", "who can", "who is", "are you", "qualify", "affected"]):
            # Get the next sibling paragraphs
            content = []
            for sib in heading.find_next_siblings():
                if sib.name in ["h2", "h3", "h4"]:
                    break
                t = sib.get_text(strip=True)
                if t:
                    content.append(t)
            if content:
                return " ".join(content[:3])

    # Try regex on body
    m = re.search(
        r'(?:eligible|eligibility|who can|you may be eligible)[:\s]+(.{100,500}?)(?:\.|$)',
        body_text, re.IGNORECASE | re.DOTALL
    )
    if m:
        return m.group(1).strip()

    return None


def extract_settlement(text):
    """Extract settlement amount."""
    patterns = [
        r'\$\s*([\d,.]+)\s*(?:million|m)\b',
        r'settlement\s+of\s+\$\s*([\d,.]+)',
        r'\$\s*([\d,]+(?:\.\d+)?)\s*(?:AUD|aud)',
    ]
    for pat in patterns:
        m = re.search(pat, text, re.IGNORECASE)
        if m:
            amount = m.group(1).replace(",", "")
            try:
                num = float(amount)
                if "million" in text[m.start():m.end()+20].lower() or "m" in text[m.start():m.end()+5].lower():
                    return f"${num:,.0f},000,000 AUD"
                elif num >= 1_000_000:
                    return f"${num:,.0f} AUD"
                else:
                    return f"${num:,.0f} AUD"
            except ValueError:
                pass
    return None


def determine_status(text):
    """Determine case status from body text."""
    text_lower = text.lower()
    if "settlement approved" in text_lower or "settlement has been approved" in text_lower:
        return "Settlement Approved"
    if "settlement pending" in text_lower or "proposed settlement" in text_lower or "awaiting approval" in text_lower:
        return "Settlement Pending"
    if "closed" in text_lower and "case is closed" in text_lower:
        return "Closed"
    if "settled" in text_lower:
        return "Settlement Approved"
    return "Active"


def extract_keywords(title, description, defendant):
    """Generate search keywords from case content."""
    stopwords = {"the", "a", "an", "and", "or", "of", "in", "to", "for", "is", "was", "were",
                 "are", "been", "be", "has", "have", "had", "that", "this", "with", "from",
                 "by", "on", "at", "their", "its", "they", "who", "which", "class", "action"}
    words = set()
    for text in [title, description[:300], defendant]:
        if text:
            for word in re.findall(r'\b[a-zA-Z]{3,}\b', text.lower()):
                if word not in stopwords:
                    words.add(word)
    return list(words)[:15]


def clean_title(title):
    """Clean up a case title."""
    title = re.sub(r'\s+', ' ', title).strip()
    # Remove trailing "| Firm Name" etc
    title = re.sub(r'\s*[|–-]\s*(?:Maurice Blackburn|Slater.Gordon|Shine Lawyers?|Bannister Law|Adero Law|Phi Finney).*$', '', title, flags=re.IGNORECASE)
    return title[:300]


# Boilerplate phrases that leak into scraped descriptions from website chrome.
# Each entry is compiled as a case-insensitive regex.
_BOILERPLATE_PATTERNS = [
    # Browser compatibility warnings
    r'your?\s+web\s*browser\s+may\s+not\s+be\s+(?:properly\s+)?supported[\s\S]{0,200}?(?:Chrome|Safari|Firefox|Edge|Internet Explorer)[\w\s,."\']*\.?',
    r'(?:please\s+)?(?:upgrade|update)\s+your\s+(?:web\s*)?browser[\w\s,."\']*\.?',
    r'(?:this\s+(?:site|website)\s+)?(?:requires?|works?\s+best\s+(?:with|in)|is\s+(?:best\s+viewed|optimised?)\s+(?:in|with))[\s\S]{0,150}?(?:Chrome|Safari|Firefox|Edge|Internet Explorer)[\w\s,."\']*\.?',
    r'for\s+(?:the\s+)?best\s+(?:experience|results?)[\s\S]{0,150}?(?:Chrome|Safari|Firefox|Edge|latest\s+version)[\w\s,."\']*\.?',
    r'to\s+use\s+this\s+site\s+and\s+all\s+its\s+features[\s\S]{0,200}?(?:Chrome|Safari|Firefox|Edge)[\w\s,."\']*\.?',
    # Cookie / privacy banners
    r'(?:we|this\s+(?:site|website))\s+uses?\s+cookies[\s\S]{0,300}?(?:accept|agree|consent|privacy\s+policy|learn\s+more|cookie\s+policy)[\w\s,."\']*\.?',
    r'by\s+(?:continuing|using)\s+(?:to\s+(?:use|browse)\s+)?(?:this|our)\s+(?:site|website)[\s\S]{0,200}?(?:cookies?|privacy)[\w\s,."\']*\.?',
    # Newsletter / subscription prompts
    r'(?:sign\s+up|subscribe)\s+(?:to|for)\s+(?:our|the)\s+(?:newsletter|mailing\s+list|updates)[\s\S]{0,200}?(?:email|submit|sign\s+up)[\w\s,."\']*\.?',
    # Skip-to-content / accessibility boilerplate
    r'skip\s+to\s+(?:main\s+)?content\.?',
    # Generic "JavaScript required" banners
    r'(?:please\s+)?enable\s+javascript[\s\S]{0,150}?(?:experience|features?|functionality)[\w\s,."\']*\.?',
    r'javascript\s+(?:is\s+)?(?:required|must\s+be\s+enabled)[\s\S]{0,150}?\.?',
    # Social sharing / follow-us blocks that sometimes sneak in
    r'(?:follow|connect\s+with|find)\s+us\s+on\s+(?:facebook|twitter|linkedin|instagram|youtube)[\w\s,|/"\']*\.?',
    r'share\s+(?:this|on)\s*:\s*(?:facebook|twitter|linkedin|email)[\w\s,|/"\']*\.?',
    # Copyright / footer lines
    r'(?:copyright|\u00a9)\s*\d{4}[\s\S]{0,100}?(?:all\s+rights\s+reserved|ABN|ACN)[\w\s,./"\']*\.?',
]
_BOILERPLATE_RE = [re.compile(p, re.IGNORECASE) for p in _BOILERPLATE_PATTERNS]


def clean_description(text):
    """Remove common website boilerplate (browser warnings, cookie notices, etc.) from scraped text."""
    if not text:
        return text

    for pattern in _BOILERPLATE_RE:
        text = pattern.sub('', text)

    # Collapse whitespace left behind by removals
    text = re.sub(r'[ \t]+', ' ', text)
    text = re.sub(r'\n\s*\n', '\n', text)
    text = text.strip()

    return text


# ─── MAIN ORCHESTRATOR ───────────────────────────────────────────────────────

SOURCES = {
    "mb": ("Maurice Blackburn", scrape_maurice_blackburn),
    "sg": ("Slater and Gordon", scrape_slater_gordon),
    "sh": ("Shine Lawyers", scrape_shine_lawyers),
    "pfm": ("Phi Finney McDonald", scrape_phi_finney),
    "bl": ("Bannister Law", scrape_bannister_law),
    "al": ("Adero Law", scrape_adero_law),
}


def save_cases(cases, source_name):
    """Save scraped cases to database, skipping duplicates."""
    added = 0
    updated = 0
    skipped = 0

    for case_data in cases:
        file_num = case_data["file_number"]

        # Check for duplicate by file_number or by similar case_name + defendant
        existing = ClassAction.query.filter_by(file_number=file_num).first()
        if not existing:
            # Also check by defendant + similar name
            existing = ClassAction.query.filter(
                ClassAction.defendant == case_data["defendant"],
                ClassAction.case_name.ilike(f"%{case_data['case_name'][:30]}%"),
            ).first()

        if existing:
            # Update if we have more info or if existing text contains boilerplate
            changed = False
            for key in ["description", "eligibility_criteria", "settlement_amount", "claim_deadline"]:
                new_val = case_data.get(key)
                old_val = getattr(existing, key)
                if new_val and not old_val:
                    # Field was empty, fill it in
                    setattr(existing, key, new_val)
                    changed = True
                elif key in ("description", "eligibility_criteria") and new_val and old_val:
                    # Re-clean existing text; replace if the cleaned version differs
                    cleaned_old = clean_description(old_val)
                    if cleaned_old != old_val or new_val != old_val:
                        setattr(existing, key, new_val)  # new_val is already cleaned
                        changed = True
            if changed:
                updated += 1
            else:
                skipped += 1
            continue

        # Create new case
        new_case = ClassAction(**case_data)
        db.session.add(new_case)
        db.session.flush()

        # Generate and save eligibility questions
        questions = generate_questions(
            case_data["case_name"],
            case_data["defendant"],
            case_data.get("description", ""),
            case_data.get("eligibility_criteria", ""),
        )
        for i, (q_text, req_answer) in enumerate(questions):
            q = EligibilityQuestion(
                class_action_id=new_case.id,
                question_text=q_text,
                question_order=i,
                required_answer=req_answer,
            )
            db.session.add(q)

        added += 1

    db.session.commit()
    return added, updated, skipped


def clean_existing_records():
    """Clean boilerplate from descriptions/eligibility on all existing records in the DB.

    This does NOT re-fetch from source websites -- it only applies the
    clean_description() filter to text already stored.  Useful as a one-time
    migration after the cleaning rules are added or updated.

    Returns (cleaned_count, total_count).
    """
    with app.app_context():
        cases = ClassAction.query.all()
        cleaned = 0
        for case in cases:
            changed = False
            for field in ("description", "eligibility_criteria"):
                old = getattr(case, field)
                if old:
                    new = clean_description(old)
                    if new != old:
                        setattr(case, field, new)
                        changed = True
            if changed:
                cleaned += 1
        db.session.commit()
        logger.info(f"Cleaned {cleaned}/{len(cases)} existing records")
        return cleaned, len(cases)


def rescrape_existing(source_keys=None):
    """Re-fetch every existing record from its source_url and update the DB.

    This is the 'hard refresh' option -- it hits the original page again,
    re-extracts the description (now with boilerplate cleaning), and updates
    the stored record.  Questions are NOT regenerated to avoid losing user
    answers tied to existing question IDs.

    Returns a summary dict.
    """
    with app.app_context():
        query = ClassAction.query.filter(ClassAction.source_url.isnot(None))
        if source_keys:
            # Filter to records whose law_firm matches the requested sources
            firm_names = [SOURCES[k][0] for k in source_keys if k in SOURCES]
            if firm_names:
                query = query.filter(ClassAction.law_firm.in_(firm_names))

        cases = query.all()
        refreshed = 0
        failed = 0

        for case in cases:
            soup = fetch(case.source_url)
            if not soup:
                failed += 1
                continue

            # Strip nav/footer/scripts just like scrape_case_page does
            for tag in soup.select("nav, footer, script, style, header"):
                tag.decompose()

            body_text = soup.get_text(" ", strip=True)

            # Re-extract description
            paragraphs = []
            for p in soup.find_all("p"):
                text = p.get_text(strip=True)
                if len(text) > 50:
                    paragraphs.append(text)

            new_desc = " ".join(paragraphs[:3]) if paragraphs else body_text[:500]
            new_desc = clean_description(new_desc)

            # Re-extract eligibility
            new_elig = extract_eligibility(soup, body_text)
            if new_elig:
                new_elig = clean_description(new_elig)

            changed = False
            if new_desc and new_desc != case.description:
                case.description = new_desc[:2000]
                changed = True
            if new_elig and new_elig != case.eligibility_criteria:
                case.eligibility_criteria = new_elig[:1000]
                changed = True

            # Also refresh status and settlement while we are here
            new_status = determine_status(body_text)
            if new_status != case.status:
                case.status = new_status
                changed = True

            new_settlement = extract_settlement(body_text)
            if new_settlement and new_settlement != case.settlement_amount:
                case.settlement_amount = new_settlement
                changed = True

            if changed:
                refreshed += 1

            time.sleep(1)  # Be polite

        db.session.commit()
        logger.info(f"Re-scraped {refreshed}/{len(cases)} records ({failed} fetch failures)")
        return {
            "total": len(cases),
            "refreshed": refreshed,
            "failed": failed,
        }


def run_auto_scraper(source_keys=None):
    """Run the auto-scraper for specified sources (or all)."""
    if source_keys is None:
        source_keys = list(SOURCES.keys())

    start = time.time()
    total_added = 0
    total_updated = 0
    total_found = 0
    errors = []

    with app.app_context():
        for key in source_keys:
            if key not in SOURCES:
                logger.warning(f"Unknown source: {key}")
                continue

            name, scraper_fn = SOURCES[key]
            logger.info(f"Scraping {name}...")

            try:
                cases = scraper_fn()
                total_found += len(cases)

                if cases:
                    added, updated, skipped = save_cases(cases, name)
                    total_added += added
                    total_updated += updated
                    logger.info(f"  {name}: {len(cases)} found, {added} added, {updated} updated, {skipped} skipped")
                else:
                    logger.info(f"  {name}: no cases found")
            except Exception as e:
                logger.error(f"  {name} error: {e}")
                errors.append(f"{name}: {str(e)}")

            # Be polite between sources
            time.sleep(2)

        duration = time.time() - start

        # Log the run
        log = ScraperLog(
            source=",".join(source_keys),
            status="success" if not errors else "partial",
            cases_found=total_found,
            cases_added=total_added,
            cases_updated=total_updated,
            error_message="; ".join(errors) if errors else None,
            duration_seconds=round(duration, 2),
        )
        db.session.add(log)
        db.session.commit()

        total_db = ClassAction.query.count()
        total_q = EligibilityQuestion.query.count()
        logger.info(f"Auto-scraper complete in {duration:.1f}s")
        logger.info(f"  Found: {total_found}, Added: {total_added}, Updated: {total_updated}")
        logger.info(f"  Database total: {total_db} cases, {total_q} questions")
        if errors:
            logger.warning(f"  Errors: {'; '.join(errors)}")

        return {
            "found": total_found,
            "added": total_added,
            "updated": total_updated,
            "errors": errors,
            "duration": round(duration, 2),
            "total_cases": total_db,
            "total_questions": total_q,
        }


if __name__ == "__main__":
    source_keys = None
    do_rescrape = False
    do_clean = False

    for arg in sys.argv[1:]:
        if arg.startswith("--source="):
            source_keys = arg.split("=")[1].split(",")
        elif arg == "--rescrape":
            do_rescrape = True
        elif arg == "--clean-existing":
            do_clean = True

    if do_clean:
        # Only clean boilerplate from existing DB records (no network requests)
        cleaned, total = clean_existing_records()
        print(f"Cleaned {cleaned} of {total} existing records")
    elif do_rescrape:
        # Re-fetch from source URLs and update existing records
        result = rescrape_existing(source_keys)
        print(f"Re-scraped: {result['refreshed']}/{result['total']} updated, {result['failed']} failures")
    else:
        run_auto_scraper(source_keys)
