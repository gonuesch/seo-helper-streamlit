# seo_app.py - Finale, bereinigte Version für IAP-Authentifizierung

import streamlit as st
from pathlib import Path
import pandas as pd
from io import BytesIO
import json
import streamlit.components.v1 as components
from streamlit_option_menu import option_menu
import logging
import google.cloud.pubsub_v1 as pubsub_v1
import uuid
import time

# Importiere Funktionen aus deinen Modulen
from utils import convert_tiff_to_png_bytes, read_text_from_docx, read_text_from_pdf, chunk_text
from api_calls import generate_seo_tags_cached, generate_accessibility_description_cached, generate_audio_from_text, get_available_voices, generate_text_summary, get_voice_recommendations, generate_ssml_chunk

# Richte den Google Cloud Pub/Sub Publisher ein
publisher = pubsub_v1.PublisherClient()
topic_path = publisher.topic_path("avid-infinity-458913-p3", "event-tracking")

# Pub/Sub Event Tracking Funktion
def send_event_to_pubsub(event_data):
    """Sendet ein Event an Google Cloud Pub/Sub."""
    try:
        # Konvertiere das Wörterbuch in einen JSON-String und dann in Bytes
        message_json = json.dumps(event_data)
        message_bytes = message_json.encode('utf-8')
        
        # Sende die Nachricht an Pub/Sub
        publish_future = publisher.publish(topic_path, data=message_bytes)
        publish_future.result()  # Wartet auf das Ergebnis (optional)
    except Exception as e:
        st.error(f"Fehler beim Senden des Tracking-Events: {e}")
        logging.error(f"Pub/Sub Fehler: {e}")

# Platzhalter-Funktionen, um Fehler zu vermeiden.
# Du musst hier noch deine eigentliche Logik implementieren.
def generate_translation_guide(german_text, gemini_api_key=None):
    st.warning("Platzhalter: Die Funktion 'generate_translation_guide' muss noch implementiert werden.")
    return {"plot_summary": "Dies ist eine Test-Zusammenfassung.", "key_terms": {"Beispiel": "Example"}}

def translate_chunk(translation_guide, german_chunk, previous_english_chunk, gemini_api_key=None):
    st.warning("Platzhalter: Die Funktion 'translate_chunk' muss noch implementiert werden.")
    return f"[Übersetzung für: {german_chunk[:50]}...]"

# State Management Callback Functions (no longer needed, but kept for potential future use)
def set_run_state_true(state_key):
    """Reusable callback function that sets a state key to True."""
    st.session_state[state_key] = True

# Button click tracking for logging
def get_button_click_id():
    """Generates a unique click ID for tracking button clicks."""
    if 'click_counter' not in st.session_state:
        st.session_state.click_counter = 0
    st.session_state.click_counter += 1
    return f"click_{st.session_state.click_counter}_{int(time.time())}"

# Comprehensive Processing Functions
def run_seo_processing_and_logging(files_to_process):
    """Comprehensive SEO processing function that handles everything in one place."""
    # Generate unique click ID for this button click
    click_id = get_button_click_id()
    
    # Store results in session state instead of displaying immediately
    results = []
    
    with st.spinner("Verarbeite SEO Tags..."):
        for i, uploaded_file in enumerate(files_to_process):
            file_name = uploaded_file.name
            safe_file_name_part = "".join(c if c.isalnum() else "_" for c in file_name)
            base_id = f"seo_file_{i}_{safe_file_name_part}"
            try:
                original_image_bytes = uploaded_file.getvalue()
                
                logging.info("Generiere SEO Tags für Datei: %s", file_name)
                title, alt = generate_seo_tags_cached(original_image_bytes, file_name, gemini_api_key)
                
                if title and alt:
                    logging.info("SEO Tags erfolgreich generiert für: %s", file_name)
                    results.append({
                        "file_name": file_name,
                        "title": title,
                        "alt": alt,
                        "image_bytes": original_image_bytes,
                        "base_id": base_id,
                        "status": "success"
                    })
                else:
                    logging.error("SEO Tag-Generierung fehlgeschlagen für: %s", file_name)
                    results.append({
                        "file_name": file_name,
                        "error": f"❌ Fehler bei SEO Tag-Generierung für '{file_name}'.",
                        "status": "failed"
                    })
            except Exception as e:
                logging.error("Unerwarteter Fehler bei SEO Tag-Generierung für %s: %s", file_name, str(e))
                results.append({
                    "file_name": file_name,
                    "error": f"🚨 Unerwarteter FEHLER bei '{file_name}': {e}",
                    "status": "error",
                    "error_message": str(e)
                })
    
    # Store results and click ID in session state
    st.session_state.seo_results = results
    st.session_state.seo_click_id = click_id
    
    st.success("SEO-Verarbeitung abgeschlossen.")

