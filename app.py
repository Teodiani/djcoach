import hashlib
import io
import json
import re
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from groq import Groq

# ------------------------------------------------------------
# TEO (DJ Coach) - chat, ricerca online, voce, documenti e immagini
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
.sottotitolo { color: var(--reattore); font-size: 1.0rem; margin-top: 2px; }

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
- Se ti vengono forniti RISULTATI DI RICERCA WEB, usali come base per i dati aggiornati.
- Se ti vengono forniti DOCUMENTI o IMMAGINI CARICATI DALL'UTENTE, usali come fonte principale.
"""


def carica_istruzioni():
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


# ---------- Lista modelli aggiornata e sicura su Groq ----------
MODELLI_SICURI = [
    "llama3-70b-8192",              # Altissima qualità e stabilità garantita
    "llama-3.2-11b-vision-preview",   # Per leggere immagini e file .jpg
    "llama-3.2-90b-vision-preview",   # Visione avanzata
    "mixtral-8x7b-32768"            # Ottimo per testi lunghi
]


# ---------- Ricerca online ----------
def decidi_ricerca(modello, messaggi):
    regole = (
        "Sei un filtro. Decidi se per rispondere all'ultimo messaggio dell'utente serve cercare "
        "informazioni aggiornate su internet. Rispondi SOLO con un oggetto JSON: {'cerca': 'query breve'} "
        "oppure {'cerca': ''} se non serve. Oggi e' il " + date.today().strftime("%d/%m/%Y") + "."
    )
    try:
        ultimi = [{"role": m["role"], "content": m["content"]} for m in messaggi[-6:]]
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


def cerca_web(ricerca):
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS
        risultati = DDGS().text(ricerca, region="it-it", max_results=6)
        return list(risultati or []), ""
    except Exception as errore:
        return [], str(errore)


def testo_per_il_cervello(ricerca, risultati):
    righe = [f"RISULTATI DI RICERCA WEB (ricerca: '{ricerca}'):"]
    for i, r in enumerate(risultati, 1):
        righe.append(f"[{i}] {r.get('title', '')} - {r.get('body', '')} (fonte: {r.get('href', '')})")
    return "\n".join(righe)


def testo_fonti(risultati):
    return "\n".join(f"- [{r.get('title', 'Fonte')}]({r.get('href', '')})" for r in risultati if r.get("href"))


# ---------- Gestione Documenti e Immagini ----------
def leggi_csv(dati):
    for codifica in ("utf-8", "latin-1"):
        try:
            return pd.read_csv(io.BytesIO(dati), sep=None, engine="python", encoding=codifica)
        except Exception:
            continue
    raise ValueError("CSV non leggibile")


def decodifica_testo(dati):
    for codifica in ("utf-8", "latin-1"):
        try:
            return dati.decode(codifica)
        except Exception:
            continue
    return dati.decode("utf-8", errors="ignore")


@st.cache_data(show_spinner=False)
def estrai_testo(nome, dati):
    n = nome.lower()
    if n.endswith(".csv"):
        df = leggi_csv(dati)
        return df.to_csv(index=False), f"CSV, {len(df)} righe"
    if n.endswith((".xlsx", ".xlsm")):
