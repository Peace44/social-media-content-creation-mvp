"""Tests for the marketing strategy generator and markdown exporter."""
from __future__ import annotations

import json
from unittest.mock import patch

from competitor_analysis.models import (
    AnalysisRecord,
    CompetitorRow,
    ContentPillar,
    EditorialItem,
    MarketingStrategy,
    ProfileSummary,
    TargetAnalysis,
)
from competitor_analysis.analysis.strategy_generator import generate_strategy
from competitor_analysis.output.export import strategy_to_markdown


# ── Shared canned response ─────────────────────────────────────────────────────

_CANNED_STRATEGY = {
    "objective": "Acquisire 10 nuovi clienti coach in 3 mesi",
    "summary": "Strategia di posizionamento organico su Instagram puntando su autenticità e competenza nella nicchia coach/counselor.",
    "positioning": "Il consulente di marketing più specializzato in Italia per coach e counselor che vogliono crescere organicamente.",
    "differentiation": [
        "Unico specialista in Italia focalizzato esclusivamente su coach e counselor",
        "Approccio basato sull'autenticità del professionista, non su contenuti generici",
    ],
    "target_focus": "Coach e counselor italiani con 1-5 anni di esperienza che faticano ad acquisire clienti online.",
    "key_messages": [
        "I social possono portarti clienti anche senza pubblicità a pagamento",
        "Il tuo metodo è il tuo marketing",
    ],
    "content_pillars": [
        {
            "title": "Educazione al marketing",
            "description": "Come funziona il marketing per i professionisti del benessere",
            "sample_topics": [
                "3 errori comuni dei coach sui social",
                "Come costruire un profilo Instagram che converte",
            ],
        }
    ],
    "channel_strategy": [
        "Instagram: 4-5 post/reel a settimana — focus su Reels educativi e caroselli",
    ],
    "recommended_actions": [
        "Ottimizzare la bio Instagram con CTA chiara",
        "Pubblicare almeno 3 Reel educativi al mese",
    ],
    "kpis": [
        "Nuovi follower/mese: +200",
        "Lead in DM/mese: 15-20",
    ],
    "editorial_plan": [
        {
            "week": 1,
            "day": "Lunedì",
            "platform": "Instagram",
            "format": "Reel",
            "pillar": "Educazione al marketing",
            "topic": "3 errori comuni dei coach sui social",
            "goal": "Aumentare la reach e attirare coach in target",
        },
        {
            "week": 1,
            "day": "Giovedì",
            "platform": "Instagram",
            "format": "Carosello",
            "pillar": "Educazione al marketing",
            "topic": "Come costruire un profilo Instagram che converte",
            "goal": "Posizionarsi come esperto",
        },
    ],
}


# ── generate_strategy ──────────────────────────────────────────────────────────

@patch("competitor_analysis.analysis.strategy_generator._call_claude")
def test_generate_strategy_returns_marketing_strategy(
    mock_claude,
    sample_profile: ProfileSummary,
    sample_row: CompetitorRow,
    sample_target_analysis: TargetAnalysis,
):
    mock_claude.return_value = json.dumps(_CANNED_STRATEGY)
    strategy = generate_strategy(
        objective="Acquisire 10 nuovi clienti coach in 3 mesi",
        profile=sample_profile,
        competitors=[sample_row],
        target_analysis=sample_target_analysis,
    )
    assert isinstance(strategy, MarketingStrategy)
    assert strategy.objective == "Acquisire 10 nuovi clienti coach in 3 mesi"
    assert len(strategy.content_pillars) == 1
    assert isinstance(strategy.content_pillars[0], ContentPillar)
    assert len(strategy.editorial_plan) == 2
    assert isinstance(strategy.editorial_plan[0], EditorialItem)
    assert strategy.editorial_plan[0].week == 1
    assert strategy.editorial_plan[0].platform == "Instagram"


@patch("competitor_analysis.analysis.strategy_generator._call_claude")
def test_generate_strategy_strips_json_fence(
    mock_claude,
    sample_profile: ProfileSummary,
    sample_row: CompetitorRow,
    sample_target_analysis: TargetAnalysis,
):
    """Claude sometimes wraps output in ```json ... ``` fences."""
    fenced = "```json\n" + json.dumps(_CANNED_STRATEGY) + "\n```"
    mock_claude.return_value = fenced
    strategy = generate_strategy(
        objective="Acquisire 10 nuovi clienti coach in 3 mesi",
        profile=sample_profile,
        competitors=[sample_row],
        target_analysis=sample_target_analysis,
    )
    assert strategy.objective == "Acquisire 10 nuovi clienti coach in 3 mesi"
    assert len(strategy.content_pillars) == 1


