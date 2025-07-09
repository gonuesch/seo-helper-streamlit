# seo_app.py

import streamlit as st
from pathlib import Path
import pandas as pd
from io import BytesIO
import json
import streamlit.components.v1 as components
from streamlit_option_menu import option_menu

# Importiere Funktionen aus deinen Modulen
from utils import convert_tiff_to_png_bytes, read_text_from_docx, read_text_from_pdf, chunk_text
from api_calls import generate_seo_tags_cached, generate_accessibility_description_cached, generate_audio_from_text, get_available_voices, generate_text_summary, get_voice_recommendations, generate_ssml_chunk

# --- Seitenkonfiguration ---
st.set_page_config(page_title="Toolbox", page_icon="app_icon.png", layout="wide")

# --- HAUPTLOGIK: LOGIN ODER APP ANZEIGEN ---
# st.login() liest seine Konfiguration automatisch aus den Secrets,
# wenn sie mit "auth_" beginnen (z.B. auth_client_id).
if not st.user.is_logged_in:
    st.title("🧰 Toolbox")
    st.info("Bitte melde dich an, um die KI-Tools zu nutzen.")
    st.button("Mit Google einloggen", on_click=st.login, args=("google",), key="google_login_button")
else:
    # Wenn der Nutzer eingeloggt ist:
    user_email = st.user.email
    allowed_domains = [
    "rowohlt.de",
    "droemer-knaur.de",
    "fischerverlage.de",
    "chaptr.xyz",
    "kiwi-verlag.de",
    "argon.de",
    "hgv-online.de",
    "fischer-sauerlaender.de",
    "holtzbrinck-buchverlage.de",
    "galiani.de"
]

    # Prüfe die E-Mail-Domain
    if user_email.split('@')[1] not in allowed_domains:
        st.error(f"Zugriff verweigert. Die E-Mail-Domain '@{user_email.split('@')[1]}' ist nicht für den Zugriff auf dieses Tool berechtigt.")
        st.button("Logout", on_click=st.logout, key="logout_button_denied")
    else:
        # ==============================================================================
        # HIER BEGINNT DIE VOLLSTÄNDIGE ANWENDUNG
        # ==============================================================================
        
        # Lade die API-Schlüssel für die Tools
        gemini_api_key = st.secrets.get("GOOGLE_API_KEY")
        elevenlabs_api_key = st.secrets.get("ELEVENLABS_API_KEY")

        if not all([gemini_api_key, elevenlabs_api_key]):
            st.error("🚨 Tool-API-Schlüssel sind nicht konfiguriert. Bitte den Admin informieren.")
            st.stop()

        # --- Seitenleiste ---
        with st.sidebar:
            st.image("app_icon.png", width=100)
            st.markdown(f"Willkommen, **{st.user.name}**!")
            st.button("Logout", on_click=st.logout, key="logout_button_sidebar")
            st.divider()
            st.markdown("# 🧰 Toolbox")
            st.markdown("##### AI-Tools für dich")
            st.divider()
            st.subheader("ℹ️ Info")

        # --- Hauptbereich mit Navigation ---
        selected_tool = option_menu(
            menu_title=None,
            options=["SEO Tags", "Barrierefreie Bildbeschreibung", "Text-to-Speech"],
            icons=['search', 'universal-access-circle', 'sound-wave'],
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

        st.divider()

        # --- Logik für jedes Werkzeug ---
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
                if st.button("🚀 SEO Tags für Dateien verarbeiten", type="primary", key="process_seo_files_button"):
                    st.subheader("Verarbeitungsergebnisse")
                    for i, uploaded_file in enumerate(seo_uploaded_files):
                        file_name = uploaded_file.name
                        safe_file_name_part = "".join(c if c.isalnum() else "_" for c in file_name)
                        base_id = f"seo_file_{i}_{safe_file_name_part}"
                        try:
                            original_image_bytes = uploaded_file.getvalue()
                            
                            with st.spinner(f"Generiere SEO Tags für {file_name}..."):
                                title, alt = generate_seo_tags_cached(original_image_bytes, file_name)
                            
                            if title and alt:
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
                                st.error(f"❌ Fehler bei SEO Tag-Generierung für '{file_name}'.")
                        except Exception as e:
                            st.error(f"🚨 Unerwarteter FEHLER bei '{file_name}': {e}")
                    st.success("SEO-Verarbeitung abgeschlossen.")
        
        # --- Logik für Bild-URL ---
        elif input_method == "Bild-URL":
            image_url = st.text_input("Bild-URL einfügen:", placeholder="https://...", key="seo_url_input")

            if image_url:
                if st.button("🚀 SEO Tags für URL verarbeiten", type="primary", key="process_seo_url_button"):
                    with st.spinner(f"Verarbeite Bild von URL..."):
                        try:
                            title, alt = generate_seo_tags_cached(image_url, image_url)
                            
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

        elif selected_tool == "Text-to-Speech":
            st.header("Text-to-Speech mit KI-Regieanweisung")
            st.caption("Dieses Tool analysiert deinen Text, um eine passende Stimme vorzuschlagen und eine natürliche Sprachausgabe zu erzeugen.")

            # Session State initialisieren
            if "tts_step" not in st.session_state:
                st.session_state.tts_step = 1
                st.session_state.guideline = None
                st.session_state.top_3_voices = []
                st.session_state.text_content = None
                st.session_state.summary = None
                st.session_state.selected_voice_name = ""
                st.session_state.uploaded_file_name = None

            # --- SCHRITT 1: DATEI HOCHLADEN ---
            if st.session_state.tts_step < 3:
                st.subheader("1. Dokument hochladen")
                uploaded_file = st.file_uploader(
                    label="Lade dein Dokument hoch (.docx oder .pdf)",
                    type=['docx', 'pdf'],
                    key="tts_uploader"
                )

            # Button zum Zurücksetzen/Neustarten
            if st.session_state.tts_step > 1:
                if st.button("Neue Analyse starten"):
                    # Setze alle relevanten Session States zurück
                    st.session_state.tts_step = 1
                    st.session_state.guideline = None
                    st.session_state.top_3_voices = []
                    st.session_state.text_content = None
                    st.session_state.summary = None
                    st.session_state.selected_voice_name = ""
                    st.session_state.uploaded_file_name = None
                    st.rerun()

            if 'uploaded_file' not in locals():
                uploaded_file = None 

            if uploaded_file and st.session_state.tts_step == 1:
                # --- SCHRITT 2: ANALYSE STARTEN ---
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
                            summary = generate_text_summary(text_content)
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
                            guideline, recommendations = get_voice_recommendations(summary, voices_info_for_prompt)
                            
                            st.session_state.guideline = guideline
                            st.session_state.top_3_voices = recommendations
                            status.update(label="Analyse abgeschlossen!", state="complete", expanded=False)
                        
                        st.session_state.tts_step = 2
                        st.rerun()

            # Nach erfolgreicher Analyse werden die Ergebnisse angezeigt
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
                    except ValueError:
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

            # Nach Klick auf "Generieren" wird die Verarbeitung gestartet
            if st.session_state.tts_step == 3:
                final_selected_voice = st.session_state.selected_voice_name
                
                st.info(f"Audio-Generierung mit der Stimme '{final_selected_voice}' wird vorbereitet...")

                with st.status("Generiere Audio-Datei...", expanded=True) as status:
                    status.write("Teile Text in initiale Stücke (Chunks)...")
                    initial_chunks = chunk_text(st.session_state.text_content, 8000)
                    
                    final_ssml_chunks = []
                    
                    for i, chunk in enumerate(initial_chunks):
                        status.write(f"Verarbeite initialen Chunk {i+1}/{len(initial_chunks)}: Erzeuge SSML...")
                        ssml_chunk = generate_ssml_chunk(st.session_state.guideline, chunk)
                        
                        if len(ssml_chunk) < 9800:
                            final_ssml_chunks.append(ssml_chunk)
                        else:
                            status.warning(f"Chunk {i+1} ist nach SSML zu lang ({len(ssml_chunk)} Zeichen). Teile ihn auf...")
                            sub_chunks = chunk_text(chunk, 4000)
                            
                            for sub_chunk in sub_chunks:
                                final_ssml_chunks.append(generate_ssml_chunk(st.session_state.guideline, sub_chunk))
                    
                    status.write(f"Finale Audio-Generierung aus {len(final_ssml_chunks)} SSML-Blöcken...")
                    all_audio_bytes = []
                    available_voices = get_available_voices(elevenlabs_api_key)
                    selected_voice_id = available_voices[final_selected_voice]["voice_id"]
                    
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