def run_seo_url_processing_and_logging(image_url):
    """Comprehensive SEO URL processing function that handles everything in one place."""
    # Generate unique click ID for this button click
    click_id = get_button_click_id()
    
    with st.spinner(f"Verarbeite Bild von URL..."):
        try:
            title, alt = generate_seo_tags_cached(image_url, image_url, gemini_api_key)
            
            if title and alt:
                st.session_state.seo_url_result = {
                    "title": title,
                    "alt": alt,
                    "image_url": image_url,
                    "status": "success"
                }
            else:
                st.session_state.seo_url_result = {
                    "error": "❌ Fehler bei SEO Tag-Generierung für die URL.",
                    "status": "failed"
                }
        except Exception as e:
            st.session_state.seo_url_result = {
                "error": f"🚨 Unerwarteter FEHLER bei der Verarbeitung der URL: {e}",
                "status": "error",
                "error_message": str(e)
            }
    
    # Store click ID for logging
    st.session_state.seo_url_click_id = click_id

def run_accessibility_processing_and_logging(files_to_process, context):
    """Comprehensive accessibility processing function that handles everything in one place."""
    # Generate unique click ID for this button click
    click_id = get_button_click_id()
    
    processed_count, failed_count = 0, 0
    results = []
    results_for_export = []
    
    with st.spinner("Verarbeite barrierefreie Beschreibungen..."):
        for i, uploaded_file in enumerate(files_to_process):
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
                            results.append({
                                "file_name": file_name,
                                "error": f"🚨 Fehler beim Konvertieren von '{file_name}': {conv_e}",
                                "status": "conversion_error",
                                "error_message": str(conv_e)
                            })
                            continue
                
                logging.info("Generiere barrierefreie Beschreibung für Datei: %s", file_name)
                short_desc, long_desc = generate_accessibility_description_cached(image_bytes_for_api, file_name, context, gemini_api_key)
                
                if short_desc and long_desc:
                    logging.info("Barrierefreie Beschreibung erfolgreich generiert für: %s", file_name)
                    results.append({
                        "file_name": file_name,
                        "short_desc": short_desc,
                        "long_desc": long_desc,
                        "image_bytes": original_image_bytes,
                        "base_id": base_id,
                        "status": "success"
                    })
                    processed_count += 1
                    results_for_export.append({
                        "Bildname": file_name, "Dateiname Produktion": "", "Alternativtext": short_desc,
                        "Bildlegende": "", "Anmerkung": "", "Langbeschreibung": long_desc,
                        "(Platzierung/Größe/Übersetzungstexte in der Abbildung/...)": ""
                    })
                else:
                    logging.error("Barrierefreie Beschreibung fehlgeschlagen für: %s", file_name)
                    results.append({
                        "file_name": file_name,
                        "error": f"❌ Fehler bei Erstellung der barrierefreien Beschreibung für '{file_name}'.",
                        "status": "failed"
                    })
                    failed_count += 1
            except Exception as e:
                logging.error("Unerwarteter Fehler bei barrierefreier Beschreibung für %s: %s", file_name, str(e))
                results.append({
                    "file_name": file_name,
                    "error": f"🚨 Unerwarteter FEHLER bei der Hauptverarbeitung von '{file_name}': {e}",
                    "status": "error",
                    "error_message": str(e)
                })
                failed_count += 1
    
    # Store results in session state
    st.session_state.accessibility_results = results
    st.session_state.accessibility_export_data = results_for_export
    st.session_state.accessibility_summary = {"processed_count": processed_count, "failed_count": failed_count}
    
    # Store click ID for logging
    st.session_state.accessibility_click_id = click_id
    
    st.success("Verarbeitung abgeschlossen.")

