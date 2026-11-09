import json
import re
from datetime import date

import streamlit as st
from groq import Groq

# ------------------------------------------------------------
# DJ COACH - Fase 2: chat + ricerca online
# ------------------------------------------------------------

st.set_page_config(page_title="DJ Coach", page_icon="🎧", layout="centered")

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
.stButton button { border: 1px solid var(--reattore); background: transparent; color: var(--reattore); font-family: 'Rajdhani', sans-serif; font-weight: 600; }
.stButton button:hover { background: var(--reattore); color: var(--fondo); border-color: var(--reattore); }
</style>
"""
st.markdown(STILE, unsafe_allow_html=True)

st.markdown(
    """
    <div class="testata">
      <div class="reattore"></div>
      <div>
        <div class="titolo">DJ COACH</div>
        <div class="sottotitolo">Il tuo Co-DJ e consulente musicale personale</div>
      </div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------- Personalità del DJ Coach ----------
ISTRUZIONI = """Sei DJ Coach, il Co-DJ e consulente musicale personale dell'utente, in stile Jarvis di Iron Man:
professionale, brillante, un po' ironico, sempre al servizio dell'utente.

Competenze: selezione musicale, costruzione di scaletta e set, mixaggio armonico (ruota di Camelot),
BPM e transizioni, lettura del pubblico, gestione della pista, tecnica e attrezzatura DJ,
generi e storia della musica elettronica e da ballo.

Regole:
- Rispondi sempre in italiano, in modo chiaro e conciso.
- Quando consigli brani, indica se possibile artista, titolo, BPM e tonalità approssimativi, e spiega
  PERCHÉ funzionano insieme.
- Se non sei sicuro di un dato (BPM, tonalità, anno), dillo invece di inventare.
- Fai al massimo una domanda alla volta per capire meglio il contesto (locale, pubblico, durata del set).
- Se ti vengono forniti RISULTATI DI RICERCA WEB, usali come base per i dati aggiornati, indica da quale
  fonte arrivano e non inventare nulla che non sia scritto lì. Se i risultati non bastano, dillo.
"""

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
        "informazioni su artisti, locali o prodotti specifici, dati che cambiano nel tempo). "
        'Se serve, rispondi SOLO con un oggetto JSON come questo: {"cerca": "query breve di ricerca"}. '
        'Se NON serve (consigli, teoria, mixaggio, conversazione generale), rispondi SOLO: {"cerca": ""}. '
        "Oggi e' il " + date.today().strftime("%d/%m/%Y") + "."
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
    """Cerca su DuckDuckGo (gratis, senza chiave). Restituisce (risultati, errore)."""
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
    righe = [f"RISULTATI DI RICERCA WEB (ricerca: '{ricerca}', data di oggi: {date.today().strftime('%d/%m/%Y')}):"]
    for i, r in enumerate(risultati, 1):
        righe.append(f"[{i}] {r.get('title', '')} - {r.get('body', '')} (fonte: {r.get('href', '')})")
    return "\n".join(righe)


def testo_fonti(risultati):
    return "\n".join(f"- [{r.get('title', 'Fonte')}]({r.get('href', '')})" for r in risultati if r.get("href"))


# ---------- Menu laterale ----------
with st.sidebar:
    st.markdown("### Impostazioni")
    modelli = elenco_modelli()
    if modelli:
        preferiti = ("llama-3.3-70b", "gpt-oss-120b", "70b", "120b", "qwen", "llama", "gpt-oss")
        predefinito = 0
        for parola in preferiti:
            trovato = next((i for i, m in enumerate(modelli) if parola in m.lower()), None)
            if trovato is not None:
                predefinito = trovato
                break
        modello = st.selectbox("Cervello (modello)", modelli, index=predefinito)
    else:
        modello = st.text_input("Cervello (modello)", value="llama-3.3-70b-versatile")
    ricerca_attiva = st.toggle("Ricerca online", value=True)
    if st.button("Nuova conversazione"):
        st.session_state.messaggi = []
        st.rerun()

# ---------- Chat ----------
if "messaggi" not in st.session_state:
    st.session_state.messaggi = []

if not st.session_state.messaggi:
    st.markdown("Sono pronto. Dimmi cosa stai preparando: un set, una serata, un nuovo genere da studiare?")

for m in st.session_state.messaggi:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])
        if m.get("fonti"):
            with st.expander("Fonti"):
                st.markdown(m["fonti"])

domanda = st.chat_input("Scrivi al tuo DJ Coach...")

if domanda:
    st.session_state.messaggi.append({"role": "user", "content": domanda})
    with st.chat_message("user"):
        st.markdown(domanda)

    with st.chat_message("assistant"):
        istruzioni = ISTRUZIONI + f"\nOggi è il {date.today().strftime('%d/%m/%Y')}."
        fonti = ""

        if ricerca_attiva:
            with st.spinner("Valuto se serve cercare online..."):
                ricerca = decidi_ricerca(modello, st.session_state.messaggi)
            if ricerca:
                with st.spinner(f"Cerco online: {ricerca}"):
                    risultati, errore = cerca_web(ricerca)
                if risultati:
                    istruzioni += "\n\n" + testo_per_il_cervello(ricerca, risultati)
                    fonti = testo_fonti(risultati)
                else:
                    istruzioni += (
                        "\n\nHai provato a cercare online ma la ricerca non ha dato risultati. "
                        "Dillo all'utente e rispondi solo con ciò che sai con certezza."
                    )

        spazio = st.empty()
        risposta = ""
        try:
            storia = [{"role": m["role"], "content": m["content"]} for m in st.session_state.messaggi[-20:]]
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
            fonti = ""

        if fonti:
            with st.expander("Fonti"):
                st.markdown(fonti)

    st.session_state.messaggi.append({"role": "assistant", "content": risposta, "fonti": fonti})
