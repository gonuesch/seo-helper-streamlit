# seo_app.py

import streamlit as st
from pathlib import Path
import pandas as pd
from io import BytesIO
import json # <--- HIER IST DIE KORREKTUR
import streamlit.components.v1 as components

# Importiere die Navigation (streamlit-option-menu)
from streamlit_option_menu import option_menu

# Importiere Funktionen aus deinen Modulen
from utils import convert_tiff_to_png_bytes, read_text_from_docx, read_text_from_pdf, chunk_text
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
    st.stop()
if not elevenlabs_api_key:
    st.error("🚨 ELEVENLABS_API_KEY nicht in den Streamlit Secrets konfiguriert!")
    st.stop()


# --- Hauptbereich mit Navigation ---
selected_tool = option_menu(
    menu_title=None,
    options=["SEO Tags", "Barrierefreie Bildbeschreibung", "Text-to-Speech"],
    icons=['search', 'universal-access-circle', 'sound-wave'],
    menu_icon="cast",
    default_index=0,
    orientation="horizontal",
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

st.divider()

# --- Seitenleiste mit dynamischem Inhalt ---
with st.sidebar:
    st.image("app_icon.png", width=100)
    st.markdown("# 🧰 Toolbox")
    st.markdown("##### AI-Tools für dich")
    
    st.divider()
    
    st.subheader("ℹ️ Info")

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
        Wandle Text aus **Word-Dokumenten** oder **PDFs** in gesprochene Sprache um.
        
        **Unterstützte Formate:** `.docx`, `.pdf`
        
        **API:** ElevenLabs
        
        Bei Fragen -> Gordon
        """)

st.divider()

# --- Logik für jedes Werkzeug (basierend auf der Navigations-Auswahl) ---

if selected_tool == "SEO Tags":
    st.header("SEO Tags (Alt & Title) generieren")
    st.caption("Dieses Werkzeug erstellt prägnante `alt`- und `title`-Tags für Bilder zur Suchmaschinenoptimierung und grundlegenden Barrierefreiheit.")
    
    seo_uploaded_files = st.file_uploader(
        "Bilder für SEO Tags hochladen...", accept_multiple_files=True,
        type=['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'tif', 'tiff'], key="seo_uploader"
    )

    if seo_uploaded_files:
        if st.button("🚀 SEO Tags verarbeiten", type="primary", key="process_seo_button"):
            st.subheader("Verarbeitungsergebnisse")
            for i, uploaded_file in enumerate(seo_uploaded_files):
                file_name = uploaded_file.name
                safe_file_name_part = "".join(c if c.isalnum() else "_" for c in file_name)
                base_id = f"seo_{i}_{safe_file_name_part}"
                try:
                    original_image_bytes = uploaded_file.getvalue()
                    image_bytes_for_api = original_image_bytes
                    
                    if Path(file_name).suffix.lower() in ['.tif', '.tiff']:
                        with st.spinner(f"Konvertiere {file_name} (TIFF) zu PNG..."):
                            try:
                                image_bytes_for_api = convert_tiff_to_png_bytes(original_image_bytes)
                            except Exception as conv_e:
                                st.error(f"🚨 Fehler beim Konvertieren von '{file_name}': {conv_e}")
                                continue
                    
                    with st.spinner(f"Generiere SEO Tags für {file_name}..."):
                        title, alt = generate_seo_tags_cached(image_bytes_for_api, file_name)
                    
                    if title and alt:
                        with st.expander(f"✅ SEO Tags für: {file_name}", expanded=True):
                            alt_button_id, title_button_id = f"alt_btn_{base_id}", f"title_btn_{base_id}"
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
                        st.error(f"❌ Fehler bei SEO Tag-Generierung für '{file_name}'.")
                except Exception as e:
                    st.error(f"🚨 Unerwarteter FEHLER bei '{file_name}': {e}")
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
            results_for_export = []
            
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
                                st.error(f"🚨 Fehler beim Konvertieren von '{file_name}': {conv_e}")
                                failed_count += 1
                                continue
                    
                    with st.spinner(f"Generiere barrierefreie Beschreibung für {file_name}..."):
                        short_desc, long_desc = generate_accessibility_description_cached(image_bytes_for_api, file_name, ebook_context_input)
                    
                    if short_desc and long_desc:
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
                        st.error(f"❌ Fehler bei Erstellung der barrierefreien Beschreibung für '{file_name}'.")
                        failed_count += 1
                except Exception as e:
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

elif selected_tool == "Text-to-Speech":
    st.header("Text-to-Speech mit ElevenLabs")
    st.caption("Lade ein Word-Dokument (.docx) oder eine PDF-Datei (.pdf) hoch, um den Text in eine Audiodatei umzuwandeln.")
    
    with st.spinner("Lade verfügbare Stimmen von ElevenLabs..."):
        available_voices = get_available_voices(elevenlabs_api_key)
    
    if "Fehler" in available_voices:
        st.error("Stimmen konnten nicht von ElevenLabs geladen werden. Bitte API-Schlüssel prüfen.")
    else:
        selected_voice_name = st.selectbox(
            label="1. Wähle eine Stimme",
            options=list(available_voices.keys()),
            key="voice_selection"
        )
        
        if selected_voice_name:
            st.write("Stimmprobe:")
            preview_url = available_voices[selected_voice_name].get("preview_url")
            if preview_url:
                st.audio(preview_url)
            else:
                st.info("Für diese Stimme ist keine Vorschau verfügbar.")
        
        st.divider()

        docx_file = st.file_uploader(
            label="2. Lade deine Datei hoch",
            type=['docx', 'pdf'],
            key="tts_uploader"
        )

        if docx_file and selected_voice_name:
            selected_voice_id = available_voices[selected_voice_name]["voice_id"]
            
            if st.button("🎙️ Audio generieren", type="primary", key="process_tts_button"):
                try:
                    text_content = ""
                    with st.spinner("Lese Text aus Datei..."):
                        if docx_file.type == "application/pdf":
                            text_content = read_text_from_pdf(docx_file)
                        else:
                            text_content = read_text_from_docx(docx_file)
                    
                    if not text_content or not text_content.strip():
                        st.warning("Das Dokument scheint keinen lesbaren Text zu enthalten.")
                    elif text_content == "NO_TEXT_IN_PDF":
                        st.warning("Die PDF-Datei enthält keinen extrahierbaren Text. Möglicherweise ist es ein reines Bild-Dokument (Scan).")
                    else:
                        st.info(f"Text mit {len(text_content)} Zeichen gelesen. Teile ihn in kleinere Stücke auf...")
                        
                        text_chunks = chunk_text(text_content)
                        st.info(f"Text wurde in {len(text_chunks)} Teile aufgeteilt. Generiere jetzt Audio für jeden Teil...")

                        all_audio_bytes = []
                        progress_bar = st.progress(0, text="Audio-Generierung startet...")

                        for i, chunk in enumerate(text_chunks):
                            progress_text = f"Generiere Audio für Teil {i+1}/{len(text_chunks)}..."
                            progress_bar.progress((i) / len(text_chunks), text=progress_text)
                            
                            audio_segment = generate_audio_from_text(chunk, elevenlabs_api_key, selected_voice_id)
                            if audio_segment:
                                all_audio_bytes.append(audio_segment)
                            else:
                                st.error(f"Fehler bei der Audio-Generierung für Teil {i+1}. Breche ab.")
                                break

                        progress_bar.progress(1.0, text="Verarbeitung abgeschlossen!")

                        if len(all_audio_bytes) == len(text_chunks):
                            final_audio = b"".join(all_audio_bytes)
                            
                            st.success("Audio erfolgreich generiert!")
                            st.audio(final_audio, format="audio/mpeg")
                            st.download_button(
                                label="MP3-Datei herunterladen",
                                data=final_audio,
                                file_name=f"{Path(docx_file.name).stem}.mp3",
                                mime="audio/mpeg"
                            )
                        else:
                            st.error("Nicht alle Audio-Teile konnten erfolgreich generiert werden.")

                except Exception as e:
                    st.error(f"Ein unerwarteter Fehler ist aufgetreten: {e}")