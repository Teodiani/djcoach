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
        <div class="sottotitolo">Il tuo Co-DJ e consulente musicale personale</div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

ISTRUZIONI_DI_RISERVA = "Sei Teo, il Co-DJ e consulente musicale personale dell'utente. Rispondi sempre in italiano, in modo chiaro e conciso."

REGOLE_TECNICHE = "Regole tecniche: - Se ti vengono forniti RISULTATI DI RICERCA WEB, usali come base per i dati aggiornati. - Se ti vengono forniti DOCUMENTI o IMMAGINI CARICATI DALL'UTENTE, usali come fonte principale."

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
    client = Groq(api_key=st.secrets["GROQ_API_KEY"])
except Exception:
    st.error("Manca la chiave Groq. Su Streamlit apri Settings > Secrets e inserisci: GROQ_API_KEY = 'la-tua-chiave'")
    st.stop()

# --- LISTA MODELLI ULTRA-SICURA (SENZA MODELLI PENSIONATI) ---
MODELLI_SICURI = [
    "llama-3.1-8b-instant",         # Veloce, leggero e sempre attivo
    "mixtral-8x7b-32768",           # Il migliore per testi lunghi e scalette, stabilissimo
    "llama-3.2-11b-vision-preview", # Indispensabile per fargli leggere le immagini .jpg
    "llama-3.2-90b-vision-preview", # Visione super avanzata
    "gemma2-9b-it"                  # Alternativa di casa Google molto solida
]

def decidi_ricerca(modello, messaggi):
    regole = "Sei un filtro. Decidi se per rispondere all'ultimo messaggio dell'utente serve cercare informazioni aggiornate su internet. Rispondi SOLO con un oggetto JSON: {'cerca': 'query breve'} oppure {'cerca': ''} se non serve."
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
    immagini_payload = []
    avvisi = []
    
    for f in files:
        ext = f.name.lower()
        if ext.endswith((".jpg", ".jpeg", ".png", ".webp")):
            import base64
            encoded = base64.b64encode(f.getvalue()).decode("utf-8")
            mime = "image/jpeg" if ext in [".jpg", ".jpeg"] else f"image/{ext.replace('.', '')}"
            immagini_payload.append({
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{encoded}"}
            })
        else:
            try:
                testo, info = estrai_testo(f.name, f.getvalue())
                testi_documenti.append(f"FILE '{f.name}' ({info}):\n{testo}")
            except Exception as e:
                avvisi.append(f"{f.name}: errore di lettura ({e}).")
                
    contesto_testo = "\n\n".join(testi_documenti)
    if contesto_testo:
        contesto_testo = "DOCUMENTI CARICATI:\n\n" + contesto_testo
        
    return contesto_testo, immagini_payload, avvisi

def crea_docx(testo):
    try:
        from docx import Document
    except ImportError:
        return None
    d = Document()
    for riga in testo.split("\n"):
        d.add_paragraph(riga)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()

def pulsanti_scarica(testo, chiave):
    with st.expander("⬇️ Scarica risposta"):
        dati_word = crea_docx(testo)
        if dati_word:
            st.download_button("Word (.docx)", data=dati_word, file_name="teo_risposta.docx", key=f"word_{chiave}")
        st.download_button("Testo (.txt)", data=testo.encode("utf-8"), file_name="teo_risposta.txt", key=f"txt_{chiave}")

def trascrivi(dati_audio):
    try:
        r = client.audio.transcriptions.create(
            file=("voce.wav", dati_audio),
            model="whisper-large-v3-turbo",
            language="it",
        )
        return (getattr(r, "text", "") or "").strip(), ""
    except Exception as errore:
        return "", str(errore)

MODELLO_VOCE = """<div style="display:flex; gap:8px;"><button id="ascolta" style="padding:6px 14px; border:1px solid #4fd8ff; background:transparent; color:#4fd8ff; border-radius:6px; cursor:pointer;">🔊 Ascolta</button><button id="ferma" style="padding:6px 14px; border:1px solid #4fd8ff; background:transparent; color:#4fd8ff; border-radius:6px; cursor:pointer;">⏹ Stop</button></div><script>const testo = __TESTO__; function parla() { if (!window.speechSynthesis) { return; } window.speechSynthesis.cancel(); const u = new SpeechSynthesisUtterance(testo); u.lang = 'it-IT'; window.speechSynthesis.speak(u); } document.getElementById('ascolta').onclick = parla; document.getElementById('ferma').onclick = () => window.speechSynthesis.cancel(); if (__AUTO__) { setTimeout(parla, 300); }</script>"""

