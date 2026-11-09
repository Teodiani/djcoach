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
# TEO (DJ Coach) - chat, ricerca online, voce, documenti (CSV, Excel, Word, PDF, TXT) e download
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
- Se ti vengono forniti DOCUMENTI CARICATI DALL'UTENTE, usali come fonte principale per le domande
  sulla sua libreria, sulle sue scalette o sui suoi file. Se i dati sono stati tagliati, dillo.
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


# ---------- Documenti: lettura di CSV, Excel, Word, PDF, TXT ----------
def leggi_csv(dati):
    """Legge un CSV riconoscendo da solo il separatore (, o ;) e la codifica."""
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
    """Trasforma un file in testo. Restituisce (testo, descrizione)."""
    n = nome.lower()

    if n.endswith(".csv"):
        df = leggi_csv(dati)
        return df.to_csv(index=False), f"CSV, {len(df)} righe, colonne: {', '.join(map(str, df.columns))}"

    if n.endswith((".xlsx", ".xlsm")):
        fogli = pd.read_excel(io.BytesIO(dati), sheet_name=None)  # serve openpyxl
        parti = []
        for nome_foglio, df in fogli.items():
            parti.append(f"--- Foglio '{nome_foglio}' ({len(df)} righe) ---\n{df.to_csv(index=False)}")
        return "\n".join(parti), f"Excel, {len(fogli)} fogli"

    if n.endswith(".docx"):
        from docx import Document  # serve python-docx

        d = Document(io.BytesIO(dati))
        righe = []
        for p in d.paragraphs:
            t = p.text.strip()
            if not t:
                continue
            stile = (p.style.name or "").lower() if p.style is not None else ""
            righe.append(("## " + t) if stile.startswith(("heading", "titolo")) else t)
        for tab in d.tables:
            righe.append("[TABELLA]")
            for riga in tab.rows:
                righe.append(" | ".join(c.text.strip() for c in riga.cells))
        return "\n".join(righe), f"Word, {len(d.paragraphs)} paragrafi, {len(d.tables)} tabelle"

    if n.endswith(".pdf"):
        from pypdf import PdfReader  # serve pypdf

        lettore = PdfReader(io.BytesIO(dati))
        pagine = [(p.extract_text() or "").strip() for p in lettore.pages]
        testo = "\n\n".join(f"[Pagina {i}]\n{t}" for i, t in enumerate(pagine, 1) if t)
        if not testo:
            raise ValueError("PDF senza testo selezionabile (forse è una scansione)")
        return testo, f"PDF, {len(pagine)} pagine"

    if n.endswith((".txt", ".md")):
        testo = decodifica_testo(dati)
        return testo, f"testo, {len(testo)} caratteri"

    raise ValueError("formato non supportato")


def documenti_per_il_cervello(files, limite):
    """Prepara il testo dei file da dare a Teo. Restituisce (testo, avvisi)."""
    blocchi, avvisi = [], []
    budget = limite // max(len(files), 1)
    for f in files:
        try:
            testo, info = estrai_testo(f.name, f.getvalue())
        except ImportError as e:
            avvisi.append(f"{f.name}: manca una libreria ({e.name}). Aggiungila a requirements.txt.")
            continue
        except Exception as e:
            avvisi.append(f"{f.name}: non riesco a leggerlo ({e}).")
            continue
        nota = ""
        if len(testo) > budget:
            testo = testo[:budget].rsplit("\n", 1)[0]
            nota = " - ATTENZIONE: file tagliato, c'è altro contenuto che non vedi"
            avvisi.append(f"{f.name}: troppo lungo, letta solo una parte. Alza il limite qui sotto.")
        blocchi.append(f"FILE '{f.name}' ({info}){nota}\n{testo}")
    if not blocchi:
        return "", avvisi
    return "DOCUMENTI CARICATI DALL'UTENTE (usali per rispondere):\n\n" + "\n\n".join(blocchi), avvisi


