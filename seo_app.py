# seo_app.py - Finale, bereinigte Version für IAP-Authentifizierung

import streamlit as st
from pathlib import Path
import pandas as pd
from io import BytesIO
import json
import streamlit.components.v1 as components
from streamlit_option_menu import option_menu
import logging
import google.cloud.logging

# Importiere Funktionen aus deinen Modulen
from utils import convert_tiff_to_png_bytes, read_text_from_docx, read_text_from_pdf, chunk_text
from api_calls import generate_seo_tags_cached, generate_accessibility_description_cached, generate_audio_from_text, get_available_voices, generate_text_summary, get_voice_recommendations, generate_ssml_chunk

# Richte den Google Cloud Logging Handler ein
client = google.cloud.logging.Client()
handler = client.get_default_handler()
cloud_logger = logging.getLogger("cloudLogger")
cloud_logger.setLevel(logging.INFO)
cloud_logger.addHandler(handler)

# Dedizierte Logging-Funktionen
def log_seo_event(uploaded_files):
    """Loggt SEO Tags Verarbeitungs-Events."""
    if uploaded_files:
        log_data = {
            "event_type": "seo_tags_processed",
            "file_count": len(uploaded_files)
        }
        cloud_logger.info(log_data)

def log_accessibility_event(uploaded_files):
    """Loggt Barrierefreie Bildbeschreibung Verarbeitungs-Events."""
    if uploaded_files:
        log_data = {
            "event_type": "accessibility_description_processed",
            "file_count": len(uploaded_files)
        }
        cloud_logger.info(log_data)

def log_tts_event():
    """Loggt Text-to-Speech Verarbeitungs-Events."""
    log_data = {
        "event_type": "text_to_speech_processed",
        "file_count": 1
    }
    cloud_logger.info(log_data)

# Platzhalter-Funktionen, um Fehler zu vermeiden.
# Du musst hier noch deine eigentliche Logik implementieren.
def generate_translation_guide(german_text, gemini_api_key=None):
    st.warning("Platzhalter: Die Funktion 'generate_translation_guide' muss noch implementiert werden.")
    return {"plot_summary": "Dies ist eine Test-Zusammenfassung.", "key_terms": {"Beispiel": "Example"}}

def translate_chunk(translation_guide, german_chunk, previous_english_chunk, gemini_api_key=None):
    st.warning("Platzhalter: Die Funktion 'translate_chunk' muss noch implementiert werden.")
    return f"[Übersetzung für: {german_chunk[:50]}...]"

