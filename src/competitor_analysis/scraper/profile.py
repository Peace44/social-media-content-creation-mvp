from __future__ import annotations

import json
import re
from urllib.parse import urlparse

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

# Map bare hostnames (without www.) to a canonical platform name.
_PLATFORM_HOSTS: dict[str, str] = {
    "instagram.com": "Instagram",
    "facebook.com": "Facebook",
    "fb.com": "Facebook",
    "linkedin.com": "LinkedIn",
    "tiktok.com": "TikTok",
    "twitter.com": "Twitter",
    "x.com": "Twitter",
    "youtube.com": "YouTube",
    "youtu.be": "YouTube",
}

# Platforms that need a real browser.  Playwright improves rendering but does
# not defeat login walls — the search-fallback in competitor_finder.py is what
# actually recovers usable data when a page is login-gated.
_JS_PLATFORMS = {"Instagram", "TikTok", "Twitter", "Facebook", "LinkedIn"}


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
        extra_data: dict | None = None,
    ) -> None:
        self.url = url
        self.title = title
        self.description = description
        self.meta_tags = meta_tags
        self.visible_text = visible_text
        self.platform = platform
        self.extra_data: dict = extra_data or {}

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
        if self.extra_data:
            parts.append(
                f"Structured profile data (JSON):\n{json.dumps(self.extra_data, ensure_ascii=False, indent=2)}"
            )
        if self.visible_text:
            parts.append(f"Page text (truncated):\n{self.visible_text[:3000]}")
        return "\n".join(parts)


def _detect_platform(url: str) -> str:
    """Return a canonical platform name for *url* using exact hostname matching.

    Hostname matching (not substring) avoids false positives such as
    ``netflix.com`` matching ``x.com`` via substring search.
    """
    try:
        host = urlparse(url).hostname or ""
    except ValueError:
        host = ""
    # Strip port if present (urlparse keeps it in hostname for bare IPs but
    # not for normal domains, so this is just a safety measure).
    host = host.split(":")[0].lower()
    for domain, platform in _PLATFORM_HOSTS.items():
        if host == domain or host.endswith("." + domain):
            return platform
    return "Website"


def _parse_extra_data(description: str, visible_text: str, platform: str) -> dict:
    """Extract structured signals from scraped text to enrich Claude's input."""
    data: dict = {}

    if platform == "Instagram" and description:
        # Description format: "117 follower, 206 seguiti, 54 post - Name (@handle) su Instagram: 'bio'"
        # or English: "117 Followers, 206 Following, 54 Posts"
        m_followers = re.search(r"([\d,.]+[KkMm]?)\s*follower", description, re.I)
        # Italian "seguiti" = Following; also match English "following"
        m_following = re.search(r"([\d,.]+[KkMm]?)\s*(?:seguiti|following)", description, re.I)
        m_posts = re.search(r"([\d,.]+[KkMm]?)\s*post", description, re.I)
        m_handle = re.search(r"@([\w.]+)", description)
        if m_followers:
            data["followers"] = m_followers.group(1)
        if m_following:
            data["following"] = m_following.group(1)
        if m_posts:
            data["posts_count"] = m_posts.group(1)
        if m_handle:
            data["handle"] = m_handle.group(1)

    elif platform == "Twitter" and description:
        # OG description often contains follower counts and handle
        m_followers = re.search(r"([\d,.]+[KkMm]?)\s*follower", description, re.I)
        m_handle = re.search(r"@([\w]+)", description)
        if m_followers:
            data["followers"] = m_followers.group(1)
        if m_handle:
            data["handle"] = m_handle.group(1)

    elif platform == "TikTok" and description:
        m_followers = re.search(r"([\d,.]+[KkMm]?)\s*follower", description, re.I)
        m_likes = re.search(r"([\d,.]+[KkMm]?)\s*like", description, re.I)
        m_handle = re.search(r"@([\w.]+)", description)
        if m_followers:
            data["followers"] = m_followers.group(1)
        if m_likes:
            data["likes"] = m_likes.group(1)
        if m_handle:
            data["handle"] = m_handle.group(1)

    # Extract all hashtags from the visible page text (posts, captions, bio)
    hashtags = list(dict.fromkeys(
        re.findall(r"#[\w\u00C0-\u024F]+", visible_text)
    ))
    if hashtags:
        data["hashtags_found"] = hashtags[:40]

    # Extract external URLs (website links in bio or page)
    urls = re.findall(
        r"(?:https?://|www\.)[^\s\"'<>()]+", visible_text
    )
    # Filter out the platform's own domain
    platform_domain = platform.lower() + ".com"
    external_urls = [
        u.rstrip(".,;)") for u in urls
        if platform_domain not in u.lower()
        and "facebook.com" not in u.lower()
        and "apple.com" not in u.lower()
        and "google.com" not in u.lower()
    ]
    if external_urls:
        data["external_links"] = list(dict.fromkeys(external_urls))[:5]

    return data


def _scrape_with_playwright(url: str, verbose: bool = False) -> str:
    """Render the page with a real browser and return the final HTML."""
    from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout

    console = Console()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            ctx = browser.new_context(
                user_agent=_HEADERS["User-Agent"],
                locale="it-IT",
                extra_http_headers={"Accept-Language": _HEADERS["Accept-Language"]},
            )
            page = ctx.new_page()
            page.goto(url, wait_until="networkidle", timeout=20_000)
            html = page.content()
            browser.close()
            return html
    except PWTimeout:
        if verbose:
            console.print(f"[yellow]Playwright timeout for {url}, falling back to httpx[/yellow]")
        return ""
    except Exception as exc:
        if verbose:
            console.print(f"[yellow]Playwright error for {url}: {exc}[/yellow]")
        return ""


def scrape_profile(url: str, verbose: bool = False) -> RawProfile:
    """Fetch a social profile URL and extract useful text/metadata."""
    console = Console()
    platform = _detect_platform(url)

    html = ""
    if platform in _JS_PLATFORMS:
        if verbose:
            console.print(f"  Using Playwright for {platform} ({url})")
        html = _scrape_with_playwright(url, verbose=verbose)

    if not html:
        try:
            with httpx.Client(headers=_HEADERS, follow_redirects=True, timeout=15) as client:
                response = client.get(url)
                response.raise_for_status()
                html = response.text
        except httpx.HTTPError as exc:
            if verbose:
                console.print(f"[yellow]Warning: Could not fetch {url}: {exc}[/yellow]")
            return RawProfile(
                url=url, title="", description="", meta_tags={},
                visible_text="", platform=platform,
            )

    soup = BeautifulSoup(html, "html.parser")

    title = soup.title.string.strip() if soup.title and soup.title.string else ""

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

    for tag in soup(["script", "style", "noscript", "header", "footer", "nav"]):
        tag.decompose()
    visible_text = re.sub(r"\s+", " ", soup.get_text(separator=" ")).strip()

    extra_data = _parse_extra_data(description, visible_text, platform)

    if verbose:
        console.print(f"  Scraped {len(html)} bytes from {platform} ({url})")

    return RawProfile(
        url=url,
        title=title,
        description=description,
        meta_tags=meta_tags,
        visible_text=visible_text,
        platform=platform,
        extra_data=extra_data,
    )