# ---------- Download della risposta (Word e testo) ----------
def crea_docx(testo):
    """Trasforma la risposta (markdown semplice) in un file Word. Restituisce i byte, o None."""
    try:
        from docx import Document
    except ImportError:
        return None
    d = Document()
    for riga in testo.split("\n"):
        r = riga.rstrip().replace("**", "").replace("`", "")
        if not r.strip() or re.fullmatch(r"[\s|:\-]+", r):
            continue
        m = re.match(r"^(#{1,3})\s+(.*)", r)
        if m:
            d.add_heading(m.group(2), level=len(m.group(1)))
        elif re.match(r"^\s*[-*•]\s+", r):
            d.add_paragraph(re.sub(r"^\s*[-*•]\s+", "", r), style="List Bullet")
        elif re.match(r"^\s*\d+[.)]\s+", r):
            d.add_paragraph(re.sub(r"^\s*\d+[.)]\s+", "", r), style="List Number")
        else:
            d.add_paragraph(r)
    buf = io.BytesIO()
    d.save(buf)
    return buf.getvalue()


def pulsanti_scarica(testo, chiave):
    with st.expander("⬇️ Scarica questa risposta come file"):
        dati_word = crea_docx(testo)
        if dati_word:
            st.download_button(
                "Word (.docx)",
                data=dati_word,
                file_name="teo_risposta.docx",
                mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                key=f"word_{chiave}",
            )
        st.download_button(
            "Testo (.txt)",
            data=testo.encode("utf-8"),
            file_name="teo_risposta.txt",
            mime="text/plain",
            key=f"txt_{chiave}",
        )


# ---------- Voce: trascrizione (tu parli) e lettura (lui parla) ----------
def trascrivi(dati_audio):
    """Trasforma la tua voce in testo con Whisper di Groq. Restituisce (testo, errore)."""
    try:
        r = client.audio.transcriptions.create(
            file=("voce.wav", dati_audio),
            model="whisper-large-v3-turbo",
            language="it",
            prompt="Teo, DJ set, BPM, house, techno, mix, Camelot, Beatport, Traktor, Rekordbox, Serato, CDJ",
        )
        return (getattr(r, "text", "") or "").strip(), ""
    except Exception as errore:
        return "", str(errore)


MODELLO_VOCE = """
<div style="display:flex; gap:8px; font-family: sans-serif;">
  <button id="ascolta" style="padding:6px 14px; border:1px solid #4fd8ff; background:transparent; color:#4fd8ff; border-radius:6px; font-size:15px; cursor:pointer;">🔊 Ascolta</button>
  <button id="ferma" style="padding:6px 14px; border:1px solid #4fd8ff; background:transparent; color:#4fd8ff; border-radius:6px; font-size:15px; cursor:pointer;">⏹ Stop</button>
</div>
<script>
  const testo = __TESTO__;
  function parla() {
    if (!window.speechSynthesis) { return; }
    window.speechSynthesis.cancel();
    const frasi = testo.match(/[^.!?]+[.!?]*/g) || [testo];
    const voci = window.speechSynthesis.getVoices().filter(v => v.lang && v.lang.toLowerCase().startsWith('it'));
    frasi.forEach(f => {
      const u = new SpeechSynthesisUtterance(f.trim());
      u.lang = 'it-IT';
      if (voci.length) { u.voice = voci[0]; }
      window.speechSynthesis.speak(u);
    });
  }
  document.getElementById('ascolta').onclick = parla;
  document.getElementById('ferma').onclick = function () { window.speechSynthesis.cancel(); };
  if (__AUTO__) { setTimeout(parla, 300); }
</script>
"""


