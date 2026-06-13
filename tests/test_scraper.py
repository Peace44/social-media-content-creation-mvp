"""Tests for the scraper modules."""
import pytest
import respx
import httpx
from unittest.mock import patch

from competitor_analysis.scraper.profile import scrape_profile, _detect_platform
from competitor_analysis.analysis.competitor_finder import _enrichment_queries, _extract_handle


# ── Platform detection ────────────────────────────────────────────────────────

def test_detect_platform_instagram():
    assert _detect_platform("https://www.instagram.com/test/") == "Instagram"


def test_detect_platform_linkedin():
    assert _detect_platform("https://www.linkedin.com/company/test/") == "LinkedIn"


def test_detect_platform_unknown():
    assert _detect_platform("https://example.com") == "Website"


def test_detect_platform_twitter_x():
    assert _detect_platform("https://x.com/someuser") == "Twitter"
    assert _detect_platform("https://twitter.com/someuser") == "Twitter"
    assert _detect_platform("https://www.twitter.com/someuser") == "Twitter"


def test_detect_platform_facebook():
    assert _detect_platform("https://www.facebook.com/somepage") == "Facebook"
    assert _detect_platform("https://fb.com/somepage") == "Facebook"


def test_detect_platform_tiktok():
    assert _detect_platform("https://www.tiktok.com/@someuser") == "TikTok"


def test_detect_platform_youtube():
    assert _detect_platform("https://www.youtube.com/@channel") == "YouTube"
    assert _detect_platform("https://youtu.be/abc123") == "YouTube"


def test_detect_platform_x_not_false_positive():
    """netflix.com contains the substring 'x.com' — hostname matching must NOT match it."""
    assert _detect_platform("https://www.netflix.com/title/123") == "Website"
    assert _detect_platform("https://example.com/x.com/foo") == "Website"


# ── Handle extraction ─────────────────────────────────────────────────────────

def test_extract_handle_instagram():
    assert _extract_handle("https://www.instagram.com/kolif_agency/") == "kolif_agency"


def test_extract_handle_twitter():
    assert _extract_handle("https://x.com/somehandle") == "somehandle"


def test_extract_handle_tiktok_at():
    assert _extract_handle("https://www.tiktok.com/@coolcreator") == "coolcreator"


def test_extract_handle_linkedin_in():
    assert _extract_handle("https://www.linkedin.com/in/john-doe/") == "john-doe"


def test_extract_handle_linkedin_company():
    assert _extract_handle("https://www.linkedin.com/company/acme-corp/") == "acme-corp"


def test_extract_handle_youtube_at():
    assert _extract_handle("https://www.youtube.com/@kolif") == "kolif"


# ── Enrichment query builder ──────────────────────────────────────────────────

def test_enrichment_queries_instagram():
    queries = _enrichment_queries("Instagram", "testhandle", "https://www.instagram.com/testhandle/")
    assert any("instagram.com" in q.lower() for q in queries), queries
    assert not any("twitter" in q.lower() or "x.com" in q.lower() for q in queries), queries


def test_enrichment_queries_twitter():
    queries = _enrichment_queries("Twitter", "testhandle", "https://x.com/testhandle")
    assert any("x.com" in q or "twitter.com" in q for q in queries), queries
    assert not any("instagram" in q.lower() for q in queries), queries


def test_enrichment_queries_linkedin():
    queries = _enrichment_queries("LinkedIn", "john-doe", "https://www.linkedin.com/in/john-doe/")
    assert any("linkedin" in q.lower() for q in queries), queries
    assert not any("instagram" in q.lower() for q in queries), queries


def test_enrichment_queries_facebook():
    queries = _enrichment_queries("Facebook", "acmecorp", "https://www.facebook.com/acmecorp")
    assert any("facebook" in q.lower() for q in queries), queries


def test_enrichment_queries_tiktok():
    queries = _enrichment_queries("TikTok", "creator99", "https://www.tiktok.com/@creator99")
    assert any("tiktok" in q.lower() for q in queries), queries


@respx.mock
@patch("competitor_analysis.scraper.profile._scrape_with_playwright", return_value="")
def test_scrape_profile_extracts_meta(mock_pw):
    # Playwright is patched to return "" so the httpx mock is used instead.
    html = """
    <html>
    <head>
        <title>Test Profile</title>
        <meta name="description" content="A test description" />
        <meta property="og:description" content="OG description" />
    </head>
    <body>
        <p>Some visible text on the page.</p>
    </body>
    </html>
    """
    respx.get("https://www.instagram.com/test/").mock(
        return_value=httpx.Response(200, text=html)
    )
    raw = scrape_profile("https://www.instagram.com/test/")
    assert raw.platform == "Instagram"
    assert raw.title == "Test Profile"
    assert "description" in raw.meta_tags
    assert "Some visible text" in raw.visible_text


@respx.mock
@patch("competitor_analysis.scraper.profile._scrape_with_playwright", return_value="")
def test_scrape_profile_handles_http_error(mock_pw):
    # Playwright is patched to return "" so the httpx error path is exercised.
    respx.get("https://www.instagram.com/notfound/").mock(
        return_value=httpx.Response(404)
    )
    # Should not raise - returns empty profile
    raw = scrape_profile("https://www.instagram.com/notfound/")
    assert raw.platform == "Instagram"
    assert raw.title == ""


@respx.mock
def test_scrape_profile_to_text():
    html = "<html><head><title>My Page</title></head><body>Hello world</body></html>"
    respx.get("https://example.com").mock(return_value=httpx.Response(200, text=html))
    raw = scrape_profile("https://example.com")
    text = raw.to_text()
    assert "URL: https://example.com" in text
    assert "Platform: Website" in text
    assert "Title: My Page" in text
