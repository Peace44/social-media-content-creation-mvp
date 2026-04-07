from __future__ import annotations

import json
import time

import anthropic
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, MofNCompleteColumn

from competitor_analysis import config
from competitor_analysis.models import CompetitorCandidate, CompetitorKPI, CompetitorRow, ProfileSummary
from competitor_analysis.scraper.profile import scrape_profile
from competitor_analysis.scraper.search import search

_MODEL = "claude-sonnet-4-6"

_KPI_SYSTEM = """\
You are an expert social media analyst. Your task is to extract structured KPI data
about a competitor from web research data. Always respond with valid JSON only.
"""

_PLATFORMS = ["instagram", "facebook", "linkedin", "youtube", "tiktok"]


def _call_claude(user: str, retries: int = 3) -> str:
    client = anthropic.Anthropic(api_key=config.require("ANTHROPIC_API_KEY"))
    for attempt in range(retries):
        try:
            message = client.messages.create(
                model=_MODEL,
                max_tokens=1024,
                system=_KPI_SYSTEM,
                messages=[{"role": "user", "content": user}],
            )
            return message.content[0].text
        except anthropic.APIStatusError as exc:
            if attempt < retries - 1 and exc.status_code in (429, 529):
                time.sleep(2 ** attempt)
                continue
            raise


def _gather_competitor_data(
    candidate: CompetitorCandidate,
    use_cache: bool,
    verbose: bool,
) -> str:
    """Collect raw data about a competitor from searches and page scraping."""
    parts: list[str] = [
        f"Competitor: {candidate.name}",
        f"URL: {candidate.primary_url}",
        f"Description: {candidate.description}",
    ]

    # Enrich with a targeted search
    query = f"{candidate.name} marketing Italy Instagram followers"
    results = search(query, use_cache=use_cache, verbose=verbose)
    if results:
        snippets = "\n".join(f"- {r.title}: {r.snippet}" for r in results[:5])
        parts.append(f"Search snippets:\n{snippets}")

    # Try to scrape the primary URL (website or social page)
    if candidate.primary_url:
        raw = scrape_profile(candidate.primary_url, verbose=verbose)
        text = raw.to_text()
        if text.strip():
            parts.append(f"Scraped page data:\n{text[:2000]}")

    # Try to scrape the website if different from primary URL
    if candidate.website and candidate.website != candidate.primary_url:
        raw_site = scrape_profile(candidate.website, verbose=verbose)
        site_text = raw_site.to_text()
        if site_text.strip():
            parts.append(f"Website data:\n{site_text[:1500]}")

    # Add known social links
    if candidate.social_links:
        parts.append("Known social profiles:")
        for platform, url in candidate.social_links.items():
            parts.append(f"  {platform}: {url}")

    return "\n\n".join(parts)


def _analyze_kpis(
    candidate: CompetitorCandidate,
    raw_data: str,
    profile: ProfileSummary,
) -> CompetitorKPI:
    """Use Claude to extract structured KPIs from raw competitor data."""
    user_prompt = f"""\
Extract KPI data for this competitor of {profile.name} ({profile.niche} in {profile.geographic_scope}).

Raw data:
{raw_data}

Return a JSON object with exactly these fields:
- follower_count (dict[str,str]): Platform name (lowercase) -> follower count as string like "12.5K", "3,200", or "N/A"
  Platforms to include: instagram, facebook, linkedin, youtube, tiktok
- interaction_score (str): Overall engagement level: "high", "medium", "low", or "N/A"
- structure (dict[str,bool]): Whether they have each of: website, landing_page, ebook, freebie, multi_platform
- active_since (str): When they started (year or date string), or "N/A"
- activities (str): Brief description of their main content/activities (1-2 sentences)

Return only a JSON object.
"""
    raw_response = _call_claude(user_prompt)

    cleaned = raw_response.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()

    data = json.loads(cleaned)

    # Ensure all platforms are present
    fc = data.get("follower_count", {})
    for platform in _PLATFORMS:
        fc.setdefault(platform, "N/A")

    return CompetitorKPI(
        follower_count=fc,
        interaction_score=data.get("interaction_score", "N/A"),
        structure=data.get("structure", {}),
        active_since=data.get("active_since", "N/A"),
        activities=data.get("activities", "N/A"),
    )


def _build_row(candidate: CompetitorCandidate, kpis: CompetitorKPI) -> CompetitorRow:
    links = list(candidate.social_links.values())
    if candidate.website and candidate.website not in links:
        links.insert(0, candidate.website)

    return CompetitorRow(
        name=candidate.name,
        description=candidate.description,
        activities=kpis.activities,
        active_since=kpis.active_since,
        social_profiles=candidate.social_links,
        website_and_links=links,
        why_competitor=candidate.relevance_reason,
        kpis=kpis,
    )


def gather_kpis(
    candidates: list[CompetitorCandidate],
    profile: ProfileSummary,
    use_cache: bool = True,
    verbose: bool = False,
    console: Console | None = None,
) -> list[CompetitorRow]:
    """Gather KPIs for each competitor and assemble CompetitorRows."""
    if console is None:
        console = Console()

    rows: list[CompetitorRow] = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        console=console,
        transient=True,
    ) as progress:
        task = progress.add_task("Gathering KPIs", total=len(candidates))

        for candidate in candidates:
            progress.update(task, description=f"Analyzing {candidate.name[:30]}...")

            try:
                raw_data = _gather_competitor_data(candidate, use_cache=use_cache, verbose=verbose)
                kpis = _analyze_kpis(candidate, raw_data, profile)
                rows.append(_build_row(candidate, kpis))
            except Exception as exc:
                if verbose:
                    console.print(f"[yellow]Warning: KPI gathering failed for {candidate.name}: {exc}[/yellow]")
                # Build row with empty KPIs rather than failing
                rows.append(_build_row(candidate, CompetitorKPI()))

            progress.advance(task)

    return rows
