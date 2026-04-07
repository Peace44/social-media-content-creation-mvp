"""Tests for the scraper modules."""
import pytest
import respx
import httpx

from competitor_analysis.scraper.profile import scrape_profile, _detect_platform


def test_detect_platform_instagram():
    assert _detect_platform("https://www.instagram.com/test/") == "Instagram"


def test_detect_platform_linkedin():
    assert _detect_platform("https://www.linkedin.com/company/test/") == "LinkedIn"


def test_detect_platform_unknown():
    assert _detect_platform("https://example.com") == "Website"


@respx.mock
def test_scrape_profile_extracts_meta():
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
def test_scrape_profile_handles_http_error():
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