def voce_html(testo, automatica=False):
    pulito = re.sub(r"https?://\S+", " ", testo)
    pulito = re.sub(r"[*_#`>~|]", " ", pulito).strip()
    js = json.dumps(pulito).replace("</", "<\\/")
    html = MODELLO_VOCE.replace("__TESTO__", js).replace("__AUTO__", "true" if automatica else "false")
    components.html(html, height=50)

# ==================== MENU LATERALE ====================
with st.sidebar:
    st.markdown("### Impostazioni")
    
    modello = st.selectbox(
        "Cervello (modello)", 
        MODELLI_SICURI, 
        index=0,
        help="Usa llama-3.1-8b o mixtral per chattare, oppure i modelli Vision per fargli leggere foto e locandine."
    )

    ricerca_attiva = st.toggle("Ricerca online", value=True)
    microfono_attivo = st.toggle("Microfono (parli tu)", value=True)
    voce_attiva = st.toggle("Risposta a voce", value=True)

    file_caricati = st.file_uploader(
        "Carica file o immagini (CSV, Excel, PDF, TXT, JPG, PNG)",
        type=["csv", "xlsx", "xlsm", "docx", "pdf", "txt", "md", "jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True,
    )
    
    contesto_documenti = ""
    immagini_per_ia = []
    if file_caricati:
        contesto_documenti, immagini_per_ia, avvisi = elabora_file_caricati(file_caricati)
        for avviso in avvisi:
            st.warning(avviso)

    st.caption("Regole di Teo: file istruzioni_teo.txt letto ✅" if FILE_CARICATO else "Regole di Teo: file base ⚠️")
    if st.button("Nuova conversazione"):
        st.session_state.messaggi = []
        st.rerun()

# ==================== CHAT PRINCIPALE ====================
if "messaggi" not in st.session_state:
    st.session_state.messaggi = []
if "ultimo_audio" not in st.session_state:
    st.session_state.ultimo_audio = ""

zona_storia = st.container()
zona_microfono = st.container()

testo_vocale = ""
if microfono_attivo:
    with zona_microfono:
        registrazione = st.audio_input("🎙️ Tocca per parlare")
        if registrazione is not None:
            dati = registrazione.getvalue()
            impronta = hashlib.md5(dati).hexdigest()
            if impronta != st.session_state.ultimo_audio:
                st.session_state.ultimo_audio = impronta
                with st.spinner("Ti ascolto..."):
                    testo_vocale, _ = trascrivi(dati)

domanda = st.chat_input("Scrivi a Teo...")
if testo_vocale:
    domanda = testo_vocale

with zona_storia:
    if not st.session_state.messaggi:
        st.markdown("Ciao, sono Teo, il tuo Co-DJ. Scegli il modello a sinistra, carica un documento o un'immagine `.jpg` oppure scrivimi qui sotto!")

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

            if ricerca_attiva:
                with st.spinner("Controllo se serve cercare online..."):
                    ricerca = decidi_ricerca(modello, st.session_state.messaggi)
                if ricerca:
                    with st.spinner(f"Cerco online: {ricerca}"):
                        risultati, _ = cerca_web(ricerca)
                    if risultati:
                        istruzioni += "\n\n" + testo_per_il_cervello(ricerca, risultati)
                        fonti = testo_fonti(risultati)

            spazio = st.empty()
            risposta = ""
            try:
                storia = []
                for m in st.session_state.messaggi[-20:]:
                    content_msg = m["content"]
                    if m["role"] == "user" and m == st.session_state.messaggi[-1] and immagini_per_ia:
                        content_msg = [{"type": "text", "text": m["content"]}] + immagini_per_ia
                    storia.append({"role": m["role"], "content": content_msg})

                flusso = client.chat.completions.create(
                    model=modello,
                    messages=[{"role": "system", "content": istruzioni}] + storia,
                    stream=True,
                )
                for pezzo in flusso:
                    risposta += pezzo.choices[0].delta.content or ""
                    spazio.markdown(risposta + "▌")
                spazio.markdown(risposta)
            except Exception as errore:
                risposta = f"Non riesco a rispondere: {errore}"
                spazio.error(risposta)

            if fonti:
                with st.expander("Fonti"):
                    st.markdown(fonti)

            if voce_attiva and not risposta.startswith("Non riesco"):
                voce_html(risposta, automatica=True)

        st.session_state.messaggi.append({"role": "assistant", "content": risposta, "fonti": fonti})
