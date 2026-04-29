# Come avviare l'applicazione sul tuo computer

---

## Prima di tutto (una volta sola)

Devi installare due programmi gratuiti. Fallo solo la prima volta.

### 1 — Python

1. Vai su **https://www.python.org/downloads/**
2. Clicca sul pulsante giallo di download
3. Apri il file scaricato
4. **IMPORTANTE:** spunta la casella **"Add Python to PATH"** (in basso nella finestra)
5. Clicca *Install Now* e aspetta
6. Riavvia il computer

### 2 — Git

**Windows:**
1. Vai su **https://git-scm.com/download/win**
2. Scarica e installa (clicca *Next* su tutto, non serve cambiare nulla)
3. Riavvia il computer

**Mac:**
1. Apri il Terminale (cercalo con Spotlight: `Cmd + Spazio`, scrivi *Terminale*)
2. Digita questo comando e premi Invio:
   ```
   xcode-select --install
   ```
3. Segui le istruzioni a schermo

### 3 — La cartella del progetto

Peace ti manderà un comando da copiare. Sarà simile a questo:

```
git clone https://Peace44:IL_TOKEN@github.com/Peace44/social-media-content-creation-mvp.git %USERPROFILE%\Desktop\kolif-app
```

Per eseguirlo:
1. Premi **Win + R**, scrivi `cmd` e premi Invio
2. Incolla il comando (tasto destro → Incolla) e premi Invio
3. Aspetta che finisca — comparirà la cartella `kolif-app` sul Desktop

### 4 — Il file .env (le chiavi API)

Chiedi a Peace di mandarti il file `.env`.  
Copialo **dentro la cartella del progetto** (quella che contiene `run.bat` o `run.sh`).

---

## Ogni volta che vuoi vedere la versione aggiornata

### Windows

1. Apri la cartella del progetto
2. Fai **doppio clic** su **`run.bat`**
3. Si apre una finestra nera — aspetta (la prima volta ci vuole qualche minuto)
4. Il browser si apre da solo con l'applicazione

### Mac

1. Apri il Terminale
2. Trascina la cartella del progetto nella finestra del Terminale  
   (questo scrive automaticamente il percorso corretto)
3. Premi Invio, poi digita:
   ```
   bash run.sh
   ```
4. Premi Invio e aspetta — il browser si apre da solo

---

## Per chiudere l'applicazione

Torna nella finestra nera (Windows) o nel Terminale (Mac) e premi **CTRL + C**.

---

## Qualcosa non funziona?

Manda uno screenshot della finestra nera / del Terminale a Peace.
