from __future__ import annotations

import json

from competitor_analysis.models import ProfileSummary, TargetAnalysis
from competitor_analysis.analysis.competitor_finder import _call_claude

_TARGET_SYSTEM = """\
Sei un esperto di marketing e psicologia del consumatore specializzato nel mercato italiano.
Il tuo compito è analizzare il profilo di un professionista (coach, counselor o consulente) \
e identificare le caratteristiche del suo pubblico target compilando una tabella strategica.
Rispondi sempre e solo con JSON valido — nessun markdown, nessuna spiegazione.
"""


def analyze_target(profile: ProfileSummary) -> TargetAnalysis:
    """Use Claude to fill in the target analysis table (Problemi/Obiettivi/Dolore/Desideri)."""
    user_prompt = f"""\
Analizza il seguente profilo professionale e identifica le caratteristiche del suo pubblico target.

Profilo:
- Nome: {profile.name}
- Nicchia: {profile.niche}
- Pubblico target: {profile.target_audience}
- Servizi offerti: {', '.join(profile.services)}
- Mercato geografico: {profile.geographic_scope}
- Bio: {profile.bio}

Compila la seguente tabella strategica per il pubblico target di questo professionista.
Ogni lista deve contenere 5-7 punti specifici e concreti, calibrati sulla nicchia e sul target.

Restituisci un oggetto JSON con questi campi:
- problemi (list[str]): I problemi concreti che il target deve affrontare nel suo quotidiano o lavoro
- obiettivi (list[str]): I risultati e i traguardi che il target vuole raggiungere
- dolore (list[str]): Le frustrazioni emotive profonde, le paure e i blocchi interiori del target
- desideri (list[str]): I sogni, le aspirazioni e i desideri profondi del target

Sii specifico e concreto rispetto alla nicchia "{profile.niche}" e al target "{profile.target_audience}".
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