def run_tts_processing_and_logging():
    """Comprehensive TTS processing function that handles everything in one place."""
    # Generate unique click ID for this button click
    click_id = get_button_click_id()
    
    with st.status("Generiere Audio-Datei...", expanded=True) as status:
        status.write("Teile Text in initiale Stücke (Chunks)...")
        initial_chunks = chunk_text(st.session_state.text_content)
        
        final_ssml_chunks = []
        
        for i, chunk in enumerate(initial_chunks):
            status.write(f"Verarbeite initialen Chunk {i+1}/{len(initial_chunks)}: Erzeuge SSML...")
            ssml_chunk = generate_ssml_chunk(st.session_state.guideline, chunk, gemini_api_key)
            
            if len(ssml_chunk) < 9800:
                final_ssml_chunks.append(ssml_chunk)
            else:
                status.warning(f"Chunk {i+1} ist nach SSML zu lang ({len(ssml_chunk)} Zeichen). Teile ihn auf...")
                sub_chunks = chunk_text(chunk, 4000)
                
                for sub_chunk in sub_chunks:
                    final_ssml_chunks.append(generate_ssml_chunk(st.session_state.guideline, sub_chunk, gemini_api_key))
        
        status.write(f"Finale Audio-Generierung aus {len(final_ssml_chunks)} SSML-Blöcken...")
        all_audio_bytes = []
        available_voices = get_available_voices(elevenlabs_api_key)
        selected_voice_id = available_voices[st.session_state.selected_voice_name]["voice_id"]
        
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
            
            # Store result in session state
            st.session_state.tts_result = {
                "audio_bytes": final_audio,
                "file_name": f"{Path(st.session_state.uploaded_file_name).stem}_mit_regie.mp3",
                "status": "success",
                "chunks_processed": len(final_ssml_chunks)
            }
        else:
            st.session_state.tts_result = {
                "error": "Fehler bei der Audio-Generierung",
                "status": "failed"
            }
    
    # Store click ID for logging
    st.session_state.tts_click_id = click_id

def run_translation_processing_and_logging(uploaded_file):
    """Comprehensive translation processing function that handles everything in one place."""
    # Generate unique click ID for this button click
    click_id = get_button_click_id()
    
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
            
            # Store failed result
            st.session_state.translation_result = {
                "status": "failed",
                "error_message": "No readable text found",
                "file_name": uploaded_file.name
            }
            st.session_state.translation_click_id = click_id
            return
        
        # Status 2: Übersetzungs-Leitfaden erstellen
        status.write("2. Erstelle Übersetzungs-Leitfaden...")
        translation_guide = generate_translation_guide(german_text, gemini_api_key)
        
        if not translation_guide or "Fehler" in str(translation_guide.get("plot_summary", "")):
            status.update(label="Fehler beim Erstellen des Leitfadens", state="error")
            st.error("Fehler beim Erstellen des Übersetzungs-Leitfadens.")
            
            # Store failed result
            st.session_state.translation_result = {
                "status": "failed",
                "error_message": "Failed to create translation guide",
                "file_name": uploaded_file.name
            }
            st.session_state.translation_click_id = click_id
            return
        
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
    
    # Store results in session state
    st.session_state.translation_result = {
        "translation_guide": translation_guide,
        "final_english_text": final_english_text,
        "german_text": german_text,
        "german_chunks": german_chunks,
        "file_name": uploaded_file.name,
        "status": "success",
        "chunks_processed": len(german_chunks)
    }
    
    # Store click ID for logging
    st.session_state.translation_click_id = click_id

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

logging.info("Streamlit-App gestartet, Tool ausgewählt: %s", selected_tool)


# --- Logik für jedes Werkzeug ---
# Initialize state variables for each tool
if 'tts_step' not in st.session_state:
    st.session_state.tts_step = 1
