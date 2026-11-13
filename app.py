import io
import json
import re
from datetime import date
from pathlib import Path

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from openai import OpenAI

st.set_page_config(page_title="Teo", page_icon="🎧", layout="centered", initial_sidebar_state="expanded")

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
    client_locale = OpenAI(
        api_key="not-needed",
        base_url="http://localhost:1234/v1"
    )
except Exception:
    client_locale = None

def cerca_web(ricerca):
    try:
        from duckduckgo_search import DDGS
        risultati = DDGS().text(ricerca, region="it-it", max_results=5)
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
        fogli = pd.read_excel(io.BytesIO(dati), sheet_name=None)
        parti = []
        for nome_foglio, df in fogli.items():
            parti.append(f"--- Foglio '{nome_foglio}' ---\n{df.to_csv(index=False)}")
        return "\n".join(parti), f"Excel, {len(fogli)} fogli"
    if n.endswith(".docx"):
        from docx import Document
        d = Document(io.BytesIO(dati))
        righe = [p.text.strip() for p in d.paragraphs if p.text.strip()]
        return "\n".join(righe), f"Word, {len(righe)} paragrafi"
    if n.endswith(".pdf"):
        from pypdf import PdfReader
        lettore = PdfReader(io.BytesIO(dati))
        pagine = [(p.extract_text() or "").strip() for p in lettore.pages]
        testo = "\n\n".join(pagine)
        return testo, f"PDF, {len(pagine)} pagine"
    if n.endswith((".txt", ".md")):
        testo = decodifica_testo(dati)
        return testo, f"testo, {len(testo)} caratteri"
    raise ValueError("formato non supportato")

def elabora_file_caricati(files):
    testi_documenti = []
    avvisi = []
    for f in files:
        try:
            testo, info = estrai_testo(f.name, f.getvalue())
            testi_documenti.append(f"FILE '{f.name}' ({info}):\n{testo}")
        except Exception as e:
            avvisi.append(f"{f.name}: errore di lettura ({e}).")
    contesto_testo = "\n\n".join(testi_documenti)
    if contesto_testo:
        contesto_testo = "DOCUMENTI CARICATI:\n\n" + contesto_testo
    return contesto_testo, avvisi

MODELLO_VOCE = """<div style="display:flex; gap:8px;"><button id="ascolta" style="padding:6px 14px; border:1px solid #4fd8ff; background:transparent; color:#4fd8ff; border-radius:6px; cursor:pointer;">🔊 Ascolta</button><button id="ferma" style="padding:6px 14px; border:1px solid #4fd8ff; background:transparent; color:#4fd8ff; border-radius:6px; cursor:pointer;">⏹ Stop</button></div><script>const testo = __TESTO__; function parla() { if (!window.speechSynthesis) { return; } window.speechSynthesis.cancel(); const u = new SpeechSynthesisUtterance(testo); u.lang = 'it-IT'; window.speechSynthesis.speak(u); } document.getElementById('ascolta').onclick = parla; document.getElementById('ferma').onclick = () => window.speechSynthesis.cancel(); if (__AUTO__) { setTimeout(parla, 300); }</script>"""

def voce_html(testo, automatica=False):
    pulito = re.sub(r"https?://\S+", " ", testo)
    pulito = re.sub(r"[*_#`>~|]", " ", pulito).strip()
    js = json.dumps(pulito).replace("</", "<\\/")
    html = MODELLO_VOCE.replace("__TESTO__", js).replace("__AUTO__", "true" if automatica else "false")
    components.html(html, height=50)

# ==================== MENU LATERALE ====================
with st.sidebar:
    st.markdown("### Impostazioni (LM Studio)")
    
    modello_locale = st.text_input("Nome Modello", value="meta-llama-3.1-8b-instruct", help="Nome del modello attivo in LM Studio.")

    ricerca_attiva = st.toggle("Ricerca online", value=True)
    voce_attiva = st.toggle("Risposta a voce", value=True)

    file_caricati = st.file_uploader(
        "Carica file (CSV, Excel, PDF, TXT)",
        type=["csv", "xlsx", "xlsm", "docx", "pdf", "txt", "md"],
        accept_multiple_files=True,
    )
    
    contesto_documenti = ""
    if file_caricati:
        contesto_documenti, avvisi = elabora_file_caricati(file_caricati)
        for avviso in avvisi:
            st.warning(avviso)

    st.caption("Regole di Teo: file istruzioni_teo.txt letto ✅" if FILE_CARICATO else "Regole di Teo: file base ⚠️")
    if st.button("Nuova conversazione"):
        st.session_state.messaggi = []
        st.rerun()

# ==================== CHAT PRINCIPALE ====================
if "messaggi" not in st.session_state:
    st.session_state.messaggi = []

zona_storia = st.container()
domanda = st.chat_input("Scrivi a Teo...")

with zona_storia:
    if not st.session_state.messaggi:
        st.markdown("Ciao, sono Teo, il tuo Co-DJ in versione **Locale** (alimentato da LM Studio sul tuo PC). Scrivimi qui sotto o carica un file!")

    ultimo = len(st.session_state.messaggi) - 1
    for indice, m in enumerate(st.session_state.messaggi):
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
            if m.get("fonti"):
                with st.expander("Fonti"):
                    st.markdown(m["fonti"])
            if not domanda and indice == ultimo and m["role"] == "assistant":
                if voce_attiva:
                    voce_html(m["content"], automatica=False)

    if domanda:
        st.session_state.messaggi.append({"role": "user", "content": domanda})
        with st.chat_message("user"):
            st.markdown(domanda)

        with st.chat_message("assistant"):
            istruzioni = ISTRUZIONI + f"\nOggi è il {date.today().strftime('%d/%m/%Y')}."
            if contesto_documenti:
                istruzioni += "\n\n" + contesto_documenti
            fonti = ""

            if ricerca_attiva and ("chi è" in domanda.lower() or "notizie" in domanda.lower() or "quando" in domanda.lower()):
                with st.spinner("Cerco online..."):
                    risultati, _ = cerca_web(domanda)
                    if risultati:
                        istruzioni += "\n\n" + testo_per_il_cervello(domanda, risultati)
                        fonti = testo_fonti(risultati)

            spazio = st.empty()
            risposta = ""
            try:
                storia = []
                for m in st.session_state.messaggi[-20:]:
                    storia.append({"role": m["role"], "content": m["content"]})

                flusso = client_locale.chat.completions.create(
                    model=modello_locale if modello_locale else "default",
                    messages=[{"role": "system", "content": istruzioni}] + storia,
                    stream=True,
                )
                for pezzo in flusso:
                    risposta += pezzo.choices[0].delta.content or ""
                    spazio.markdown(risposta + "▌")
                spazio.markdown(risposta)
            except Exception as errore:
                risposta = f"Errore di connessione con LM Studio: {errore}. Assicurati di aver avviato il server su LM Studio (http://localhost:1234)."
                spazio.error(risposta)

            if fonti:
                with st.expander("Fonti"):
                    st.markdown(fonti)

            if voce_attiva and not risposta.startswith("Errore"):
                voce_html(risposta, automatica=True)

        st.session_state.messaggi.append({"role": "assistant", "content": risposta, "fonti": fonti})
