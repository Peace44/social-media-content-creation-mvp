from __future__ import annotations

import json
import hashlib
import time
from datetime import datetime, timedelta
from pathlib import Path

import anthropic
from rich.console import Console

from competitor_analysis import config
from competitor_analysis.models import CompetitorCandidate, ProfileSummary
from competitor_analysis.scraper.profile import RawProfile
from competitor_analysis.scraper.search import search

_MODEL = "claude-sonnet-4-6"

_PROFILE_SYSTEM = """\
You are an expert social media marketing analyst specializing in the Italian market.
Your task is to analyze a social media profile and extract structured information about it.
Always respond with valid JSON only — no markdown, no explanation.
"""

_COMPETITOR_SYSTEM = """\
You are an expert competitive intelligence analyst for the Italian digital marketing industry.
Your task is to identify direct competitors based on a client's profile and web search results.
A direct competitor: operates in the same niche, targets the same audience, offers similar services.
Always respond with valid JSON only — no markdown, no explanation.
"""

# Step C: verification cache
_VERIFY_CACHE_DIR = Path(__file__).resolve().parents[4] / ".cache" / "verify"
_VERIFY_CACHE_TTL = timedelta(days=7)

# Step D: few-shot examples — only injected when niche is coach/counselor
_COACH_NICHE_TOKENS = {"coach", "counselor", "counseling", "coaching"}

_COACH_FEW_SHOT = """\
EXAMPLES for this niche (marketing per coach e counselor):

CORRECT direct competitors (same niche):
- Federico Ferrarelli (@federicoferrarellimarketing): consulente di marketing specializzato in coach e counselor italiani
- Ivano Peggion – Impact Academy: formazione e marketing specificamente per coach professionisti
- Francesco Conte: strategia social media per coach e professionisti della crescita personale

NOT direct competitors (reject these even if they work in marketing):
- Renato Bertuol: consulente marketing per PMI — target completamente diverso (piccole imprese, non coach)
- Alessandro Ingala: marketing e comunicazione per aziende — non si occupa di coach/counselor
- Lorenzo Marabini: marketing per imprese e organizzazioni — niche PMI, non coach

REJECTION CRITERIA — exclude any candidate who:
- Works in marketing for generic SMEs (PMI / Piccole e Medie Imprese)
- Targets industries unrelated to personal development, coaching, or counseling
- Only tangentially mentions coaching (e.g. one blog post) but focuses on other sectors
"""


def _call_claude(system: str, user: str, retries: int = 3, verbose: bool = False) -> str:
    """Call Claude API with retry on transient errors."""
    client = anthropic.Anthropic(api_key=config.require("ANTHROPIC_API_KEY"))
    for attempt in range(retries):
        try:
            message = client.messages.create(
                model=_MODEL,
                max_tokens=2048,
                system=system,
                messages=[{"role": "user", "content": user}],
            )
            return message.content[0].text
        except anthropic.APIStatusError as exc:
            if attempt < retries - 1 and exc.status_code in (429, 529):
                wait = 2 ** attempt
                if verbose:
                    Console().print(f"[yellow]Rate limited, retrying in {wait}s...[/yellow]")
                time.sleep(wait)
                continue
            raise


# ── Step A: profile enrichment via SerpAPI when scraping is blocked ───────────

def _enrich_profile_from_search(profile_url: str, use_cache: bool, verbose: bool) -> str:
    """Run a targeted SerpAPI query to recover bio info blocked by Instagram."""
    handle = profile_url.rstrip("/").split("/")[-1]
    query = f'"{handle}" instagram marketing Italia'
    results = search(query, use_cache=use_cache, verbose=verbose)
    if not results:
        return ""
    snippets = "\n".join(f"- {r.title}: {r.snippet}" for r in results[:5])
    return f"\nAdditional search context (from Google, used because direct scraping was blocked):\n{snippets}"


