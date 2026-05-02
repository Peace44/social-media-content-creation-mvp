from __future__ import annotations

import json

from competitor_analysis.models import ProfileSummary, TargetAnalysis
from competitor_analysis.analysis.competitor_finder import _call_claude

_TARGET_SYSTEM = """\
Sei un esperto di marketing e psicologia del consumatore specializzato nel mercato italiano.

Il tuo compito è compilare la tabella strategica del CLIENTE POTENZIALE (target), \
ovvero le persone che potrebbero acquistare i servizi del professionista analizzato.

ATTENZIONE — distinzione fondamentale:
- TARGET = i clienti potenziali (chi compra o potrebbe comprare)
- NON analizzare il professionista stesso
- NON analizzare i competitor (altri professionisti rivali)

Ogni punto deve descrivere esclusivamente la realtà, le emozioni e i desideri \
dei CLIENTI POTENZIALI, non di chi offre il servizio.
Rispondi sempre e solo con JSON valido — nessun markdown, nessuna spiegazione.
"""


def analyze_target(profile: ProfileSummary) -> TargetAnalysis:
    """Fill in the target analysis table (Problemi/Obiettivi/Dolore/Desideri) for potential clients."""
    user_prompt = f"""\
Stai analizzando i CLIENTI POTENZIALI (target) di un professionista — \
le persone reali che cercano e acquistano i suoi servizi.

NON stai analizzando il professionista stesso, né i suoi competitor.

Profilo del professionista (usato solo come contesto per capire il suo mercato):
- Nome: {profile.name}
- Nicchia: {profile.niche}
- Clienti target dichiarati: {profile.target_audience}
- Servizi offerti: {', '.join(profile.services)}
- Mercato geografico: {profile.geographic_scope}
- Bio: {profile.bio}

Compila la tabella strategica per i CLIENTI POTENZIALI di questo professionista.
Mettiti nei panni di chi cerca e compra questi servizi — non di chi li vende.
Ogni lista deve contenere 5-7 punti specifici, concreti e psicologicamente precisi.

Restituisci un oggetto JSON con questi campi:
- problemi (list[str]): I problemi pratici e quotidiani che spingono il cliente a cercare questi servizi
- obiettivi (list[str]): I risultati concreti che il cliente vuole ottenere acquistando questi servizi
- dolore (list[str]): Le frustrazioni emotive, le paure e i blocchi interiori che il cliente sente prima di comprare
- desideri (list[str]): I sogni, le aspirazioni e la vita che il cliente immagina dopo aver risolto il problema

Sii specifico rispetto alla nicchia "{profile.niche}" e al tipo di cliente "{profile.target_audience}".
Restituisci solo il JSON.
"""
    raw = _call_claude(_TARGET_SYSTEM, user_prompt)
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()

    data = json.loads(cleaned)
    return TargetAnalysis(**data)