def process_seo_tags(files):
    """Verarbeitet SEO Tags für die übergebenen Dateien."""
    cloud_logger.info("SEO Tags Verarbeitung gestartet für %d Dateien", len(files))
    st.subheader("Verarbeitungsergebnisse")
    
    for i, uploaded_file in enumerate(files):
        file_name = uploaded_file.name
        safe_file_name_part = "".join(c if c.isalnum() else "_" for c in file_name)
        base_id = f"seo_file_{i}_{safe_file_name_part}"
        try:
            original_image_bytes = uploaded_file.getvalue()
            
            with st.spinner(f"Generiere SEO Tags für {file_name}..."):
                cloud_logger.info("Generiere SEO Tags für Datei: %s", file_name)
                title, alt = generate_seo_tags_cached(original_image_bytes, file_name, gemini_api_key)
            
            if title and alt:
                cloud_logger.info("SEO Tags erfolgreich generiert für: %s", file_name)
                with st.expander(f"✅ SEO Tags für: {file_name}", expanded=True):
                    alt_button_id = f"alt_btn_{base_id}"
                    title_button_id = f"title_btn_{base_id}"
                    col1, col2 = st.columns([1, 3], gap="medium")
                    with col1:
                        st.image(original_image_bytes, width=150, caption="Vorschau")
                    with col2:
                        st.text("ALT Tag:")
                        st.text_area("ALT", value=alt, height=75, key=f"alt_text_{base_id}", disabled=True, label_visibility="collapsed")
                        alt_json = json.dumps(alt)
                        components.html(f"""<button id="{alt_button_id}">ALT kopieren</button><script>document.getElementById("{alt_button_id}").addEventListener('click', function(){{navigator.clipboard.writeText({alt_json}).then(function(){{let b=document.getElementById("{alt_button_id}");let o=b.innerText;b.innerText='Kopiert!';setTimeout(function(){{b.innerText=o}},1500)}})}});</script><style>#{alt_button_id}{{background-color:#007bff;color:white;border:none;padding:5px 10px;border-radius:5px;cursor:pointer;margin-top:5px}}#{alt_button_id}:hover{{background-color:#0056b3}}</style>""", height=45)
                        
                        st.write("")
                        
                        st.text("TITLE Tag:")
                        st.text_area("TITLE", value=title, height=75, key=f"title_text_{base_id}", disabled=True, label_visibility="collapsed")
                        title_json = json.dumps(title)
                        components.html(f"""<button id="{title_button_id}">TITLE kopieren</button><script>document.getElementById("{title_button_id}").addEventListener('click', function(){{navigator.clipboard.writeText({title_json}).then(function(){{let b=document.getElementById("{title_button_id}");let o=b.innerText;b.innerText='Kopiert!';setTimeout(function(){{b.innerText=o}},1500)}})}});</script><style>#{title_button_id}{{background-color:#007bff;color:white;border:none;padding:5px 10px;border-radius:5px;cursor:pointer;margin-top:5px}}#{title_button_id}:hover{{background-color:#0056b3}}</style>""", height=45)
            else:
                logging.error("SEO Tag-Generierung fehlgeschlagen für: %s", file_name)
                st.error(f"❌ Fehler bei SEO Tag-Generierung für '{file_name}'.")
        except Exception as e:
            logging.error("Unerwarteter Fehler bei SEO Tag-Generierung für %s: %s", file_name, str(e))
            st.error(f"🚨 Unerwarteter FEHLER bei '{file_name}': {e}")
    
    cloud_logger.info("SEO-Verarbeitung abgeschlossen")
    st.success("SEO-Verarbeitung abgeschlossen.")

