# seo_app.py

import streamlit as st
from pathlib import Path
import pandas as pd
from io import BytesIO

# Importiere die Navigation (streamlit-option-menu)
from streamlit_option_menu import option_menu

# Importiere Funktionen aus deinen Modulen
from utils import convert_tiff_to_png_bytes, read_text_from_docx
from api_calls import generate_seo_tags_cached, generate_accessibility_description_cached, generate_audio_from_text, get_available_voices


# --- Seitenkonfiguration & API Keys ---
st.set_page_config(
    page_title="Toolbox",
    page_icon="app_icon.png",
    layout="wide"
)

# Lade die API-Schlüssel aus den Streamlit Secrets
gemini_api_key = st.secrets.get("GOOGLE_API_KEY")
elevenlabs_api_key = st.secrets.get("ELEVENLABS_API_KEY")

# Prüfe, ob die Schlüssel vorhanden sind, bevor die App weiter lädt
if not gemini_api_key:
    st.error("🚨 GOOGLE_API_KEY nicht in den Streamlit Secrets konfiguriert!")
    st.stop() # Stoppt die App
if not elevenlabs_api_key:
    st.error("🚨 ELEVENLABS_API_KEY nicht in den Streamlit Secrets konfiguriert!")
    st.stop() # Stoppt die App


# --- Hauptbereich mit Navigation ---
# Das Menü, das die Tool-Auswahl steuert
selected_tool = option_menu(
    menu_title=None,
    options=["SEO Tags", "Barrierefreie Bildbeschreibung", "Text-to-Speech"], # Die Optionen für die Navigation
    icons=['search', 'universal-access-circle', 'sound-wave'], # Icons für jede Option
    menu_icon="cast", # Optionales Icon für das Menü selbst
    default_index=0, # Startet standardmäßig beim ersten Element
    orientation="horizontal", # Lässt das Menü wie Tabs aussehen
    styles={
        "container": {"padding": "5px !important", "background-color": "#fafafa", "border-radius": "10px"},
        "icon": {"color": "#4A90E2", "font-size": "24px"},
        "nav-link": {
            "font-size": "16px",
            "font-weight": "600",
            "text-align": "center",
            "margin": "0px 5px",
            "--hover-color": "#eee",
            "border-radius": "10px",
        },
        "nav-link-selected": {"background-color": "#007bff"},
    }
)

st.divider() # Visuelle Trennlinie unter der Navigation

# --- Seitenleiste mit dynamischem Inhalt ---
with st.sidebar:
    st.image("app_icon.png", width=100) # Das App-Icon in der Sidebar
    st.markdown("# 🧰 Toolbox") # Haupttitel der App
    st.markdown("##### AI-Tools für dich") # Untertitel
    
    st.divider() # Trennlinie
    
    st.subheader("ℹ️ Info") # Überschrift für den Info-Bereich

    # Dynamischer Info-Text basierend auf der Auswahl im Hauptbereich
    supported_formats_images = "jpg, jpeg, png, gif, bmp, webp, tif, tiff"

    if selected_tool == "SEO Tags":
        st.markdown(f"""
        Erzeuge **Alt** und **Title Tags** mit Gemini.
        
        **Unterstützte Formate:** `{supported_formats_images}`
        
        Bei Fragen -> Gordon
        """)
    elif selected_tool == "Barrierefreie Bildbeschreibung":
        st.markdown(f"""
        Erzeuge **Bildbeschreibungen** mit Gemini.
        
        **Unterstützte Formate:** `{supported_formats_images}`
        
        **Download möglich:** Die Ergebnisse können als Excel-Datei heruntergeladen werden.
        
        Bei Fragen -> Gordon
        """)
    elif selected_tool == "Text-to-Speech":
        st.markdown("""
        Wandle Text aus **Word-Dokumenten** in gesprochene Sprache um.
        
        **Unterstütztes Format:** `.docx`
        
        **API:** ElevenLabs
        
        Bei Fragen -> Gordon
        """)

