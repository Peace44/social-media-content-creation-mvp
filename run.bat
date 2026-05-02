@echo off
title Kolif Agency — Competitor Analysis
color 0A

echo.
echo  ================================================
echo    Kolif Agency ^| Competitor Analysis
echo  ================================================
echo.

REM ── Check Python ──────────────────────────────────
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERRORE] Python non trovato sul tuo computer.
    echo.
    echo  Vai su https://www.python.org/downloads/
    echo  Scarica la versione piu' recente e installala.
    echo  IMPORTANTE: spunta la casella "Add Python to PATH"
    echo  durante l'installazione, poi riavvia il computer.
    echo.
    pause
    exit /b 1
)

REM ── Check Git ─────────────────────────────────────
git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo  [ERRORE] Git non trovato sul tuo computer.
    echo.
    echo  Vai su https://git-scm.com/download/win
    echo  Scarica e installa Git, poi riavvia il computer.
    echo.
    pause
    exit /b 1
)

REM ── Check .env ────────────────────────────────────
if not exist ".env" (
    echo  [ERRORE] File .env non trovato.
    echo.
    echo  Chiedi a Peace di mandarti il file .env
    echo  e copialo nella stessa cartella di questo script.
    echo.
    pause
    exit /b 1
)

REM ── Pull aggiornamenti ────────────────────────────
echo  [1/4] Scarico aggiornamenti...
git pull
if %errorlevel% neq 0 (
    echo  [ATTENZIONE] Impossibile scaricare aggiornamenti.
    echo  L'app si avviera' con la versione precedente.
)
echo.

REM ── Ambiente virtuale ─────────────────────────────
if not exist ".venv" (
    echo  [2/4] Creo ambiente virtuale (solo la prima volta^)...
    python -m venv .venv
) else (
    echo  [2/4] Ambiente virtuale OK.
)
echo.

REM ── Dipendenze ────────────────────────────────────
echo  [3/4] Aggiorno le dipendenze...
.venv\Scripts\pip install -r requirements.txt -q --disable-pip-version-check
.venv\Scripts\pip install -e . -q --disable-pip-version-check
echo.

REM ── Playwright browser ────────────────────────────
echo  [4/4] Installo il browser interno (la prima volta ci vuole qualche minuto^)...
.venv\Scripts\python -m playwright install chromium
echo.

REM ── Avvio ─────────────────────────────────────────
echo  Tutto pronto! Avvio l'applicazione...
echo  Apri il browser e vai su: http://localhost:8501
echo  Per chiuderla premi CTRL+C in questa finestra.
echo.

.venv\Scripts\streamlit run app.py --server.headless true

pause