if 'guideline' not in st.session_state:
    st.session_state.guideline = None
if 'top_3_voices' not in st.session_state:
    st.session_state.top_3_voices = []
if 'text_content' not in st.session_state:
    st.session_state.text_content = None
if 'summary' not in st.session_state:
    st.session_state.summary = None
if 'selected_voice_name' not in st.session_state:
    st.session_state.selected_voice_name = ""
if 'uploaded_file_name' not in st.session_state:
    st.session_state.uploaded_file_name = None

# Initialize result state variables
if 'seo_results' not in st.session_state:
    st.session_state.seo_results = None
if 'seo_url_result' not in st.session_state:
    st.session_state.seo_url_result = None
if 'accessibility_results' not in st.session_state:
    st.session_state.accessibility_results = None
if 'accessibility_export_data' not in st.session_state:
    st.session_state.accessibility_export_data = None
if 'accessibility_summary' not in st.session_state:
    st.session_state.accessibility_summary = None
if 'tts_result' not in st.session_state:
    st.session_state.tts_result = None
if 'translation_result' not in st.session_state:
    st.session_state.translation_result = None

# Clear state when switching tools
if selected_tool != st.session_state.get("last_selected_tool", ""):
    st.session_state.tts_step = 1
    st.session_state.guideline = None
    st.session_state.top_3_voices = []
    st.session_state.text_content = None
    st.session_state.summary = None
    st.session_state.selected_voice_name = ""
    st.session_state.uploaded_file_name = None
    st.session_state.seo_results = None
    st.session_state.seo_url_result = None
    st.session_state.accessibility_results = None
    st.session_state.accessibility_export_data = None
    st.session_state.accessibility_summary = None
    st.session_state.tts_result = None
    st.session_state.translation_result = None
    
    # Clear all logging guards and click IDs when switching tools
    for key in list(st.session_state.keys()):
        if key.startswith("logged_") or key.endswith("_click_id") or key.endswith("_logged"):
            del st.session_state[key]
    
    st.session_state.last_selected_tool = selected_tool

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
                on_click=run_seo_processing_and_logging,
                args=(seo_uploaded_files,)
            )
    
    # --- SEO Results Display ---
    if st.session_state.get("seo_results"):
        st.divider()
        st.subheader("Verarbeitungsergebnisse")
        
        # Log each file individually only once when displaying results
        if st.session_state.get("seo_click_id") and not st.session_state.get("seo_logged"):
            for result in st.session_state.seo_results:
                log_data = {
                    "event_type": "seo_tags_processed",
                    "file_name": result["file_name"],
                    "file_count": 1,
                    "status": result["status"]
                }
                if "error_message" in result:
                    log_data["error_message"] = result["error_message"]
                send_event_to_pubsub(log_data)
            st.session_state.seo_logged = True
        
        for result in st.session_state.seo_results:
            if "error" in result:
                st.error(result["error"])
            else:
                with st.expander(f"✅ SEO Tags für: {result['file_name']}", expanded=True):
                    alt_button_id = f"alt_btn_{result['base_id']}"
                    title_button_id = f"title_btn_{result['base_id']}"
                    col1, col2 = st.columns([1, 3], gap="medium")
                    with col1:
                        st.image(result['image_bytes'], width=150, caption="Vorschau")
                    with col2:
                        st.text("ALT Tag:")
                        st.text_area("ALT", value=result['alt'], height=75, key=f"alt_text_{result['base_id']}", disabled=True, label_visibility="collapsed")
                        alt_json = json.dumps(result['alt'])
                        components.html(f"""<button id="{alt_button_id}">ALT kopieren</button><script>document.getElementById("{alt_button_id}").addEventListener('click', function(){{navigator.clipboard.writeText({alt_json}).then(function(){{let b=document.getElementById("{alt_button_id}");let o=b.innerText;b.innerText='Kopiert!';setTimeout(function(){{b.innerText=o}},1500)}})}});</script><style>#{alt_button_id}{{background-color:#007bff;color:white;border:none;padding:5px 10px;border-radius:5px;cursor:pointer;margin-top:5px}}#{alt_button_id}:hover{{background-color:#0056b3}}</style>""", height=45)
                        
                        st.write("")
                        
                        st.text("TITLE Tag:")
                        st.text_area("TITLE", value=result['title'], height=75, key=f"title_text_{result['base_id']}", disabled=True, label_visibility="collapsed")
                        title_json = json.dumps(result['title'])
                        components.html(f"""<button id="{title_button_id}">TITLE kopieren</button><script>document.getElementById("{title_button_id}").addEventListener('click', function(){{navigator.clipboard.writeText({title_json}).then(function(){{let b=document.getElementById("{title_button_id}");let o=b.innerText;b.innerText='Kopiert!';setTimeout(function(){{b.innerText=o}},1500)}})}});</script><style>#{title_button_id}{{background-color:#007bff;color:white;border:none;padding:5px 10px;border-radius:5px;cursor:pointer;margin-top:5px}}#{title_button_id}:hover{{background-color:#0056b3}}</style>""", height=45)
    
    # --- Logik für Bild-URL ---
    elif input_method == "Bild-URL":
        image_url = st.text_input("Bild-URL einfügen:", placeholder="https://...", key="seo_url_input")
        st.caption("Bitte füge einen direkten Link zu einer Bilddatei ein (z.B. endend auf .jpg, .png).")

        if image_url:
            st.button("🚀 SEO Tags für URL verarbeiten", type="primary", key="process_seo_url_button", on_click=run_seo_url_processing_and_logging, args=(image_url,))
    
    # --- SEO URL Results Display ---
    if st.session_state.get("seo_url_result"):
        st.divider()
        st.subheader("Verarbeitungsergebnis")
        
        # Log URL processing only once when displaying results
        if st.session_state.get("seo_url_click_id") and not st.session_state.get("seo_url_logged"):
            result = st.session_state.seo_url_result
            log_data = {
                "event_type": "seo_url_processed",
                "file_count": 1,
                "status": result["status"]
            }
            if "error_message" in result:
                log_data["error_message"] = result["error_message"]
            send_event_to_pubsub(log_data)
            st.session_state.seo_url_logged = True
        
        result = st.session_state.seo_url_result
        if "error" in result:
            st.error(result["error"])
        else:
            base_id = "seo_url_result"
            alt_button_id = f"alt_btn_{base_id}"
            title_button_id = f"title_btn_{base_id}"
            with st.expander(f"✅ SEO Tags für die URL", expanded=True):
                col1, col2 = st.columns([1, 3], gap="medium")
                with col1:
                    st.image(result["image_url"], width=150, caption="Vorschau")
                with col2:
                    st.text("ALT Tag:")
                    st.text_area("ALT", value=result["alt"], height=75, key=f"alt_text_{base_id}", disabled=True, label_visibility="collapsed")
                    alt_json = json.dumps(result["alt"])
                    components.html(f"""<button id="{alt_button_id}">ALT kopieren</button><script>document.getElementById("{alt_button_id}").addEventListener('click', function(){{navigator.clipboard.writeText({alt_json}).then(function(){{let b=document.getElementById("{alt_button_id}");let o=b.innerText;b.innerText='Kopiert!';setTimeout(function(){{b.innerText=o}},1500)}})}});</script><style>#{alt_button_id}{{background-color:#007bff;color:white;border:none;padding:5px 10px;border-radius:5px;cursor:pointer;margin-top:5px}}#{alt_button_id}:hover{{background-color:#0056b3}}</style>""", height=45)

                    st.write("")

                    st.text("TITLE Tag:")
                    st.text_area("TITLE", value=result["title"], height=75, key=f"title_text_{base_id}", disabled=True, label_visibility="collapsed")
                    title_json = json.dumps(result["title"])
                    components.html(f"""<button id="{title_button_id}">TITLE kopieren</button><script>document.getElementById("{title_button_id}").addEventListener('click', function(){{navigator.clipboard.writeText({title_json}).then(function(){{let b=document.getElementById("{title_button_id}");let o=b.innerText;b.innerText='Kopiert!';setTimeout(function(){{b.innerText=o}},1500)}})}});</script><style>#{title_button_id}{{background-color:#007bff;color:white;border:none;padding:5px 10px;border-radius:5px;cursor:pointer;margin-top:5px}}#{title_button_id}:hover{{background-color:#0056b3}}</style>""", height=45)

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
            on_click=run_accessibility_processing_and_logging,
            args=(accessibility_uploaded_files, ebook_context_input)
        )
    
    # --- Accessibility Results Display ---
    if st.session_state.get("accessibility_results"):
        st.divider()
        st.subheader("Verarbeitungsergebnisse")
        
        # Log each file individually only once when displaying results
        if st.session_state.get("accessibility_click_id") and not st.session_state.get("accessibility_logged"):
            for result in st.session_state.accessibility_results:
                log_data = {
                    "event_type": "accessibility_description_processed",
                    "file_name": result["file_name"],
                    "file_count": 1,
                    "status": result["status"]
                }
                if "error_message" in result:
                    log_data["error_message"] = result["error_message"]
                send_event_to_pubsub(log_data)
            st.session_state.accessibility_logged = True
        
        for result in st.session_state.accessibility_results:
            if "error" in result:
                st.error(result["error"])
            else:
                st.markdown(f"--- \n#### ✅ Ergebnisse für: `{result['file_name']}`")
                col1, col2 = st.columns([1, 3], gap="medium")
                with col1:
                    st.image(result['image_bytes'], width=150, caption="Vorschau")
                with col2:
                    st.text("Kurzbeschreibung (max. 140 Zeichen):")
                    st.text_area("Kurz", value=result['short_desc'], height=100, key=f"short_text_{result['base_id']}", disabled=True, label_visibility="collapsed")
                    short_desc_button_id = f"short_copy_{result['base_id']}"
                    short_json = json.dumps(result['short_desc'])
                    components.html(f"""<button id="{short_desc_button_id}">Kurzbeschreibung kopieren</button><script>document.getElementById("{short_desc_button_id}").addEventListener('click', function(){{navigator.clipboard.writeText({short_json}).then(function(){{let b=document.getElementById("{short_desc_button_id}");let o=b.innerText;b.innerText='Kopiert!';setTimeout(function(){{b.innerText=o}},1500)}})}});</script><style>#{short_desc_button_id}{{background-color:#007bff;color:white;border:none;padding:5px 10px;border-radius:5px;cursor:pointer;margin-top:5px}}#{short_desc_button_id}:hover{{background-color:#0056b3}}</style>""", height=45)
                    
                    with st.expander("Zeige/verberge Langbeschreibung"):
                        st.text_area("Lang", value=result['long_desc'], height=200, key=f"long_text_{result['base_id']}", disabled=True, label_visibility="collapsed")
                        long_desc_button_id = f"long_copy_{result['base_id']}"
                        long_json = json.dumps(result['long_desc'])
                        components.html(f"""<button id="{long_desc_button_id}">Langbeschreibung kopieren</button><script>document.getElementById("{long_desc_button_id}").addEventListener('click', function(){{navigator.clipboard.writeText({long_json}).then(function(){{let b=document.getElementById("{long_desc_button_id}");let o=b.innerText;b.innerText='Kopiert!';setTimeout(function(){{b.innerText=o}},1500)}})}});</script><style>#{long_desc_button_id}{{background-color:#007bff;color:white;border:none;padding:5px 10px;border-radius:5px;cursor:pointer;margin-top:5px}}#{long_desc_button_id}:hover{{background-color:#0056b3}}</style>""", height=45)
        
        # Export section
        if st.session_state.get("accessibility_export_data"):
            st.divider()
            st.subheader("📊 Ergebnisse exportieren")
            df = pd.DataFrame(st.session_state.accessibility_export_data)
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Bildbeschreibungen')
            excel_data = output.getvalue()
            st.download_button(
                label="💾 Excel-Datei herunterladen", data=excel_data,
                file_name="barrierefreie_bildbeschreibungen.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        
        # Summary section
        if st.session_state.get("accessibility_summary"):
            st.divider()
            st.subheader("🏁 Zusammenfassung")
            summary = st.session_state.accessibility_summary
            col1, col2 = st.columns(2)
            col1.metric("Erfolgreich verarbeitet", summary["processed_count"])
            col2.metric("Fehlgeschlagen", summary["failed_count"], delta=None if summary["failed_count"] == 0 else -summary["failed_count"], delta_color="inverse")

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
        if st.button("🎙️ Audio mit KI-Regie generieren", type="primary", key="generate_audio_button", on_click=run_tts_processing_and_logging):
            st.session_state.tts_step = 3
    
    # --- TTS Results Display ---
    if st.session_state.get("tts_result"):
        st.divider()
        st.subheader("🎙️ Audio-Ergebnis")
        
        # Log TTS processing only once when displaying results
        if st.session_state.get("tts_click_id") and not st.session_state.get("tts_logged"):
            result = st.session_state.tts_result
            log_data = {
                "event_type": "text_to_speech_processed",
                "file_count": 1,
                "status": result["status"]
            }
            if "chunks_processed" in result:
                log_data["chunks_processed"] = result["chunks_processed"]
            if "error_message" in result:
                log_data["error_message"] = result["error_message"]
            send_event_to_pubsub(log_data)
            st.session_state.tts_logged = True
        
        if "error" in st.session_state.tts_result:
            st.error(st.session_state.tts_result["error"])
        else:
            st.success("Finale Audiodatei erfolgreich erstellt!")
            st.audio(st.session_state.tts_result["audio_bytes"], format="audio/mpeg")
            st.download_button(
                "MP3-Datei herunterladen", 
                st.session_state.tts_result["audio_bytes"], 
                file_name=st.session_state.tts_result["file_name"],
                mime="audio/mpeg"
            )

elif selected_tool == "Manuskript-Übersetzung":
    st.header("Manuskript-Übersetzung (Deutsch → Englisch)")
    st.caption("Dieses Tool übersetzt deutsche Manuskripte ins Englische mit kontext-bewusster KI für hohe stilistische und terminologische Konsistenz.")

    uploaded_file = st.file_uploader(
        label="Lade dein deutsches Manuskript hoch (.docx oder .pdf)",
        type=['docx', 'pdf'],
        key="translation_uploader"
    )

    if uploaded_file:
        st.button("🚀 Übersetzung starten", type="primary", key="start_translation_button", on_click=run_translation_processing_and_logging, args=(uploaded_file,))
    
    # --- Translation Results Display ---
    if st.session_state.get("translation_result"):
        result = st.session_state.translation_result
        
        # Log translation processing only once when displaying results
        if st.session_state.get("translation_click_id") and not st.session_state.get("translation_logged"):
            log_data = {
                "event_type": "translation_processed",
                "file_name": result["file_name"],
                "file_count": 1,
                "status": result["status"]
            }
            if "chunks_processed" in result:
                log_data["chunks_processed"] = result["chunks_processed"]
            if "error_message" in result:
                log_data["error_message"] = result["error_message"]
            send_event_to_pubsub(log_data)
            st.session_state.translation_logged = True
        
        # Erfolgsmeldung anzeigen
        st.success("✅ Übersetzung erfolgreich abgeschlossen!")
        
        # Style & Glossar-Leitfaden anzeigen
        with st.expander("📋 Style & Glossar-Leitfaden anzeigen", expanded=False):
            st.json(result["translation_guide"])
        
        # Download-Button für das übersetzte Manuskript
        st.download_button(
            label="💾 Übersetztes Manuskript herunterladen (.txt)",
            data=result["final_english_text"].encode('utf-8'),
            file_name=f"übersetzung_{Path(result['file_name']).stem}.txt",
            mime="text/plain"
        )
        
        # Statistiken anzeigen
        st.divider()
        st.subheader("📊 Übersetzungs-Statistiken")
        col1, col2, col3 = st.columns(3)
        col1.metric("Deutsche Wörter", len(result["german_text"].split()))
        col2.metric("Englische Wörter", len(result["final_english_text"].split()))
        col3.metric("Verarbeitete Abschnitte", len(result["german_chunks"]))