def voce_html(testo, automatica=False):
    """Mostra i pulsanti Ascolta/Stop. La voce è quella del tuo telefono o computer (gratis)."""
    pulito = re.sub(r"https?://\S+", " ", testo)
    pulito = re.sub(r"[*_#`>~|]", " ", pulito)
    pulito = re.sub(r"\s+", " ", pulito).strip()
    js = json.dumps(pulito).replace("</", "<\\/")
    html = MODELLO_VOCE.replace("__TESTO__", js).replace("__AUTO__", "true" if automatica else "false")
    components.html(html, height=50)


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
    microfono_attivo = st.toggle("Microfono (parli tu)", value=True)
    voce_attiva = st.toggle("Risposta a voce (parla lui)", value=True)

    file_caricati = st.file_uploader(
        "Carica file (CSV, Excel, Word, PDF, TXT)",
        type=["csv", "xlsx", "xlsm", "docx", "pdf", "txt", "md"],
        accept_multiple_files=True,
    )
    contesto_documenti = ""
    if file_caricati:
        limite_caratteri = st.slider(
            "Quanto testo leggere (caratteri)",
            min_value=4000,
            max_value=40000,
            value=12000,
            step=1000,
            help="Più è alto, più Teo vede dei tuoi file, ma consuma più token. Sul piano gratuito di Groq se è troppo alto può dare errore.",
        )
        contesto_documenti, avvisi_documenti = documenti_per_il_cervello(file_caricati, limite_caratteri)
        for avviso in avvisi_documenti:
            st.warning(avviso)

    st.caption("Regole di Teo: file istruzioni_teo.txt letto ✅" if FILE_CARICATO else "Regole di Teo: file non trovato, uso quelle base ⚠️")
    if st.button("Nuova conversazione"):
        st.session_state.messaggi = []
        st.rerun()

# ---------- Chat ----------
if "messaggi" not in st.session_state:
    st.session_state.messaggi = []
if "ultimo_audio" not in st.session_state:
    st.session_state.ultimo_audio = ""

# Due "zone" della pagina: sopra la conversazione, sotto il microfono.
zona_storia = st.container()
zona_microfono = st.container()

testo_vocale = ""
if microfono_attivo:
    with zona_microfono:
        registrazione = st.audio_input("🎙️ Tocca per parlare, tocca ancora per fermare")
        if registrazione is not None:
            dati = registrazione.getvalue()
            impronta = hashlib.md5(dati).hexdigest()
            if impronta != st.session_state.ultimo_audio:
                st.session_state.ultimo_audio = impronta
                with st.spinner("Ti ascolto..."):
                    testo_vocale, errore_voce = trascrivi(dati)
                if errore_voce:
                    st.error(f"Non sono riuscito a capire l'audio: {errore_voce}")
                elif not testo_vocale:
                    st.warning("Non ho sentito nulla. Riprova avvicinandoti al microfono.")

domanda = st.chat_input("Scrivi a Teo...")
if testo_vocale:
    domanda = testo_vocale

with zona_storia:
    if not st.session_state.messaggi:
        st.markdown("Ciao, sono Teo, il tuo Co-DJ. Dimmi cosa stai preparando: un set, una serata, un nuovo genere da studiare?")

    ultimo = len(st.session_state.messaggi) - 1
    for indice, m in enumerate(st.session_state.messaggi):
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
            if m.get("fonti"):
                with st.expander("Fonti"):
                    st.markdown(m["fonti"])
            # Pulsanti solo sull'ultima risposta (e se non ne stiamo creando una nuova)
            if not domanda and indice == ultimo and m["role"] == "assistant":
                if voce_attiva:
                    voce_html(m["content"], automatica=False)
                if file_caricati and not m["content"].startswith("Non riesco a rispondere"):
                    pulsanti_scarica(m["content"], f"storia_{indice}")

    if domanda:
        st.session_state.messaggi.append({"role": "user", "content": domanda})
        with st.chat_message("user"):
            st.markdown(domanda)

        with st.chat_message("assistant"):
            istruzioni = ISTRUZIONI + f"\nOggi è il {date.today().strftime('%d/%m/%Y')}."
            if voce_attiva or testo_vocale:
                istruzioni += (
                    "\nL'utente potrebbe ascoltare la tua risposta a voce: sii breve e parlato, "
                    "evita tabelle e elenchi lunghi. Fa eccezione se ti chiede di riorganizzare "
                    "o riscrivere un documento: in quel caso scrivi il testo completo."
                )
            if contesto_documenti:
                istruzioni += "\n\n" + contesto_documenti
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

            errore_risposta = risposta.startswith("Non riesco a rispondere")
            if voce_attiva and not errore_risposta:
                voce_html(risposta, automatica=True)
            if file_caricati and not errore_risposta:
                pulsanti_scarica(risposta, "nuova")

        st.session_state.messaggi.append({"role": "assistant", "content": risposta, "fonti": fonti})