@patch("competitor_analysis.analysis.strategy_generator._call_claude")
def test_generate_strategy_with_priority_platform(
    mock_claude,
    sample_profile: ProfileSummary,
    sample_row: CompetitorRow,
    sample_target_analysis: TargetAnalysis,
):
    mock_claude.return_value = json.dumps(_CANNED_STRATEGY)
    generate_strategy(
        objective="Crescere su LinkedIn",
        profile=sample_profile,
        competitors=[sample_row],
        target_analysis=sample_target_analysis,
        timeframe="6 mesi",
        priority_platform="LinkedIn",
    )
    # Verify the prompt passed to Claude mentions the platform
    call_args = mock_claude.call_args
    user_prompt = call_args[0][1]
    assert "LinkedIn" in user_prompt
    assert "6 mesi" in user_prompt


@patch("competitor_analysis.analysis.strategy_generator._call_claude")
def test_generate_strategy_empty_competitors(
    mock_claude,
    sample_profile: ProfileSummary,
    sample_target_analysis: TargetAnalysis,
):
    mock_claude.return_value = json.dumps(_CANNED_STRATEGY)
    strategy = generate_strategy(
        objective="Test",
        profile=sample_profile,
        competitors=[],
        target_analysis=sample_target_analysis,
    )
    assert isinstance(strategy, MarketingStrategy)


# ── strategy_to_markdown ───────────────────────────────────────────────────────

def _make_strategy() -> MarketingStrategy:
    return MarketingStrategy(
        **{
            **_CANNED_STRATEGY,
            "content_pillars": [ContentPillar(**p) for p in _CANNED_STRATEGY["content_pillars"]],
            "editorial_plan": [EditorialItem(**i) for i in _CANNED_STRATEGY["editorial_plan"]],
        }
    )


def test_strategy_to_markdown_contains_objective():
    md = strategy_to_markdown(_make_strategy())
    assert "Acquisire 10 nuovi clienti coach in 3 mesi" in md


def test_strategy_to_markdown_contains_section_headers():
    md = strategy_to_markdown(_make_strategy())
    assert "## Sintesi strategica" in md
    assert "## Posizionamento" in md
    assert "## Messaggi chiave" in md
    assert "## Piano editoriale" in md


def test_strategy_to_markdown_contains_editorial_plan_row():
    md = strategy_to_markdown(_make_strategy())
    assert "Lunedì" in md
    assert "Reel" in md
    assert "Educazione al marketing" in md


def test_strategy_to_markdown_groups_by_week():
    md = strategy_to_markdown(_make_strategy())
    assert "### Settimana 1" in md


# ── model round-trips ──────────────────────────────────────────────────────────

def test_marketing_strategy_roundtrip():
    strategy = _make_strategy()
    data = strategy.model_dump()
    restored = MarketingStrategy(**{
        **data,
        "content_pillars": [ContentPillar(**p) for p in data["content_pillars"]],
        "editorial_plan": [EditorialItem(**i) for i in data["editorial_plan"]],
    })
    assert restored.objective == strategy.objective
    assert len(restored.content_pillars) == len(strategy.content_pillars)
    assert len(restored.editorial_plan) == len(strategy.editorial_plan)


def test_analysis_record_backward_compat(
    sample_profile: ProfileSummary,
    sample_row: CompetitorRow,
):
    """AnalysisRecord without marketing_strategy must still validate (old saved records)."""
    record = AnalysisRecord(
        id="test_001",
        created_at="2026-06-13T10:00:00",
        input_url="https://www.instagram.com/test/",
        profile=sample_profile,
        rows=[sample_row],
    )
    assert record.marketing_strategy is None
    assert record.objective is None
    # Serialize and deserialize as JSON (mimics history.py load path)
    json_str = record.model_dump_json()
    restored = AnalysisRecord.model_validate_json(json_str)
    assert restored.marketing_strategy is None
