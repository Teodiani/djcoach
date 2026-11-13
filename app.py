import hashlib
import io
import json
import re
import base64
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from groq import Groq

# ------------------------------------------------------------
# TEO (DJ Coach) - chat, ricerca online, voce, documenti (CSV, Excel, Word, PDF, TXT, JPG) e download
# ------------------------------------------------------------

st.set_page_config(page_title="Teo", page_icon="🎧", layout="centered")

# ---------- Aspetto grafico (stile Jarvis) ----------
STILE = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@600;800&family=Rajdhani:wght@400;500;600&display=swap');

:root {
  --fondo: #04101c;
  --pannello: #0a1f33;
  --reattore: #4fd8ff;
  --ghiaccio: #e6f6ff;
  --oro: #ffb347;
}

.stApp { background: radial-gradient(circle at 50% 0%, #0b2a45 0%, var(--fondo) 55%); }
html, body, [class*="css"], .stMarkdown, p, li { font-family: 'Rajdhani', sans-serif; color: var(--ghiaccio); font-size: 1.1rem; }

header[data-testid="stHeader"] { background: transparent; }
section[data-testid="stSidebar"] { background: var(--pannello); border-right: 1px solid rgba(79,216,255,.25); }

.testata { display: flex; align-items: center; gap: 18px; padding: 10px 0 18px 0; }
.reattore {
  width: 58px; height: 58px; border-radius: 50%; flex: none;
  border: 3px solid var(--reattore);
  background: radial-gradient(circle, #ffffff 0%, var(--reattore) 38%, transparent 70%);
  box-shadow: 0 0 18px var(--reattore), inset 0 0 14px rgba(79,216,255,.7);
  animation: pulsa 3.2s ease-in-out infinite;
}
@keyframes pulsa {
  0%, 100% { box-shadow: 0 0 10px var(--reattore), inset 0 0 10px rgba(79,216,255,.6); }
  50% { box-shadow: 0 0 28px var(--reattore), inset 0 0 20px rgba(79,216,255,.9); }
}
@media (prefers-reduced-motion: reduce) { .reattore { animation: none; } }

.titolo { font-family: 'Orbitron', sans-serif; font-weight: 800; font-size: 1.7rem; letter-spacing: .08em; color: var(--ghiaccio); line-height: 1.1; }
.sottotitolo { color: var(--reattore); font-size: 1rem; margin-top: 2px; }

[data-testid="stChatMessage"] {
  background: rgba(10,31,51,.85);
  border: 1px solid rgba(79,216,255,.22);
  border-radius: 10px;
}
[data-testid="stChatInput"] textarea { color: var(--ghiaccio); }
.stButton button, .stDownloadButton button { border: 1px solid var(--reattore); background: transparent; color: var(--reattore); font-family: 'Rajdhani', sans-serif; font-weight: 600; }
.stButton button:hover, .stDownloadButton button:hover { background: var(--reattore); color: var(--fondo); border-color: var(--reattore); }
</style>
"""
st.markdown(STILE, unsafe_allow_html=True)

st.markdown(
    """
    <div class="testata">
      <div class="reattore"></div>
      <div>
        <div class="titolo">TEO</div>
        <div class="sottotitolo">Il tuo Co-DJ e consulente musicale personale</div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------- Personalità del DJ Coach ----------
ISTRUZIONI_DI_RISERVA = """Sei Teo, il Co-DJ e consulente musicale personale dell'utente.
Rispondi sempre in italiano, in modo chiaro e conciso."""

REGOLE_TECNICHE = """

Regole tecniche:
- Se ti vengono forniti RISULTATI DI RICERCA WEB, usali come base per i dati aggiornati, indica da quale
  fonte arrivano e non inventare nulla che non sia scritto lì. Se i risultati non bastano, dillo.
- Se ti vengono forniti DOCUMENTI O IMMAGINI CARICATI DALL'UTENTE, usali come fonte principale per le domande
  sulla sua libreria, sulle sue scalette, sui suoi file o sulle immagini/locandine. Se i dati sono stati tagliati, dillo.
- Se l'utente ti chiede di riorganizzare, riscrivere o sistemare un documento, restituisci il testo
  completo già riorganizzato, senza riassumerlo e senza inventare contenuti che non ci sono.
- Se non sei sicuro di un dato (BPM, tonalità, anno), dillo invece di inventare.
"""


def carica_istruzioni():
    """Legge le regole di Teo dal file istruzioni_teo.txt (nella stessa cartella di app.py)."""
    try:
        percorso = Path(__file__).parent / "istruzioni_teo.txt"
        testo = percorso.read_text(encoding="utf-8").strip()
        if testo:
            return testo, True
    except Exception:
        pass
    return ISTRUZIONI_DI_RISERVA, False


TESTO_REGOLE, FILE_CARICATO = carica_istruzioni()
ISTRUZIONI = TESTO_REGOLE + REGOLE_TECNICHE

# ---------- Collegamento al cervello (Groq) ----------
try:
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except Exception:
    st.error(
        "Manca la chiave Groq. Su Streamlit apri Settings > Secrets e inserisci: "
        'GROQ_API_KEY = "la-tua-chiave"'
    )
    st.stop()


@st.cache_data(ttl=3600)
def elenco_modelli():
    """Chiede a Groq quali modelli di chat sono disponibili adesso."""
    escludi = ("whisper", "guard", "tts", "playai", "orpheus", "safeguard")
    try:
        ids = [m.id for m in client.models.list().data]
        ids = [i for i in ids if not any(x in i.lower() for x in escludi)]
        return sorted(ids)
    except Exception:
        return []


# ---------- Ricerca online ----------
def decidi_ricerca(modello, messaggi):
    """Chiede al cervello se serve cercare su internet. Restituisce la ricerca da fare, o '' se non serve."""
    regole = (
        "Sei un filtro. Decidi se per rispondere all'ultimo messaggio dell'utente serve cercare "
        "informazioni aggiornate su internet (nuove uscite, classifiche, date di eventi, notizie, "
        "informazioni su artisti, locali o prodotti specifici, dati che cambiano nel tempo). Cerca SEMPRE per trend, hit del momento, classifiche, Beatport, Spotify, Shazam, DJ chart, suggerimenti mensili di nuovi brani e piani di marketing con costi aggiornati. "
        'Se serve, rispondi SOLO con un oggetto JSON come questo: {"cerca": "query breve di ricerca"}. '
        'Se NON serve (consigli, teoria, mixaggio, conversazione generale, domande o richieste di riorganizzazione sui documenti caricati dall\'utente), rispondi SOLO: {"cerca": ""}. '
        "Oggi e' il " + date.today().strftime("%d/%m/%Y") + "."
    )
    try:
        ultimi = [{"role": m["role"], "content": m["content"]} for m in messaggi[-6:] if isinstance(m["content"], str)]
        r = client.chat.completions.create(
            model=modello,
            messages=[{"role": "system", "content": regole}] + ultimi,
            temperature=0,
            max_tokens=80,
        )
        testo = r.choices[0].message.content or ""
        trovato = re.search(r"\{.*?\}", testo, re.S)
        if trovato:
            return str(json.loads(trovato.group(0)).get("cerca", "")).strip()
    except Exception:
        pass
    return ""