st.divider() # Visuelle Trennlinie unter der Sidebar-Sektion

# --- Logik für jedes Werkzeug (basierend auf der Navigations-Auswahl) ---

if selected_tool == "SEO Tags":
    st.header("SEO Tags (Alt & Title) generieren")
    st.caption("Dieses Werkzeug erstellt prägnante `alt`- und `title`-Tags für Bilder zur Suchmaschinenoptimierung und grundlegenden Barrierefreiheit.")
    
    # File Uploader für SEO-Tags
    seo_uploaded_files = st.file_uploader(
        "Bilder für SEO Tags hochladen...", accept_multiple_files=True,
        type=['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'tif', 'tiff'], key="seo_uploader"
    )

    if seo_uploaded_files: # Wenn Dateien hochgeladen wurden
        # Button zum Starten der Verarbeitung
        if st.button("🚀 SEO Tags verarbeiten", type="primary", key="process_seo_button"):
            st.subheader("Verarbeitungsergebnisse")
            # Schleife für die Verarbeitung jedes Bildes
            for i, uploaded_file in enumerate(seo_uploaded_files):
                file_name = uploaded_file.name
                safe_file_name_part = "".join(c if c.isalnum() else "_" for c in file_name)
                base_id = f"seo_{i}_{safe_file_name_part}" # Eindeutige ID für Widgets pro Bild
                try:
                    original_image_bytes = uploaded_file.getvalue()
                    image_bytes_for_api = original_image_bytes
                    
                    # TIFF Konvertierung
                    if Path(file_name).suffix.lower() in ['.tif', '.tiff']:
                        with st.spinner(f"Konvertiere {file_name} (TIFF) zu PNG..."):
                            try: image_bytes_for_api = convert_tiff_to_png_bytes(original_image_bytes)
                            except Exception as conv_e: st.error(f"🚨 Fehler beim Konvertieren von '{file_name}': {conv_e}"); continue
                    
                    # Spinner während der Generierung
                    with st.spinner(f"Generiere SEO Tags für {file_name}..."):
                        title, alt = generate_seo_tags_cached(image_bytes_for_api, file_name)
                    
                    # Ergebnisse anzeigen, wenn erfolgreich
                    if title and alt:
                        with st.expander(f"✅ SEO Tags für: {file_name}", expanded=True):
                            # HTML/JS Button IDs
                            alt_button_id, title_button_id = f"alt_btn_{base_id}", f"title_btn_{base_id}"
                            col1, col2 = st.columns([1, 3], gap="medium") # Spalten für Layout
                            with col1: st.image(original_image_bytes, width=150, caption="Vorschau") # Bildvorschau
                            with col2:
                                # ALT Tag Anzeige und Copy Button
                                st.text("ALT Tag:"); st.text_area("ALT", value=alt, height=75, key=f"alt_text_{base_id}", disabled=True, label_visibility="collapsed")
                                alt_json = json.dumps(alt); components.html(f"""<button id="{alt_button_id}">ALT kopieren</button><script>document.getElementById("{alt_button_id}").addEventListener('click', function(){{navigator.clipboard.writeText({alt_json}).then(function(){{let b=document.getElementById("{alt_button_id}");let o=b.innerText;b.innerText='Kopiert!';setTimeout(function(){{b.innerText=o}},1500)}})}});</script><style>#{alt_button_id}{{background-color:#007bff;color:white;border:none;padding:5px 10px;border-radius:5px;cursor:pointer;margin-top:5px}}#{alt_button_id}:hover{{background-color:#0056b3}}</style>""",height=45)
                                st.write(""); # Abstand
                                # TITLE Tag Anzeige und Copy Button
                                st.text("TITLE Tag:")
                                st.text_area("TITLE", value=title, height=75, key=f"title_text_{base_id}", disabled=True, label_visibility="collapsed")
                                title_json = json.dumps(title); components.html(f"""<button id="{title_button_id}">TITLE kopieren</button><script>document.getElementById("{title_button_id}").addEventListener('click', function(){{navigator.clipboard.writeText({title_json}).then(function(){{let b=document.getElementById("{title_button_id}");let o=b.innerText;b.innerText='Kopiert!';setTimeout(function(){{b.innerText=o}},1500)}})}});</script><style>#{title_button_id}{{background-color:#007bff;color:white;border:none;padding:5px 10px;border-radius:5px;cursor:pointer;margin-top:5px}}#{title_button_id}:hover{{background-color:#0056b3}}</style>""",height=45)
                    else: st.error(f"❌ Fehler bei SEO Tag-Generierung für '{file_name}'.")
                except Exception as e: st.error(f"🚨 Unerwarteter FEHLER bei '{file_name}': {e}")
            st.success("SEO-Verarbeitung abgeschlossen.")

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
        if st.button("🚀 Beschreibungen verarbeiten", type="primary", key="process_accessibility_button"):
            st.subheader("Verarbeitungsergebnisse")
            processed_count, failed_count = 0, 0
            results_for_export = [] # Für Excel-Export
            
            for i, uploaded_file in enumerate(accessibility_uploaded_files):
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
                                st.error(f"🚨 Fehler beim Konvertieren von '{file_name}': {conv_e}"); failed_count += 1; continue
                    
                    with st.spinner(f"Generiere barrierefreie Beschreibung für {file_name}..."):
                        short_desc, long_desc = generate_accessibility_description_cached(image_bytes_for_api, file_name, ebook_context_input)
                    if short_desc and long_desc:
                        st.markdown(f"--- \n#### ✅ Ergebnisse für: `{file_name}`")
                        col1, col2 = st.columns([1, 3], gap="medium")
                        with col1: st.image(original_image_bytes, width=150, caption="Vorschau")
                        with col2:
                            st.text("Kurzbeschreibung (max. 140 Zeichen):")
                            st.text_area("Kurz", value=short_desc, height=100, key=f"short_text_{base_id}", disabled=True, label_visibility="collapsed")
                            short_desc_button_id = f"short_copy_{base_id}"; short_json = json.dumps(short_desc)
                            components.html(f"""<button id="{short_desc_button_id}">Kurzbeschreibung kopieren</button><script>document.getElementById("{short_desc_button_id}").addEventListener('click', function(){{navigator.clipboard.writeText({short_json}).then(function(){{let b=document.getElementById("{short_desc_button_id}");let o=b.innerText;b.innerText='Kopiert!';setTimeout(function(){{b.innerText=o}},1500)}})}});</script><style>#{short_desc_button_id}{{background-color:#007bff;color:white;border:none;padding:5px 10px;border-radius:5px;cursor:pointer;margin-top:5px}}#{short_desc_button_id}:hover{{background-color:#0056b3}}</style>""", height=45)
                            
                            with st.expander("Zeige/verberge Langbeschreibung"):
                                st.text_area("Lang", value=long_desc, height=200, key=f"long_text_{base_id}", disabled=True, label_visibility="collapsed")
                                long_desc_button_id = f"long_copy_{base_id}"; long_json = json.dumps(long_desc)
                                components.html(f"""<button id="{long_desc_button_id}">Langbeschreibung kopieren</button><script>document.getElementById("{long_desc_button_id}").addEventListener('click', function(){{navigator.clipboard.writeText({long_json}).then(function(){{let b=document.getElementById("{long_desc_button_id}");let o=b.innerText;b.innerText='Kopiert!';setTimeout(function(){{b.innerText=o}},1500)}})}});</script><style>#{long_desc_button_id}{{background-color:#007bff;color:white;border:none;padding:5px 10px;border-radius:5px;cursor:pointer;margin-top:5px}}#{long_desc_button_id}:hover{{background-color:#0056b3}}</style>""", height=45)
                        
                        processed_count += 1
                        results_for_export.append({
                            "Bildname": file_name, "Dateiname Produktion": "", "Alternativtext": short_desc,
                            "Bildlegende": "", "Anmerkung": "", "Langbeschreibung": long_desc,
                            "(Platzierung/Größe/Übersetzungstexte in der Abbildung/...)": ""
                        })
                    else:
                        st.error(f"❌ Fehler bei Erstellung der barrierefreien Beschreibung für '{file_name}'.")
                        failed_count += 1
                except Exception as e:
                    st.error(f"🚨 Unerwarteter FEHLER bei der Hauptverarbeitung von '{file_name}': {e}")
                    failed_count += 1
            
            # Export Button anzeigen
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
            
            # Finale Zusammenfassung
            st.divider()
            st.subheader("🏁 Zusammenfassung")
            col1, col2 = st.columns(2)
            col1.metric("Erfolgreich verarbeitet", processed_count)
            col2.metric("Fehlgeschlagen", failed_count, delta=None if failed_count == 0 else -failed_count, delta_color="inverse")
            st.success("Verarbeitung abgeschlossen.")

elif selected_tool == "Text-to-Speech":
    st.header("Text-to-Speech mit ElevenLabs")
    st.caption("Lade ein Word-Dokument (.docx) hoch, um den Text in eine Audiodatei umzuwandeln.")
    
    # Lade verfügbare Stimmen
    with st.spinner("Lade verfügbare Stimmen von ElevenLabs..."):
        available_voices = get_available_voices(elevenlabs_api_key)
    
    # Prüfe, ob das Laden der Stimmen erfolgreich war
    if "Fehler" in available_voices:
        st.error("Stimmen konnten nicht von ElevenLabs geladen werden. Bitte API-Schlüssel prüfen.")
    else:
        # UI zur Stimmenauswahl
        selected_voice_name = st.selectbox(
            label="Wähle eine Stimme",
            options=list(available_voices.keys()),
            key="voice_selection" # Eindeutiger Key für die Selectbox
        )
        
        # File Uploader
        docx_file = st.file_uploader(
            label="Word-Dokument (.docx) hochladen",
            type=['docx'],
            key="tts_uploader"
        )

        # Wenn eine Datei hochgeladen wurde und eine Stimme ausgewählt ist
        if docx_file and selected_voice_name:
            selected_voice_id = available_voices[selected_voice_name]
            
            # Button zum Generieren des Audios. Dieser Code-Pfad wird nur einmal erreicht.
            if st.button("🎙️ Audio generieren", type="primary", key="process_tts_button"):
                try:
                    with st.spinner("Lese Text aus Word-Dokument..."):
                        text_content = read_text_from_docx(docx_file)
                    
                    if not text_content or not text_content.strip():
                        st.warning("Das Word-Dokument scheint keinen Text zu enthalten.")
                    else:
                        st.info(f"Text mit {len(text_content)} Zeichen gelesen. Generiere Audio mit Stimme '{selected_voice_name}'...")
                        
                        with st.spinner("Audio wird von ElevenLabs generiert... (Dies kann einige Minuten dauern)"):
                            audio_bytes = generate_audio_from_text(text_content, elevenlabs_api_key, selected_voice_id)
                        
                        if audio_bytes:
                            st.success("Audio erfolgreich generiert!")
                            st.audio(audio_bytes, format="audio/mpeg")
                            st.download_button(
                                label="MP3-Datei herunterladen",
                                data=audio_bytes,
                                file_name=f"{Path(docx_file.name).stem}.mp3",
                                mime="audio/mpeg"
                            )
                        else:
                            st.error(
                                "Audio konnte nicht generiert werden. "
                                "Mögliche Ursachen: Der Text im Dokument ist zu kurz/ungültig oder es gab ein vorübergehendes Serverproblem. "
                                "Bitte prüfe die App-Logs für technische Details."
                            )
                except Exception as e:
                    st.error(f"Ein unerwarteter Fehler ist aufgetreten: {e}")