#!/bin/bash
# Kolif Agency — Competitor Analysis — avvio per Mac/Linux

set -e

echo ""
echo " ================================================"
echo "   Kolif Agency | Competitor Analysis"
echo " ================================================"
echo ""

# ── Check Python ──────────────────────────────────
if ! command -v python3 &>/dev/null; then
    echo " [ERRORE] Python non trovato sul tuo computer."
    echo ""
    echo " Su Mac: scarica Python da https://www.python.org/downloads/"
    echo " oppure installa Homebrew (brew.sh) e poi: brew install python"
    echo ""
    exit 1
fi

# ── Check Git ─────────────────────────────────────
if ! command -v git &>/dev/null; then
    echo " [ERRORE] Git non trovato sul tuo computer."
    echo ""
    echo " Su Mac: apri il Terminale e digita:  xcode-select --install"
    echo ""
    exit 1
fi

# ── Check .env ────────────────────────────────────
if [ ! -f ".env" ]; then
    echo " [ERRORE] File .env non trovato."
    echo ""
    echo " Chiedi a Peace di mandarti il file .env"
    echo " e copialo nella stessa cartella di questo script."
    echo ""
    exit 1
fi

# ── Pull aggiornamenti ────────────────────────────
echo " [1/4] Scarico aggiornamenti..."
git pull || echo " [ATTENZIONE] Impossibile scaricare aggiornamenti. Si avvia la versione precedente."
echo ""

# ── Ambiente virtuale ─────────────────────────────
if [ ! -d ".venv" ]; then
    echo " [2/4] Creo ambiente virtuale (solo la prima volta)..."
    python3 -m venv .venv
else
    echo " [2/4] Ambiente virtuale OK."
fi
echo ""

# ── Dipendenze ────────────────────────────────────
echo " [3/4] Aggiorno le dipendenze..."
.venv/bin/pip install --upgrade pip -q
.venv/bin/pip install -r requirements.txt -q
.venv/bin/pip install -e . -q
echo ""

# ── Playwright browser ────────────────────────────
echo " [4/4] Controllo il browser interno..."
.venv/bin/python -m playwright install chromium &>/dev/null
echo ""

# ── Avvio ─────────────────────────────────────────
echo " Tutto pronto! Avvio l'applicazione..."
echo " Si aprira' automaticamente nel tuo browser."
echo " Per chiuderla premi CTRL+C in questa finestra."
echo ""

.venv/bin/streamlit run app.py
