from __future__ import annotations

import re

import httpx
from bs4 import BeautifulSoup
from rich.console import Console

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "it-IT,it;q=0.9,en-US;q=0.8,en;q=0.7",
}


class RawProfile:
    """Container for data scraped from a social media profile page."""

    def __init__(
        self,
        url: str,
        title: str,
        description: str,
        meta_tags: dict[str, str],
        visible_text: str,
        platform: str,
    ) -> None:
        self.url = url
        self.title = title
        self.description = description
        self.meta_tags = meta_tags
        self.visible_text = visible_text
        self.platform = platform

    def to_text(self) -> str:
        """Flatten all scraped data into a single text block for Claude."""
        parts = [
            f"URL: {self.url}",
            f"Platform: {self.platform}",
            f"Title: {self.title}",
            f"Description: {self.description}",
        ]
        for key, value in self.meta_tags.items():
            parts.append(f"Meta[{key}]: {value}")
        if self.visible_text:
            # Truncate visible text to avoid huge tokens
            parts.append(f"Page text (truncated):\n{self.visible_text[:3000]}")
        return "\n".join(parts)


def _detect_platform(url: str) -> str:
    url_lower = url.lower()
    if "instagram.com" in url_lower:
        return "Instagram"
    if "facebook.com" in url_lower:
        return "Facebook"
    if "linkedin.com" in url_lower:
        return "LinkedIn"
    if "tiktok.com" in url_lower:
        return "TikTok"
    if "youtube.com" in url_lower or "youtu.be" in url_lower:
        return "YouTube"
    return "Website"


def scrape_profile(url: str, verbose: bool = False) -> RawProfile:
    """Fetch a social profile URL and extract useful text/metadata."""
    console = Console()
    platform = _detect_platform(url)

    try:
        with httpx.Client(headers=_HEADERS, follow_redirects=True, timeout=15) as client:
            response = client.get(url)
            response.raise_for_status()
            html = response.text
    except httpx.HTTPError as exc:
        if verbose:
            console.print(f"[yellow]Warning: Could not fetch {url}: {exc}[/yellow]")
        # Return minimal profile so the pipeline can continue with Claude's knowledge
        return RawProfile(
            url=url,
            title="",
            description="",
            meta_tags={},
            visible_text="",
            platform=platform,
        )

    soup = BeautifulSoup(html, "html.parser")

    title = soup.title.string.strip() if soup.title and soup.title.string else ""

    # Extract all useful meta tags
    meta_tags: dict[str, str] = {}
    for tag in soup.find_all("meta"):
        name = tag.get("name") or tag.get("property") or tag.get("itemprop") or ""
        content = tag.get("content") or ""
        if name and content:
            meta_tags[name] = content

    description = (
        meta_tags.get("description")
        or meta_tags.get("og:description")
        or meta_tags.get("twitter:description")
        or ""
    )

    # Extract visible text, collapsing whitespace
    for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
        tag.decompose()
    visible_text = re.sub(r"\s+", " ", soup.get_text(separator=" ")).strip()

    if verbose:
        console.print(f"  Scraped {len(html)} bytes from {platform} ({url})")

    return RawProfile(
        url=url,
        title=title,
        description=description,
        meta_tags=meta_tags,
        visible_text=visible_text,
        platform=platform,
    )