def analyze_profile(
    raw: RawProfile,
    profile_url: str,
    verbose: bool = False,
    use_cache: bool = True,
) -> ProfileSummary:
    """Use Claude to extract structured profile info from scraped data."""
    extra_context = ""

    # Step A: if Instagram returned an empty/login-wall page, enrich via SerpAPI
    is_instagram = "instagram.com" in profile_url.lower()
    scraping_blocked = is_instagram and not raw.description.strip()
    if scraping_blocked:
        extra_context = _enrich_profile_from_search(profile_url, use_cache=use_cache, verbose=verbose)

    user_prompt = f"""\
Analyze this social media profile and return a JSON object with these fields:
- name (str): The person or brand name
- niche (str): Their market niche / industry — be as specific as possible \
(e.g. "marketing per coach e counselor" NOT just "marketing")
- target_audience (str): Who they target — be specific \
(e.g. "coach e counselor italiani" NOT just "professionisti")
- services (list[str]): Services or products they offer
- geographic_scope (str): Geographic market (e.g. "Italy", "Global")
- brand_values (list[str]): Core brand values or positioning
- website (str|null): Website URL if found
- social_links (dict[str,str]): Other social profile URLs keyed by platform name
- bio (str): A brief bio/description of the profile

Profile data:
{raw.to_text()}

Also consider: the profile URL is {profile_url}
{extra_context}
If the scraped data is sparse (e.g. Instagram blocked scraping), use your knowledge of this profile.
Return only a JSON object.
"""
    raw_response = _call_claude(_PROFILE_SYSTEM, user_prompt, verbose=verbose)

    cleaned = raw_response.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()

    data = json.loads(cleaned)
    return ProfileSummary(**data)


# ── Step B: niche-aware search query builder ──────────────────────────────────

def _build_search_queries(profile: ProfileSummary) -> list[str]:
    """Build niche-specific search queries to find direct competitors."""
    niche = profile.niche
    geo = profile.geographic_scope
    audience = profile.target_audience

    # Pull 2-3 salient micro-niche tokens from niche + audience
    niche_tokens = [w.lower() for w in niche.split() if len(w) > 3][:4]
    audience_words = audience.split()[:3]
    audience_short = " ".join(audience_words)

    queries = [
        # Exact niche phrase — highest signal
        f'"{niche}" Italia Instagram',
        # Niche + platform combination
        f"marketing per {audience_short} Instagram Italia",
        # Niche via token — broader
        f"consulente marketing {audience_short} Italia",
        # Service-based
        f"social media {audience_short} {geo}",
    ]

    # Add a query with the top micro-niche tokens joined (e.g. "coach counselor marketing")
    if niche_tokens:
        queries.append(f'{" ".join(niche_tokens[:3])} consulente marketing Italia')

    # Add service-specific queries
    for service in profile.services[:2]:
        queries.append(f"{service} {audience_short} {geo}")

    return queries[:6]


# ── Step C: per-candidate verification with caching ──────────────────────────

def _verify_cache_path(primary_url: str, niche: str) -> Path:
    key = hashlib.md5(f"{primary_url}|{niche}".encode()).hexdigest()
    return _VERIFY_CACHE_DIR / f"{key}.json"


def _load_verify_cache(primary_url: str, niche: str) -> dict | None:
    path = _verify_cache_path(primary_url, niche)
    if not path.exists():
        return None
    data = json.loads(path.read_text())
    cached_at = datetime.fromisoformat(data["cached_at"])
    if datetime.now() - cached_at > _VERIFY_CACHE_TTL:
        return None
    return data


def _save_verify_cache(primary_url: str, niche: str, result: dict) -> None:
    _VERIFY_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _verify_cache_path(primary_url, niche)
    path.write_text(json.dumps({**result, "cached_at": datetime.now().isoformat()}, ensure_ascii=False, indent=2))


