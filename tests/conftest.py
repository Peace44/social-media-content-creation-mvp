import pytest
from competitor_analysis.models import (
    CompetitorCandidate,
    CompetitorKPI,
    CompetitorRow,
    ProfileSummary,
    TargetAnalysis,
)


@pytest.fixture
def sample_profile() -> ProfileSummary:
    return ProfileSummary(
        name="Kolif Agency",
        niche="Marketing for coaches and counselors",
        target_audience="Italian coaches and counselors",
        services=["Social media strategy", "Content creation", "Client acquisition"],
        geographic_scope="Italy",
        brand_values=["spontaneity", "warmth", "professionalism", "effectiveness"],
        website="https://kolifagency.it",
        social_links={"instagram": "https://www.instagram.com/sid_consulentemarketing/"},
        bio="Marketing agency by Sid, specializing in coaches and counselors in Italy.",
    )


@pytest.fixture
def sample_candidate() -> CompetitorCandidate:
    return CompetitorCandidate(
        name="Test Agency",
        description="A marketing agency for coaches in Italy",
        primary_url="https://www.instagram.com/test_agency/",
        relevance_reason="Same niche (marketing for coaches), same market (Italy)",
        social_links={"instagram": "https://www.instagram.com/test_agency/"},
        website="https://testagency.it",
    )


@pytest.fixture
def sample_kpis() -> CompetitorKPI:
    return CompetitorKPI(
        follower_count={"instagram": "5.2K", "facebook": "N/A", "linkedin": "800", "youtube": "N/A", "tiktok": "N/A"},
        interaction_score="medium",
        structure={"website": True, "landing_page": True, "ebook": False, "freebie": False, "multi_platform": True},
        active_since="2020",
        activities="Creates content about social media strategy for coaches.",
    )


@pytest.fixture
def sample_row(sample_candidate: CompetitorCandidate, sample_kpis: CompetitorKPI) -> CompetitorRow:
    return CompetitorRow(
        name=sample_candidate.name,
        description=sample_candidate.description,
        activities=sample_kpis.activities,
        active_since=sample_kpis.active_since,
        social_profiles=sample_candidate.social_links,
        website_and_links=["https://testagency.it"],
        why_competitor=sample_candidate.relevance_reason,
        kpis=sample_kpis,
    )


@pytest.fixture
def sample_target_analysis() -> TargetAnalysis:
    return TargetAnalysis(
        problemi=[
            "Non riesco ad acquisire clienti tramite i social",
            "Non so come posizionarmi online",
            "Non ho tempo per creare contenuti efficaci",
        ],
        obiettivi=[
            "Avere una presenza digitale professionale",
            "Acquisire almeno 5 nuovi clienti al mese",
            "Essere riconosciuto come esperto nella mia nicchia",
        ],
        dolore=[
            "Paura di non essere abbastanza visibile",
            "Frustrazione per il tempo sprecato senza risultati",
            "Senso di inadeguatezza rispetto ai competitor",
        ],
        desideri=[
            "Lavorare con clienti ideali senza rincorrere",
            "Avere un metodo chiaro e ripetibile per crescere online",
            "Sentirsi libero e riconosciuto nel proprio lavoro",
        ],
    )
