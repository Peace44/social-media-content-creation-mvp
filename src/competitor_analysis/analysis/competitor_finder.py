from __future__ import annotations

import json
import time

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


def analyze_profile(raw: RawProfile, profile_url: str, verbose: bool = False) -> ProfileSummary:
    """Use Claude to extract structured profile info from scraped data."""
    user_prompt = f"""\
Analyze this social media profile and return a JSON object with these fields:
- name (str): The person or brand name
- niche (str): Their market niche / industry
- target_audience (str): Who they target
- services (list[str]): Services or products they offer
- geographic_scope (str): Geographic market (e.g. "Italy", "Global")
- brand_values (list[str]): Core brand values or positioning
- website (str|null): Website URL if found
- social_links (dict[str,str]): Other social profile URLs keyed by platform name
- bio (str): A brief bio/description of the profile

Profile data:
{raw.to_text()}

Also consider: the profile URL is {profile_url}
If the scraped data is sparse (e.g. Instagram blocked scraping), use your knowledge of this profile.
Return only a JSON object.
"""
    raw_response = _call_claude(_PROFILE_SYSTEM, user_prompt, verbose=verbose)

    # Strip markdown code fences if Claude wrapped the JSON
    cleaned = raw_response.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()

    data = json.loads(cleaned)
    return ProfileSummary(**data)


def find_competitors(
    profile: ProfileSummary,
    max_results: int = 10,
    use_cache: bool = True,
    verbose: bool = False,
) -> list[CompetitorCandidate]:
    """Search for and identify direct competitors using SerpAPI + Claude."""
    console = Console()

    # Build targeted search queries
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
    return [CompetitorCandidate(**item) for item in data[:max_results]]


def _build_search_queries(profile: ProfileSummary) -> list[str]:
    """Build targeted search queries to find competitors."""
    niche = profile.niche
    geo = profile.geographic_scope
    # Take only the first 3 words of target_audience to keep queries short
    audience_words = profile.target_audience.split()[:3]
    audience_short = " ".join(audience_words)

    queries = [
        f"agenzia marketing {audience_short} {geo} Instagram",
        f"consulente marketing {audience_short} {geo}",
        f"{niche} {geo} social media",
        f"marketing digitale {audience_short} Italia Instagram",
    ]

    # Add service-specific queries
    for service in profile.services[:2]:
        queries.append(f"{service} {audience_short} {geo}")

    return queries[:5]
