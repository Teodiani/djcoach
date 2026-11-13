import io
import json
import re
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from openai import OpenAI

st.set_page_config(page_title="Teo", page_icon="🎧", layout="centered")

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
        <div class="sottotitolo">Il tuo Co-DJ e consulente musicale (Locale)</div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

ISTRUZIONI_DI_RISERVA = "Sei Teo, il Co-DJ e consulente musicale personale dell'utente. Rispondi sempre in italiano, in modo chiaro e conciso."
REGOLE_TECNICHE = "Regole tecniche: - Se ti vengono forniti RISULTATI DI RICERCA WEB, usali come base per i dati aggiornati. - Se ti vengono forniti DOCUMENTI CARICATI DALL'UTENTE, usali come fonte principale."

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
ISTRUZIONI = TESTO_REGOLE + "\n" + REGOLE_TECNICHE

try:
