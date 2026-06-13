from __future__ import annotations

import json

from competitor_analysis.models import (
    CompetitorRow,
    ContentPillar,
    EditorialItem,
    MarketingStrategy,
    ProfileSummary,
    TargetAnalysis,
)
from competitor_analysis.analysis.competitor_finder import _call_claude

_STRATEGY_SYSTEM = """\
Sei un esperto di strategia di marketing digitale per il mercato italiano, \
specializzato nel posizionamento organico sui social media.

Il tuo compito è definire una strategia di marketing concreta e personalizzata \
basandoti su:
  1. Il profilo del professionista e il suo obiettivo dichiarato
  2. Il panorama competitivo (competitor diretti, loro punti di forza/debolezza)
  3. L'analisi del target (problemi, obiettivi, dolore, desideri dei clienti potenziali)

La strategia deve essere:
  - Specifica rispetto alla nicchia, non generica
  - Differenziante rispetto ai competitor analizzati
  - Radicata nei bisogni reali del target
  - Immediatamente azionabile

Rispondi sempre e solo con JSON valido — nessun markdown, nessuna spiegazione aggiuntiva.
"""


def _compact_competitors(rows: list[CompetitorRow], max_rows: int = 8) -> str:
    """Render the competitor list as a concise text block for the prompt."""
    lines: list[str] = []
    for row in rows[:max_rows]:
        follower_parts = [
            f"{p}: {v}"
            for p, v in row.kpis.follower_count.items()
            if v and v != "N/A"
        ]
        follower_str = ", ".join(follower_parts) if follower_parts else "dati follower N/A"

        structure_flags = [
            k.replace("_", " ")
            for k, v in row.kpis.structure.items()
            if v
        ]
        structure_str = ", ".join(structure_flags) if structure_flags else "nessuna struttura segnalata"

        lines.append(
            f"- {row.name}: {row.description} | "
            f"Follower: {follower_str} | "
            f"Struttura: {structure_str} | "
            f"Engagement: {row.kpis.interaction_score} | "
            f"Perché competitor: {row.why_competitor}"
        )
    return "\n".join(lines)


def generate_strategy(
    objective: str,
    profile: ProfileSummary,
    competitors: list[CompetitorRow],
    target_analysis: TargetAnalysis,
    *,
    timeframe: str = "3 mesi",
    priority_platform: str | None = None,
) -> MarketingStrategy:
    """Generate a full marketing strategy grounded in competitor + target data.

    Returns a :class:`MarketingStrategy` that includes a 2-4 week editorial plan.
    """
    platform_hint = (
        f"\nPiattaforma prioritaria su cui concentrarsi: **{priority_platform}**."
        if priority_platform
        else ""
    )

    competitor_block = _compact_competitors(competitors) if competitors else "Nessun competitor identificato."

    target_block = (
        f"PROBLEMI: {'; '.join(target_analysis.problemi)}\n"
        f"OBIETTIVI: {'; '.join(target_analysis.obiettivi)}\n"
        f"DOLORE: {'; '.join(target_analysis.dolore)}\n"
        f"DESIDERI: {'; '.join(target_analysis.desideri)}"
    )

    user_prompt = f"""\
Definisci una strategia di marketing completa per il seguente professionista.

═══ OBIETTIVO DICHIARATO ═══
{objective}
Orizzonte temporale: {timeframe}{platform_hint}

═══ PROFILO DEL PROFESSIONISTA ═══
Nome: {profile.name}
Nicchia: {profile.niche}
Target dichiarato: {profile.target_audience}
Servizi: {", ".join(profile.services)}
Mercato geografico: {profile.geographic_scope}
Valori del brand: {", ".join(profile.brand_values) if profile.brand_values else "non specificati"}
Bio: {profile.bio}

═══ PANORAMA COMPETITIVO (competitor diretti identificati) ═══
{competitor_block}

═══ ANALISI DEL TARGET (clienti potenziali) ═══
{target_block}

═══ ISTRUZIONI ═══
Produci una strategia che:
- Definisce un posizionamento chiaro e differenziante rispetto ai competitor elencati
- Radica i messaggi chiave e i pilastri di contenuto nei problemi/dolore/desideri del target
- Propone 3-5 pilastri di contenuto concreti (non generici) con 3-5 idee di topic per ciascuno
- Include la strategia di canale (quali piattaforme, perché, con quale frequenza)
- Suggerisce azioni concrete e prioritarie
- Definisce KPI misurabili coerenti con l'obiettivo

Includi anche un piano editoriale di 2-4 settimane con post/reel/caroselli/storie concrete, \
mappate sui pilastri di contenuto, che rispettino la strategia di canale.

Restituisci un oggetto JSON con esattamente questi campi:
- objective (str): l'obiettivo dichiarato (copialo invariato)
- summary (str): sintesi della strategia in 2-3 frasi
- positioning (str): il posizionamento proposto (1-2 frasi precise)
- differentiation (list[str]): 3-5 elementi di differenziazione concreti vs i competitor
- target_focus (str): descrizione focalizzata del cliente ideale da raggiungere
- key_messages (list[str]): 4-6 messaggi chiave da comunicare
- content_pillars (list[object]): 3-5 pilastri, ciascuno con:
    - title (str)
    - description (str)
    - sample_topics (list[str]): 3-5 idee concrete di contenuto
- channel_strategy (list[str]): una voce per piattaforma consigliata con frequenza e tipo di contenuto
- recommended_actions (list[str]): 5-8 azioni prioritarie nell'ordine suggerito
- kpis (list[str]): 4-6 KPI misurabili
- editorial_plan (list[object]): piano editoriale 2-4 settimane, ciascun item con:
    - week (int): numero settimana (1-4)
    - day (str): giorno della settimana in italiano
    - platform (str): piattaforma
    - format (str): formato del contenuto (Reel, Carosello, Post, Storia, Video, ecc.)
    - pillar (str): titolo del pilastro di appartenenza
    - topic (str): idea concreta / hook del contenuto
    - goal (str): obiettivo specifico di quel contenuto

Restituisci solo il JSON.
"""

    raw = _call_claude(_STRATEGY_SYSTEM, user_prompt)
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()

    data = json.loads(cleaned)
    # Deserialize nested objects
    data["content_pillars"] = [ContentPillar(**p) for p in data.get("content_pillars", [])]
    data["editorial_plan"] = [EditorialItem(**item) for item in data.get("editorial_plan", [])]
    return MarketingStrategy(**data)
