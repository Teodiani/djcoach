import streamlit as st
from groq import Groq

# ------------------------------------------------------------
# DJ COACH - Fase 1: chat con il tuo Co-DJ
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


with st.sidebar:
    st.markdown("### Impostazioni")
    modelli = elenco_modelli()
    if modelli:
        predefinito = next((i for i, m in enumerate(modelli) if "70b" in m), 0)
        modello = st.selectbox("Cervello (modello)", modelli, index=predefinito)
    else:
        modello = st.text_input("Cervello (modello)", value="llama-3.3-70b-versatile")
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

domanda = st.chat_input("Scrivi al tuo DJ Coach...")

if domanda:
    st.session_state.messaggi.append({"role": "user", "content": domanda})
    with st.chat_message("user"):
        st.markdown(domanda)

    with st.chat_message("assistant"):
        spazio = st.empty()
        risposta = ""
        try:
            conversazione = [{"role": "system", "content": ISTRUZIONI}] + st.session_state.messaggi[-20:]
            flusso = client.chat.completions.create(
                model=modello, messages=conversazione, stream=True
            )
            for pezzo in flusso:
                risposta += pezzo.choices[0].delta.content or ""
                spazio.markdown(risposta + "▌")
            spazio.markdown(risposta)
        except Exception as errore:
            risposta = f"Non riesco a rispondere: {errore}"
            spazio.error(risposta)

    st.session_state.messaggi.append({"role": "assistant", "content": risposta})
