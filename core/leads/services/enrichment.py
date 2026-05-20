"""
enrichment.py

Scrape company website content and synthesise it into a structured business analysis
using Groq (LLM). Returns a dict matching the keys consumed by the PDF generator.
"""

import json
import re
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup
from groq import Groq

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    )
}

# Conservative timeout so the enrichment step doesn't block the whole request
# indefinitely.
TIMEOUT = 10


def _scrape(url: str) -> str:
    """Fetch and extract main text from a web page.

    Notes:
    - Removes scripts/styles and common non-content sections.
    - Truncates to a maximum size to keep the downstream LLM prompt bounded.
    - Failures are swallowed and result in an empty string (best-effort enrichment).
    """

    try:
        r = requests.get(
            url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True
        )
        r.raise_for_status()

        soup = BeautifulSoup(r.text, "lxml")
        for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
            tag.decompose()

        text = soup.get_text(" ", strip=True)
        return re.sub(r"\s{2,}", " ", text)[:5000]
    except Exception as e:
        print(f"  ⚠ scrape failed {url}: {e}")
        return ""


def _normalise(url: str) -> str:
    """Ensure the provided URL has a scheme and no trailing slash."""

    url = url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    return url.rstrip("/")


def scrape_website(website: str) -> dict:
    """Return scraped homepage + about text for a website domain."""

    base = _normalise(website)
    home = _scrape(base)

    # Common URL patterns for "About".
    about = _scrape(urljoin(base + "/", "about")) or _scrape(
        urljoin(base + "/", "about-us")
    )

    return {"homepage": home, "about": about, "base_url": base}


def enrich_company(lead: dict) -> dict:
    """Enrich a lead dict using web scraping + Groq LLM.

    Input keys expected in `lead`:
    - company, website, industry, role, pain_points, team_size (some are optional)

    Output:
    - A dict with keys required by the PDF generator.

    Reliability:
    - Any failure in scraping/LLM parsing falls back to `_fallback()`.
    """

    scraped = scrape_website(lead["website"]) if lead.get("website") else {}

    # Context is embedded into the prompt so the LLM can produce a structured response.
    context = f"""
Company     : {lead['company']}
Industry    : {lead['industry']}
Website     : {lead.get('website', 'N/A')}
Contact Role: {lead.get('role', 'N/A')}
Pain Points : {lead.get('pain_points', 'N/A')}
Team Size   : {lead.get('team_size', 'N/A')}

--- Homepage (scraped) ---
{scraped.get('homepage', 'Not available')}

--- About page (scraped) ---
{scraped.get('about', 'Not available')}
""".strip()

    prompt = f"""You are a senior business analyst. Analyse the company data below and return ONLY
    a valid JSON object (no markdown, no preamble) with these exact keys:

{{
  "company_overview": "2-3 sentence summary of what the company does and their market position",
  "value_proposition": "Core value proposition in 1-2 sentences",
  "target_market": "Who their customers/users are",
  "business_model": "How they make money (SaaS/services/e-commerce/etc.)",
  "key_strengths": ["strength 1", "strength 2", "strength 3"],
  "potential_challenges": ["challenge 1", "challenge 2"],
  "technology_signals": "Visible tech stack or digital maturity signals",
  "growth_stage": "Early-stage / Growth / Established / Enterprise",
  "ai_opportunity_areas": ["specific AI/automation opportunity 1", "opportunity 2"],
  "recommended_solutions": [
    {{"title": "Solution Name", "description": "Why this matters for them", "impact": "High/Medium"}},
    {{"title": "Solution Name", "description": "Why this matters for them", "impact": "High/Medium"}}
  ],
  "personalized_opening": "Warm 2-3 sentence opening for the report referencing something concrete about their business",
  "industry_context": "1-2 sentences on trends in their industry and why automation matters now",
  "estimated_roi_narrative": "2-3 sentence ROI/impact narrative for a company like this",
  "confidence_level": "high/medium/low"
}}

Data:
{context}"""

    try:
        from django.conf import settings as djsettings

        api_key = djsettings.GROQ_API_KEY
        client = Groq(api_key=api_key)

        # Groq chat completion call. The prompt asks for strict JSON output.
        resp = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            max_tokens=1500,
            messages=[{"role": "user", "content": prompt}],
        )

        raw = resp.choices[0].message.content.strip()

        # Some models wrap JSON in code fences. Remove them before json.loads.
        raw = re.sub(r"^```json\s*|\s*```$", "", raw, flags=re.MULTILINE)
        data = json.loads(raw)
    except Exception as e:
        # Best-effort: if enrichment fails, still return a valid structure.
        print(f"  ⚠ Groq enrichment failed: {e} — using fallback")
        data = _fallback(lead)

    # Expose scraped content for potential debugging / future report sections.
    data["_scraped"] = scraped
    return data


def _fallback(lead: dict) -> dict:
    """Generate a minimal-but-complete enrichment payload."""

    return {
        "company_overview": f"{lead['company']} operates in the {lead['industry']} sector.",
        "value_proposition": "Delivers value through specialised services.",
        "target_market": f"Businesses in the {lead['industry']} space.",
        "business_model": "To be determined.",
        "key_strengths": ["Industry presence", "Dedicated team", "Domain expertise"],
        "potential_challenges": ["Manual processes", "Scaling operations"],
        "technology_signals": "Limited data available.",
        "growth_stage": "Growth",
        "ai_opportunity_areas": ["Process automation", "Lead management"],
        "recommended_solutions": [
            {
                "title": "Workflow Automation",
                "description": "Streamline repetitive tasks",
                "impact": "High",
            },
            {
                "title": "AI-Powered Analytics",
                "description": "Data-driven decisions",
                "impact": "Medium",
            },
        ],
        "personalized_opening": f"We're excited to connect with {lead['company']}.",
        "industry_context": f"The {lead['industry']} sector is rapidly adopting AI tools.",
        "estimated_roi_narrative": "Companies typically see 30–50% reduction in manual overhead within 90 days.",
        "confidence_level": "low",
    }

