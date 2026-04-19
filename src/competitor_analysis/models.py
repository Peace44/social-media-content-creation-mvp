from __future__ import annotations

from pydantic import BaseModel, Field




class ProfileSummary(BaseModel):
    name: str
    niche: str
    target_audience: str
    services: list[str]
    geographic_scope: str
    brand_values: list[str] = Field(default_factory=list)
    website: str | None = None
    social_links: dict[str, str] = Field(default_factory=dict)
    bio: str = ""


class SearchResult(BaseModel):
    title: str
    url: str
    snippet: str


class CompetitorCandidate(BaseModel):
    name: str
    description: str
    primary_url: str
    relevance_reason: str
    social_links: dict[str, str] = Field(default_factory=dict)
    website: str | None = None


class CompetitorKPI(BaseModel):
    follower_count: dict[str, str] = Field(
        default_factory=dict,
        description="Platform -> follower count string (e.g. '12.5K') or 'N/A'",
    )
    interaction_score: str = "N/A"
    structure: dict[str, bool] = Field(
        default_factory=lambda: {
            "website": False,
            "landing_page": False,
            "ebook": False,
            "freebie": False,
            "multi_platform": False,
        }
    )
    active_since: str = "N/A"
    activities: str = "N/A"
    social_links: dict[str, str] = Field(
        default_factory=dict,
        description="Platform -> profile URL extracted during KPI analysis",
    )


class CompetitorRow(BaseModel):
    name: str
    description: str
    activities: str
    active_since: str
    social_profiles: dict[str, str] = Field(default_factory=dict)
    website_and_links: list[str] = Field(default_factory=list)
    why_competitor: str
    kpis: CompetitorKPI


class AnalysisRecordMeta(BaseModel):
    id: str
    created_at: str
    input_url: str
    profile_name: str
    competitor_count: int


class AnalysisRecord(BaseModel):
    id: str
    created_at: str
    input_url: str
    profile: ProfileSummary
    rows: list[CompetitorRow]