def _verify_candidates(
    candidates: list[CompetitorCandidate],
    profile: ProfileSummary,
    verbose: bool = False,
) -> list[CompetitorCandidate]:
    """Re-rank and filter candidates with a batch Claude verification call."""
    if not candidates:
        return candidates

    # Split into cached and uncached
    cached_results: dict[str, dict] = {}
    to_verify: list[CompetitorCandidate] = []

    for c in candidates:
        cached = _load_verify_cache(c.primary_url, profile.niche)
        if cached:
            cached_results[c.primary_url] = cached
        else:
            to_verify.append(c)

    # Batch-verify uncached candidates in a single Claude call
    if to_verify:
        candidates_text = "\n".join(
            f"{i+1}. {c.name} | URL: {c.primary_url} | {c.description}"
            for i, c in enumerate(to_verify)
        )
        user_prompt = f"""\
Client profile:
- Niche: {profile.niche}
- Target audience: {profile.target_audience}
- Geographic scope: {profile.geographic_scope}

Evaluate each candidate below. A DIRECT competitor must operate in EXACTLY the same niche \
({profile.niche}) and target the same audience ({profile.target_audience}).
A consultant who works in marketing for generic businesses (PMI) is NOT a direct competitor \
even if they are in the same geographic area.

Return a JSON array with one object per candidate (same order), each with:
- primary_url (str): the candidate's URL unchanged
- is_direct_competitor (bool): true only if they precisely match the niche and audience
- confidence (float): 0.0–1.0
- reason (str): one sentence explanation

Candidates:
{candidates_text}

Return only a JSON array.
"""
        raw_response = _call_claude(_COMPETITOR_SYSTEM, user_prompt, verbose=verbose)
        cleaned = raw_response.strip()
        if cleaned.startswith("```"):
            cleaned = cleaned.split("```")[1]
            if cleaned.startswith("json"):
                cleaned = cleaned[4:]
            cleaned = cleaned.strip()

        try:
            verifications = json.loads(cleaned)
            for v in verifications:
                url = v.get("primary_url", "")
                _save_verify_cache(url, profile.niche, v)
                cached_results[url] = v
        except (json.JSONDecodeError, TypeError):
            # If verification fails, keep all candidates (graceful degradation)
            return candidates

    # Filter and sort: keep confirmed competitors, sort by confidence
    scored: list[tuple[float, CompetitorCandidate]] = []
    for c in candidates:
        v = cached_results.get(c.primary_url, {})
        is_direct = v.get("is_direct_competitor", True)  # default True on missing data
        confidence = float(v.get("confidence", 0.5))
        if is_direct and confidence >= 0.5:
            scored.append((confidence, c))

    # If verification filtered everything out, fall back to top half of originals
    if not scored:
        return candidates[: max(1, len(candidates) // 2)]

    scored.sort(key=lambda x: x[0], reverse=True)
    return [c for _, c in scored]


# ── Main entrypoint ────────────────────────────────────────────────────────────

def find_competitors(
    profile: ProfileSummary,
    max_results: int = 10,
    use_cache: bool = True,
    verbose: bool = False,
) -> list[CompetitorCandidate]:
    """Search for and identify direct competitors using SerpAPI + Claude."""
    console = Console()

    # Step B: niche-aware queries
    queries = _build_search_queries(profile)
    if verbose:
        console.print(f"  Search queries: {queries}")

    from competitor_analysis.models import SearchResult

    all_results: list[SearchResult] = []
    for query in queries:
        results = search(query, use_cache=use_cache, verbose=verbose)
        all_results.extend(results)
        if len(all_results) >= 30:
            break

    # Deduplicate by URL
    seen: set[str] = set()
    unique_results: list[SearchResult] = []
    for r in all_results:
        if r.url not in seen:
            seen.add(r.url)
            unique_results.append(r)

    if verbose:
        console.print(f"  Total unique search results: {len(unique_results)}")

    results_text = "\n".join(
        f"[{i+1}] Title: {r.title}\n    URL: {r.url}\n    Snippet: {r.snippet}"
        for i, r in enumerate(unique_results[:30])
    )

    # Step D: inject rejection criteria + conditional few-shots
    niche_lower = profile.niche.lower()
    is_coach_niche = any(token in niche_lower for token in _COACH_NICHE_TOKENS) or any(
        token in profile.target_audience.lower() for token in _COACH_NICHE_TOKENS
    )
    few_shot_block = _COACH_FEW_SHOT if is_coach_niche else (
        f"\nREJECTION CRITERIA — only include candidates who operate in '{profile.niche}' "
        f"and target '{profile.target_audience}'. Exclude anyone in a different niche even "
        f"if they use similar marketing tactics.\n"
    )

    user_prompt = f"""\
I have a client with this profile:
Name: {profile.name}
Niche: {profile.niche}
Target audience: {profile.target_audience}
Services: {', '.join(profile.services)}
Geographic scope: {profile.geographic_scope}

From the following web search results, identify up to {max_results} DIRECT competitors.
A direct competitor operates in the same niche ({profile.niche}), targets the same audience \
({profile.target_audience}), offers similar services, and operates in {profile.geographic_scope}.
{few_shot_block}
Search results:
{results_text}

Return a JSON array of competitor objects. Each object must have:
- name (str): Competitor name
- description (str): Brief description of who they are
- primary_url (str): Their main URL (Instagram profile, website, etc.)
- relevance_reason (str): Why they are a direct competitor
- social_links (dict[str,str]): Their social profile URLs keyed by platform
- website (str|null): Their website URL if known

If search results are sparse, also include competitors you know from your training knowledge.
Return only a JSON array.
"""
    raw_response = _call_claude(_COMPETITOR_SYSTEM, user_prompt, verbose=verbose)

    cleaned = raw_response.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()

    data = json.loads(cleaned)
    candidates = [CompetitorCandidate(**item) for item in data[:max_results * 2]]

    # Step C: verify and re-rank candidates
    verified = _verify_candidates(candidates, profile, verbose=verbose)
    return verified[:max_results]
