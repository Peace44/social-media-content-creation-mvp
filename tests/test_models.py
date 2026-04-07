"""Tests for Pydantic data models."""
from competitor_analysis.models import (
    CompetitorKPI,
    CompetitorRow,
    ProfileSummary,
    SearchResult,
)


def test_profile_summary_defaults():
    p = ProfileSummary(
        name="Test",
        niche="Marketing",
        target_audience="SMBs",
        services=["SEO"],
        geographic_scope="Italy",
    )
    assert p.brand_values == []
    assert p.website is None
    assert p.social_links == {}
    assert p.bio == ""


def test_competitor_kpi_defaults():
    kpi = CompetitorKPI()
    assert kpi.follower_count == {}
    assert kpi.interaction_score == "N/A"
    assert kpi.active_since == "N/A"
    assert kpi.activities == "N/A"
    assert isinstance(kpi.structure, dict)


def test_competitor_kpi_structure_defaults():
    kpi = CompetitorKPI()
    assert kpi.structure["website"] is False
    assert kpi.structure["landing_page"] is False
    assert kpi.structure["ebook"] is False
    assert kpi.structure["freebie"] is False
    assert kpi.structure["multi_platform"] is False


def test_search_result_fields():
    r = SearchResult(title="Test", url="https://example.com", snippet="A snippet")
    assert r.title == "Test"
    assert r.url == "https://example.com"
    assert r.snippet == "A snippet"


def test_competitor_row_uses_fixtures(sample_row: CompetitorRow):
    assert sample_row.name == "Test Agency"
    assert sample_row.active_since == "2020"
    assert sample_row.kpis.follower_count["instagram"] == "5.2K"
    assert sample_row.kpis.structure["website"] is True


def test_profile_summary_round_trip(sample_profile: ProfileSummary):
    data = sample_profile.model_dump()
    restored = ProfileSummary(**data)
    assert restored.name == sample_profile.name
    assert restored.services == sample_profile.services