def process_accessibility_descriptions(files, context):
    """Verarbeitet barrierefreie Bildbeschreibungen für die übergebenen Dateien."""
    cloud_logger.info("Barrierefreie Bildbeschreibung Verarbeitung gestartet für %d Dateien", len(files))
    st.subheader("Verarbeitungsergebnisse")
    processed_count, failed_count = 0, 0
    results_for_export = []
    
    for i, uploaded_file in enumerate(files):
        file_name = uploaded_file.name
        safe_file_name_part = "".join(c if c.isalnum() else "_" for c in file_name)
        base_id = f"access_{i}_{safe_file_name_part}"
        try:
            original_image_bytes = uploaded_file.getvalue()
            image_bytes_for_api = original_image_bytes
            if Path(file_name).suffix.lower() in ['.tif', '.tiff']:
                with st.spinner(f"Konvertiere {file_name} (TIFF) zu PNG..."):
                    try:
                        image_bytes_for_api = convert_tiff_to_png_bytes(original_image_bytes)
                    except Exception as conv_e:
                        st.error(f"🚨 Fehler beim Konvertieren von '{file_name}': {conv_e}")
                        failed_count += 1
                        continue
            
            with st.spinner(f"Generiere barrierefreie Beschreibung für {file_name}..."):
                cloud_logger.info("Generiere barrierefreie Beschreibung für Datei: %s", file_name)
                short_desc, long_desc = generate_accessibility_description_cached(image_bytes_for_api, file_name, context, gemini_api_key)
            
            if short_desc and long_desc:
                cloud_logger.info("Barrierefreie Beschreibung erfolgreich generiert für: %s", file_name)
                st.markdown(f"--- \n#### ✅ Ergebnisse für: `{file_name}`")
                col1, col2 = st.columns([1, 3], gap="medium")
                with col1:
                    st.image(original_image_bytes, width=150, caption="Vorschau")
                with col2:
                    st.text("Kurzbeschreibung (max. 140 Zeichen):")
                    st.text_area("Kurz", value=short_desc, height=100, key=f"short_text_{base_id}", disabled=True, label_visibility="collapsed")
                    short_desc_button_id = f"short_copy_{base_id}"
                    short_json = json.dumps(short_desc)
                    components.html(f"""<button id="{short_desc_button_id}">Kurzbeschreibung kopieren</button><script>document.getElementById("{short_desc_button_id}").addEventListener('click', function(){{navigator.clipboard.writeText({short_json}).then(function(){{let b=document.getElementById("{short_desc_button_id}");let o=b.innerText;b.innerText='Kopiert!';setTimeout(function(){{b.innerText=o}},1500)}})}});</script><style>#{short_desc_button_id}{{background-color:#007bff;color:white;border:none;padding:5px 10px;border-radius:5px;cursor:pointer;margin-top:5px}}#{short_desc_button_id}:hover{{background-color:#0056b3}}</style>""", height=45)
                    
                    with st.expander("Zeige/verberge Langbeschreibung"):
                        st.text_area("Lang", value=long_desc, height=200, key=f"long_text_{base_id}", disabled=True, label_visibility="collapsed")
                        long_desc_button_id = f"long_copy_{base_id}"
                        long_json = json.dumps(long_desc)
                        components.html(f"""<button id="{long_desc_button_id}">Langbeschreibung kopieren</button><script>document.getElementById("{long_desc_button_id}").addEventListener('click', function(){{navigator.clipboard.writeText({long_json}).then(function(){{let b=document.getElementById("{long_desc_button_id}");let o=b.innerText;b.innerText='Kopiert!';setTimeout(function(){{b.innerText=o}},1500)}})}});</script><style>#{long_desc_button_id}{{background-color:#007bff;color:white;border:none;padding:5px 10px;border-radius:5px;cursor:pointer;margin-top:5px}}#{long_desc_button_id}:hover{{background-color:#0056b3}}</style>""", height=45)
                
                processed_count += 1
                results_for_export.append({
                    "Bildname": file_name, "Dateiname Produktion": "", "Alternativtext": short_desc,
                    "Bildlegende": "", "Anmerkung": "", "Langbeschreibung": long_desc,
                    "(Platzierung/Größe/Übersetzungstexte in der Abbildung/...)": ""
                })
            else:
                logging.error("Barrierefreie Beschreibung fehlgeschlagen für: %s", file_name)
                st.error(f"❌ Fehler bei Erstellung der barrierefreien Beschreibung für '{file_name}'.")
                failed_count += 1
        except Exception as e:
            logging.error("Unerwarteter Fehler bei barrierefreier Beschreibung für %s: %s", file_name, str(e))
            st.error(f"🚨 Unerwarteter FEHLER bei der Hauptverarbeitung von '{file_name}': {e}")
            failed_count += 1
    
    if results_for_export:
        st.divider()
        st.subheader("📊 Ergebnisse exportieren")
        df = pd.DataFrame(results_for_export)
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Bildbeschreibungen')
        excel_data = output.getvalue()
        st.download_button(
            label="💾 Excel-Datei herunterladen", data=excel_data,
            file_name="barrierefreie_bildbeschreibungen.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    
    st.divider()
    st.subheader("🏁 Zusammenfassung")
    col1, col2 = st.columns(2)
    col1.metric("Erfolgreich verarbeitet", processed_count)
    col2.metric("Fehlgeschlagen", failed_count, delta=None if failed_count == 0 else -failed_count, delta_color="inverse")
    
    st.success("Verarbeitung abgeschlossen.")

def process_text_to_speech(text_content, guideline, selected_voice_name):
    """Verarbeitet Text-to-Speech."""
    with st.status("Generiere Audio-Datei...", expanded=True) as status:
        status.write("Teile Text in initiale Stücke (Chunks)...")
        initial_chunks = chunk_text(text_content)
        
        final_ssml_chunks = []
        
        for i, chunk in enumerate(initial_chunks):
            status.write(f"Verarbeite initialen Chunk {i+1}/{len(initial_chunks)}: Erzeuge SSML...")
            ssml_chunk = generate_ssml_chunk(guideline, chunk, gemini_api_key)
            
            if len(ssml_chunk) < 9800:
                final_ssml_chunks.append(ssml_chunk)
            else:
                status.warning(f"Chunk {i+1} ist nach SSML zu lang ({len(ssml_chunk)} Zeichen). Teile ihn auf...")
                sub_chunks = chunk_text(chunk, 4000)
                
                for sub_chunk in sub_chunks:
                    final_ssml_chunks.append(generate_ssml_chunk(guideline, sub_chunk, gemini_api_key))
        
        status.write(f"Finale Audio-Generierung aus {len(final_ssml_chunks)} SSML-Blöcken...")
        all_audio_bytes = []
        available_voices = get_available_voices(elevenlabs_api_key)
        selected_voice_id = available_voices[selected_voice_name]["voice_id"]
        
        for i, final_chunk in enumerate(final_ssml_chunks):
            status.write(f"Generiere Audio für finalen Block {i+1}/{len(final_ssml_chunks)}...")
            audio_segment = generate_audio_from_text(final_chunk, elevenlabs_api_key, selected_voice_id)
            
            if audio_segment:
                all_audio_bytes.append(audio_segment)
            else:
                status.update(label=f"Fehler bei Block {i+1}", state="error")
                break
        
        if len(all_audio_bytes) == len(final_ssml_chunks):
            status.update(label="Audio-Generierung abgeschlossen!", state="complete")
            final_audio = b"".join(all_audio_bytes)

            st.success("Finale Audiodatei erfolgreich erstellt!")
            st.audio(final_audio, format="audio/mpeg")
            st.download_button(
                "MP3-Datei herunterladen", final_audio, 
                file_name=f"{Path(st.session_state.uploaded_file_name).stem}_mit_regie.mp3",
                mime="audio/mpeg"
            )
    st.session_state.tts_step = 2


# Page config MUSS der erste Streamlit-Befehl sein
st.set_page_config(page_title="Toolbox", page_icon="app_icon.png", layout="wide")

# ==============================================================================
# HIER BEGINNT DIE ANWENDUNG
# Da IAP-Authentifizierung aktiviert ist, wird dieser Code nur von
# bereits authentifizierten und autorisierten Nutzern erreicht.
# ==============================================================================

# API-Schlüssel direkt aus st.secrets laden
gemini_api_key = st.secrets.get("gemini_api_key")
elevenlabs_api_key = st.secrets.get("elevenlabs_api_key")

# Prüfe, ob die API-Schlüssel vorhanden sind.
missing_keys = []
if not gemini_api_key:
    missing_keys.append("gemini-api-key")
if not elevenlabs_api_key:
    missing_keys.append("elevenlabs-api-key")

if missing_keys:
    st.error(f"🚨 Folgende API-Schlüssel sind nicht konfiguriert: {', '.join(missing_keys)}")
    st.info("Die App läuft im Demo-Modus. Funktionen sind eingeschränkt.")
    logging.warning("API-Schlüssel fehlen: %s", missing_keys)

# --- Seitenleiste ---
with st.sidebar:
    st.image("app_icon.png", width=100)
    st.markdown("Willkommen!")
    st.divider()
    st.markdown("# 🧰 Toolbox")
    st.markdown("##### AI-Tools für dich")
    st.divider()
    st.subheader("ℹ️ Info")

# --- Hauptbereich mit Navigation ---
selected_tool = option_menu(
    menu_title=None,
    options=["SEO Tags", "Barrierefreie Bildbeschreibung", "Text-to-Speech", "Manuskript-Übersetzung"],
    icons=['search', 'universal-access-circle', 'sound-wave', 'translate'],
    menu_icon="cast", default_index=0, orientation="horizontal",
    styles={
        "container": {"padding": "5px !important", "background-color": "#fafafa", "border-radius": "10px"},
        "icon": {"color": "#4A90E2", "font-size": "24px"},
        "nav-link": {"font-size": "16px", "font-weight": "600", "text-align": "center", "margin": "0px 5px", "--hover-color": "#eee", "border-radius": "10px"},
        "nav-link-selected": {"background-color": "#007bff"},
    }
)

# Update der Sidebar-Info basierend auf der Tool-Auswahl
with st.sidebar:
    supported_formats_images = "jpg, jpeg, png, gif, bmp, webp, tif, tiff"
    if selected_tool == "SEO Tags":
        st.markdown(f"Erzeuge **Alt** und **Title Tags** mit Gemini.\n\n**Unterstützte Formate:** `{supported_formats_images}`\n\nBei Fragen -> Gordon")
    elif selected_tool == "Barrierefreie Bildbeschreibung":
        st.markdown(f"Erzeuge **Bildbeschreibungen** mit Gemini.\n\n**Unterstützte Formate:** `{supported_formats_images}`\n\n**Download möglich:** Die Ergebnisse können als Excel-Datei heruntergeladen werden.\n\nBei Fragen -> Gordon")
    elif selected_tool == "Text-to-Speech":
        st.markdown("Wandle Text aus **Word-Dokumenten** oder **PDFs** in gesprochene Sprache um.\n\n**Unterstützte Formate:** `.docx`, `.pdf`\n\n**API:** ElevenLabs\n\nBei Fragen -> Gordon")
    elif selected_tool == "Manuskript-Übersetzung":
        st.markdown("Übersetze **deutsche Manuskripte** ins Englische mit kontext-bewusster KI.\n\n**Unterstützte Formate:** `.docx`, `.pdf`\n\n**Features:** Style & Glossar-Leitfaden, konsistente Terminologie\n\nBei Fragen -> Gordon")

st.divider()

cloud_logger.info("Streamlit-App gestartet, Tool ausgewählt: %s", selected_tool)


# --- Logik für jedes Werkzeug ---
if selected_tool == "SEO Tags":
    st.header("SEO Tags (Alt & Title) generieren")
    st.caption("Dieses Werkzeug erstellt prägnante `alt`- und `title`-Tags für Bilder.")

    # Tab-Auswahl für Upload oder URL
    input_method = st.radio(
        "Wähle die Eingabemethode:",
        ("Datei-Upload", "Bild-URL"),
        horizontal=True,
        key="seo_input_method"
    )
    st.divider()

    # --- Logik für Datei-Upload ---
    if input_method == "Datei-Upload":
        seo_uploaded_files = st.file_uploader(
            "Bilder für SEO Tags hochladen...", accept_multiple_files=True,
            type=['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'tif', 'tiff'], key="seo_uploader"
        )

        if seo_uploaded_files:
            st.button(
                "🚀 SEO Tags für Dateien verarbeiten",
                key="process_seo_files_button",
                on_click=log_seo_event,
                args=(seo_uploaded_files,)
            )
            
            # Verarbeitungslogik
            process_seo_tags(seo_uploaded_files)
    
    # --- Logik für Bild-URL ---
    elif input_method == "Bild-URL":
        image_url = st.text_input("Bild-URL einfügen:", placeholder="https://...", key="seo_url_input")
        st.caption("Bitte füge einen direkten Link zu einer Bilddatei ein (z.B. endend auf .jpg, .png).")

        if image_url:
            if st.button("🚀 SEO Tags für URL verarbeiten", type="primary", key="process_seo_url_button"):
                with st.spinner(f"Verarbeite Bild von URL..."):
                    try:
                        title, alt = generate_seo_tags_cached(image_url, image_url, gemini_api_key)
                        
                        if title and alt:
                            st.subheader("Verarbeitungsergebnis")
                            base_id = "seo_url_result"
                            alt_button_id = f"alt_btn_{base_id}"
                            title_button_id = f"title_btn_{base_id}"
                            with st.expander(f"✅ SEO Tags für die URL", expanded=True):
                                col1, col2 = st.columns([1, 3], gap="medium")
                                with col1:
                                    st.image(image_url, width=150, caption="Vorschau")
                                with col2:
                                    st.text("ALT Tag:")
                                    st.text_area("ALT", value=alt, height=75, key=f"alt_text_{base_id}", disabled=True, label_visibility="collapsed")
                                    alt_json = json.dumps(alt)
                                    components.html(f"""<button id="{alt_button_id}">ALT kopieren</button><script>document.getElementById("{alt_button_id}").addEventListener('click', function(){{navigator.clipboard.writeText({alt_json}).then(function(){{let b=document.getElementById("{alt_button_id}");let o=b.innerText;b.innerText='Kopiert!';setTimeout(function(){{b.innerText=o}},1500)}})}});</script><style>#{alt_button_id}{{background-color:#007bff;color:white;border:none;padding:5px 10px;border-radius:5px;cursor:pointer;margin-top:5px}}#{alt_button_id}:hover{{background-color:#0056b3}}</style>""", height=45)

                                    st.write("")

                                    st.text("TITLE Tag:")
                                    st.text_area("TITLE", value=title, height=75, key=f"title_text_{base_id}", disabled=True, label_visibility="collapsed")
                                    title_json = json.dumps(title)
                                    components.html(f"""<button id="{title_button_id}">TITLE kopieren</button><script>document.getElementById("{title_button_id}").addEventListener('click', function(){{navigator.clipboard.writeText({title_json}).then(function(){{let b=document.getElementById("{title_button_id}");let o=b.innerText;b.innerText='Kopiert!';setTimeout(function(){{b.innerText=o}},1500)}})}});</script><style>#{title_button_id}{{background-color:#007bff;color:white;border:none;padding:5px 10px;border-radius:5px;cursor:pointer;margin-top:5px}}#{title_button_id}:hover{{background-color:#0056b3}}</style>""", height=45)
                        else:
                            st.error(f"❌ Fehler bei SEO Tag-Generierung für die URL.")
                    except Exception as e:
                        st.error(f"🚨 Unerwarteter FEHLER bei der Verarbeitung der URL: {e}")

elif selected_tool == "Barrierefreie Bildbeschreibung":
    st.header("Barrierefreie Bildbeschreibung (Kurz & Lang)")
    st.caption("Dieses Werkzeug erstellt eine prägnante Kurzbeschreibung (Alt-Text) und eine detaillierte Langbeschreibung für E-Books und barrierefreie Inhalte.")

    ebook_context_input = st.text_area(
        "Kontext des E-Books eingeben (optional, aber empfohlen)",
        height=100, key="ebook_context_main", max_chars=500,
        placeholder="z.B. Titel, Kapitel, Thema des Abschnitts, oder was das Bild illustrieren soll.",
        help="Dieser Kontext wird an die KI weitergegeben."
    )
    st.caption(f"{len(ebook_context_input)}/500 Zeichen")

    accessibility_uploaded_files = st.file_uploader(
        "Bilder für barrierefreie Beschreibungen hochladen...", accept_multiple_files=True,
        type=['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'tif', 'tiff'], key="accessibility_uploader"
    )

    if accessibility_uploaded_files:
        st.button(
            "🚀 Beschreibungen verarbeiten",
            key="process_accessibility_button",
            on_click=log_accessibility_event,
            args=(accessibility_uploaded_files,)
        )
        
        # Verarbeitungslogik
        process_accessibility_descriptions(accessibility_uploaded_files, ebook_context_input)

elif selected_tool == "Text-to-Speech":
    st.header("Text-to-Speech mit KI-Regieanweisung")
    st.caption("Dieses Tool analysiert deinen Text, um eine passende Stimme vorzuschlagen und eine natürliche Sprachausgabe zu erzeugen.")

    if "tts_step" not in st.session_state:
        st.session_state.tts_step = 1
        st.session_state.guideline = None
        st.session_state.top_3_voices = []
        st.session_state.text_content = None
        st.session_state.summary = None
        st.session_state.selected_voice_name = ""
        st.session_state.uploaded_file_name = None

    if st.session_state.tts_step > 1:
        if st.button("Neue Analyse starten"):
            st.session_state.tts_step = 1
            st.session_state.guideline = None
            st.session_state.top_3_voices = []
            st.session_state.text_content = None
            st.session_state.summary = None
            st.session_state.selected_voice_name = ""
            st.session_state.uploaded_file_name = None
            st.rerun()

    if st.session_state.tts_step < 3:
        st.subheader("1. Dokument hochladen")
        uploaded_file = st.file_uploader(
            label="Lade dein Dokument hoch (.docx oder .pdf)",
            type=['docx', 'pdf'],
            key="tts_uploader"
        )

    if 'uploaded_file' not in locals():
        uploaded_file = None 

    if uploaded_file and st.session_state.tts_step == 1:
        if st.button("Text analysieren & Stimmen empfehlen", type="primary"):
            st.session_state.uploaded_file_name = uploaded_file.name 
            with st.spinner("Lese Text aus Datei..."):
                if uploaded_file.name.lower().endswith('.pdf'):
                    text_content = read_text_from_pdf(uploaded_file)
                else:
                    text_content = read_text_from_docx(uploaded_file)
            
            if not text_content or not text_content.strip() or text_content == "NO_TEXT_IN_PDF":
                st.error("Das Dokument scheint keinen lesbaren Text zu enthalten.")
            else:
                st.session_state.text_content = text_content
                
                with st.status("Führe KI-Analyse aus...", expanded=True) as status:
                    status.write("Schritt 1/3: Erstelle Zusammenfassung des Textes...")
                    summary = generate_text_summary(text_content, gemini_api_key)
                    st.session_state.summary = summary
                    
                    status.write("Schritt 2/3: Rufe verfügbare Stimmen ab...")
                    available_voices = get_available_voices(elevenlabs_api_key)
                    if "Fehler" in available_voices:
                        status.update(label="Fehler beim Abrufen der Stimmen.", state="error")
                        st.stop()
                    
                    voices_info_for_prompt = "\n".join([f"Name: {n} (Beschreibung: {', '.join(f'{k}: {v}' for k, v in details.get('labels', {}).items())})" for n, details in available_voices.items() if details.get('labels')])
                    
                    if not voices_info_for_prompt:
                        status.warning("Keine Stimmen mit detaillierten Beschreibungen gefunden. Verwende stattdessen nur die Namen für die Empfehlung.")
                        voices_info_for_prompt = "\n".join([f"Name: {n}" for n in available_voices.keys()])

                    status.write("Schritt 3/3: Erstelle Regieleitlinie und finde passende Stimmen...")
                    guideline, recommendations = get_voice_recommendations(summary, voices_info_for_prompt, gemini_api_key)
                    
                    st.session_state.guideline = guideline
                    st.session_state.top_3_voices = recommendations
                    status.update(label="Analyse abgeschlossen!", state="complete", expanded=False)
                
                st.session_state.tts_step = 2
                st.rerun()

    if st.session_state.tts_step >= 2:
        st.divider()
        st.subheader("2. Analyse-Ergebnisse")

        with st.expander("KI-Regieanweisung und Stimmen-Empfehlung anzeigen", expanded=True):
            st.markdown(st.session_state.guideline)

        if st.session_state.summary:
            with st.expander("Inhaltliche Zusammenfassung des Textes anzeigen"):
                st.markdown(st.session_state.summary)
                st.download_button(
                    label="Zusammenfassung herunterladen (.txt)",
                    data=st.session_state.summary.encode('utf-8'),
                    file_name=f"zusammenfassung_{st.session_state.uploaded_file_name}.txt",
                    mime="text/plain"
                )
        
        st.divider()
        st.subheader("3. Stimme auswählen")
        
        if st.session_state.top_3_voices:
            st.write("**Top 3 Empfehlungen der KI:**")
            if len(st.session_state.top_3_voices) > 0:
                st.success(f"🥇 **{st.session_state.top_3_voices[0]}**")
            if len(st.session_state.top_3_voices) > 1:
                st.info(f"🥈 {st.session_state.top_3_voices[1]}")
            if len(st.session_state.top_3_voices) > 2:
                st.info(f"🥉 {st.session_state.top_3_voices[2]}")
        
        available_voices = get_available_voices(elevenlabs_api_key)
        voice_names = list(available_voices.keys())
        
        default_index = 0
        if st.session_state.top_3_voices:
            try:
                default_index = voice_names.index(st.session_state.top_3_voices[0])
            except (ValueError, IndexError):
                st.warning(f"Empfohlene Stimme '{st.session_state.top_3_voices[0]}' nicht in der Liste gefunden. Wähle manuell.")
                default_index = 0

        st.session_state.selected_voice_name = st.selectbox(
            "Wähle eine Stimme (Top-Empfehlung ist vorausgewählt)",
            options=voice_names,
            index=default_index,
            key="voice_selector"
        )
        
        if st.session_state.selected_voice_name:
            preview_url = available_voices[st.session_state.selected_voice_name].get("preview_url")
            if preview_url:
                st.audio(preview_url)
        
        st.divider()
        st.subheader("4. Finale Audio-Datei generieren")
        if st.button("🎙️ Audio mit KI-Regie generieren", type="primary", key="generate_audio_button"):
            st.session_state.tts_step = 3
            st.rerun()

    if st.session_state.tts_step == 3:
        final_selected_voice = st.session_state.selected_voice_name
        
        st.info(f"Audio-Generierung mit der Stimme '{final_selected_voice}' wird vorbereitet...")
        
        st.button(
            "🎙️ Audio mit KI-Regie generieren",
            key="tts_generate_button",
            on_click=log_tts_event
        )
        
        # Verarbeitungslogik
        process_text_to_speech(st.session_state.text_content, st.session_state.guideline, final_selected_voice)

elif selected_tool == "Manuskript-Übersetzung":
    st.header("Manuskript-Übersetzung (Deutsch → Englisch)")
    st.caption("Dieses Tool übersetzt deutsche Manuskripte ins Englische mit kontext-bewusster KI für hohe stilistische und terminologische Konsistenz.")

    uploaded_file = st.file_uploader(
        label="Lade dein deutsches Manuskript hoch (.docx oder .pdf)",
        type=['docx', 'pdf'],
        key="translation_uploader"
    )

    if uploaded_file:
        if st.button("🚀 Übersetzung starten", type="primary", key="start_translation_button"):
            with st.status("Übersetzung läuft...", expanded=True) as status:
                # Status 1: Text extrahieren
                status.write("1. Extrahiere Text aus Dokument...")
                if uploaded_file.name.lower().endswith('.pdf'):
                    german_text = read_text_from_pdf(uploaded_file)
                else:
                    german_text = read_text_from_docx(uploaded_file)
                
                if not german_text or not german_text.strip() or german_text == "NO_TEXT_IN_PDF":
                    status.update(label="Fehler: Kein lesbarer Text gefunden", state="error")
                    st.error("Das Dokument scheint keinen lesbaren Text zu enthalten.")
                    st.stop()
                
                # Status 2: Übersetzungs-Leitfaden erstellen
                status.write("2. Erstelle Übersetzungs-Leitfaden...")
                translation_guide = generate_translation_guide(german_text, gemini_api_key)
                
                if not translation_guide or "Fehler" in str(translation_guide.get("plot_summary", "")):
                    status.update(label="Fehler beim Erstellen des Leitfadens", state="error")
                    st.error("Fehler beim Erstellen des Übersetzungs-Leitfadens.")
                    st.stop()
                
                # Status 3: Text in Chunks aufteilen
                status.write("3. Teile Text in Abschnitte...")
                german_chunks = chunk_text(german_text, chunk_size=3000)
                
                # Status 4: Chunks übersetzen
                status.write(f"4. Übersetze {len(german_chunks)} Abschnitte...")
                english_chunks = []
                
                for i, german_chunk in enumerate(german_chunks):
                    status.write(f"   Übersetze Abschnitt {i+1} von {len(german_chunks)}...")
                    
                    # Übergebe den vorherigen englischen Chunk für flüssige Übergänge
                    previous_english_chunk = english_chunks[-1] if english_chunks else None
                    
                    english_chunk = translate_chunk(translation_guide, german_chunk, previous_english_chunk, gemini_api_key)
                    english_chunks.append(english_chunk)
                
                # Status 5: Übersetztes Manuskript zusammenfügen
                status.write("5. Setze übersetztes Manuskript zusammen...")
                final_english_text = "\n\n".join(english_chunks)
                
                status.update(label="Übersetzung abgeschlossen!", state="complete", expanded=False)
            
            # Erfolgsmeldung anzeigen
            st.success("✅ Übersetzung erfolgreich abgeschlossen!")
            
            # Style & Glossar-Leitfaden anzeigen
            with st.expander("📋 Style & Glossar-Leitfaden anzeigen", expanded=False):
                st.json(translation_guide)
            
            # Download-Button für das übersetzte Manuskript
            st.download_button(
                label="💾 Übersetztes Manuskript herunterladen (.txt)",
                data=final_english_text.encode('utf-8'),
                file_name=f"übersetzung_{Path(uploaded_file.name).stem}.txt",
                mime="text/plain"
            )
            
            # Statistiken anzeigen
            st.divider()
            st.subheader("📊 Übersetzungs-Statistiken")
            col1, col2, col3 = st.columns(3)
            col1.metric("Deutsche Wörter", len(german_text.split()))
            col2.metric("Englische Wörter", len(final_english_text.split()))
            col3.metric("Verarbeitete Abschnitte", len(german_chunks))