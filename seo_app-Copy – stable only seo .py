# -*- coding: utf-8 -*-

import os
import streamlit as st
import google.generativeai as genai
from PIL import Image
import time
from io import BytesIO # Wichtig für In-Memory Bildverarbeitung
from typing import Union
import json
import streamlit.components.v1 as components
from google.api_core.exceptions import ResourceExhausted
from pathlib import Path # Hinzugefügt für Dateiendungen

# --- Grundkonfiguration & API Key ---
st.set_page_config(page_title="SEO Bild-Tag Generator", layout="wide")

st.title("🤖 SEO Bild-Tag Generator (Cloud Version)")
st.write("""
    Lade ein oder mehrere Bilder hoch. Diese App analysiert sie mithilfe der Gemini API
    und generiert SEO-optimierte 'alt'- und 'title'-Attribute.
    Unterstützt jetzt auch TIFF-Bilder (werden zu PNG konvertiert).
""")

# API Key aus Streamlit Secrets lesen
api_key = st.secrets.get("GOOGLE_API_KEY")

# Prüfen ob API Key vorhanden ist
if not api_key:
    st.error("🚨 Fehler: GOOGLE_API_KEY nicht in den Streamlit Secrets konfiguriert! Bitte füge ihn in den App-Einstellungen unter 'Settings' -> 'Secrets' hinzu.")
    st.stop() # App anhalten, wenn kein Key da ist
else:
    # Versuche Gemini zu konfigurieren
    try:
        genai.configure(api_key=api_key)
    except Exception as e:
        st.error(f"🚨 Fehler bei der Konfiguration von Gemini mit dem API Key: {e}")
        st.stop() # App anhalten bei Konfigurationsfehler

# --- Kernfunktion: Tag-Generierung (Gecacht) ---
@st.cache_data
def generate_image_tags_cached(image_bytes_for_api, file_name_for_log: str, model_name: str = "gemini-1.5-pro-latest") -> tuple[Union[str, None], Union[str, None]]:
    """
    Nimmt Bild-Bytes (bereits im API-kompatiblen Format), sendet sie an Gemini
    und gibt SEO-optimierte Tags zurück. Fängt ResourceExhausted Fehler ab.
    """
    try:
        # Erstelle PIL Image aus den Bytes für die API (sollten bereits PNG etc. sein)
        img = Image.open(BytesIO(image_bytes_for_api))

        model = genai.GenerativeModel(model_name)
        prompt = """
        Analysiere das folgende Bild sorgfältig.
        Deine Aufgabe ist es, SEO-optimierte HTML-Attribute für dieses Bild zu generieren:
        1. Ein 'alt'-Attribut (Alternativtext)
        2. Ein 'title'-Attribut

        Beachte dabei die aktuellen SEO Best Practices:
        - Das 'alt'-Attribut muss das Bild präzise und prägnant beschreiben. Es ist entscheidend für Barrierefreiheit (Screenreader) und das Verständnis des Bildinhalts durch Suchmaschinen. Beschreibe Objekte, Personen, Aktionen und ggf. Text im Bild. Vermeide Keyword-Stuffing.
        - Das 'title'-Attribut wird oft als Tooltip beim Überfahren mit der Maus angezeigt. Es kann zusätzliche kontextbezogene Informationen liefern, die über die reine Beschreibung des 'alt'-Attributs hinausgehen, sollte aber ebenfalls relevant sein.

        Gib *nur* die beiden Attribute im folgenden Format zurück, ohne zusätzliche Erklärungen oder Formatierungen:

        ALT: [Hier der generierte Alt-Text]
        TITLE: [Hier der generierte Title-Text]
        """
        try:
            response = model.generate_content([prompt, img], request_options={"timeout": 120})
        except ResourceExhausted as e:
            print(f"Rate limit exceeded for {file_name_for_log}: {e}") # Log in Streamlit Cloud Logs
            return None, None 
        
        generated_text = response.text.strip()
        alt_tag = None
        title_tag = None
        lines = generated_text.split('\n')
        for line in lines:
            if line.strip().upper().startswith("ALT:"):
                alt_tag = line.strip()[len("ALT:"):].strip()
            elif line.strip().upper().startswith("TITLE:"):
                title_tag = line.strip()[len("TITLE:"):].strip()

        if alt_tag and title_tag:
            return title_tag, alt_tag
        else:
            print(f"Warning: Could not extract tags for {file_name_for_log}. Raw response: {generated_text}")
            return None, None
    except Exception as e:
        print(f"Error during Gemini processing for {file_name_for_log}: {e}")
        try:
             if 'response' in locals() and response and hasattr(response, 'prompt_feedback'):
                 print(f"Prompt Feedback: {response.prompt_feedback}")
        except Exception:
            pass
        return None, None

# --- Streamlit UI & Verarbeitungslogik ---
st.divider()

# File Uploader für mehrere Bilder, jetzt mit TIFF-Unterstützung
uploaded_files = st.file_uploader(
    "Lade ein oder mehrere Bilder hoch...",
    accept_multiple_files=True,
    type=['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'tif', 'tiff'], # TIFF hinzugefügt
    key="file_uploader"
)

st.divider()

if uploaded_files:
    st.info(f"{len(uploaded_files)} Bild(er) zum Hochladen ausgewählt.")

    if st.button("🚀 Ausgewählte Bilder verarbeiten", type="primary", key="process_button"):
        st.subheader("Verarbeitungsergebnisse")
        processed_count = 0
        failed_count = 0
        status_placeholder = st.empty()

        for i, uploaded_file in enumerate(uploaded_files):
            file_name = uploaded_file.name
            safe_file_name_part = "".join(c if c.isalnum() else "_" for c in file_name)
            base_id = f"file_{i}_{safe_file_name_part}"
            alt_button_id = f"alt_btn_{base_id}"
            title_button_id = f"title_btn_{base_id}"

            status_placeholder.info(f"Verarbeite Bild {i+1}/{len(uploaded_files)}: {file_name}...")

            try:
                original_image_bytes = uploaded_file.getvalue()
                image_bytes_for_api = original_image_bytes # Standard

                # TIFF Konvertierung
                file_extension = Path(file_name).suffix.lower()
                if file_extension in ['.tif', '.tiff']:
                    try:
                        with st.spinner(f"Konvertiere {file_name} (TIFF) zu PNG für die Analyse..."):
                            pil_image = Image.open(BytesIO(original_image_bytes))
                            
                            if getattr(pil_image, "is_animated", False) or getattr(pil_image, "n_frames", 1) > 1:
                                pil_image.seek(0) # Ersten Frame verwenden
                            
                            # In RGB konvertieren, um Kompatibilität für PNG sicherzustellen
                            # (außer es ist bereits RGB, RGBA oder L (Graustufen))
                            if pil_image.mode not in ('RGB', 'RGBA', 'L'):
                                if pil_image.mode == 'P' and 'transparency' in pil_image.info: # Palette mit Transparenz
                                    pil_image = pil_image.convert('RGBA')
                                else:
                                    pil_image = pil_image.convert('RGB')
                            
                            output_buffer = BytesIO()
                            pil_image.save(output_buffer, format="PNG")
                            image_bytes_for_api = output_buffer.getvalue()
                        # Die Erfolgsmeldung hier kann man auch weglassen, um die UI nicht zu überladen
                        # st.success(f"'{file_name}' (TIFF) erfolgreich zu PNG für API konvertiert.")
                    except Exception as conv_e:
                        st.error(f"🚨 Fehler beim Konvertieren der TIFF-Datei '{file_name}': {conv_e}")
                        failed_count += 1
                        continue # Nächstes Bild in der Schleife
                
                # (Die feste time.sleep(32) wurde hier bereits entfernt)

                with st.spinner(f"Generiere Tags für {file_name}..."):
                    # Übergebe die (ggf. konvertierten) Bytes an die API-Funktion
                    title, alt = generate_image_tags_cached(image_bytes_for_api, file_name)

                if title and alt:
                    with st.expander(f"✅ Ergebnisse für: {file_name}", expanded=True):
                        col1, col2 = st.columns([1, 3], gap="medium")
                        with col1:
                            # Zeige Originalbild-Bytes für die Vorschau
                            st.image(original_image_bytes, width=150, caption="Vorschau")
                        with col2:
                            st.text("ALT Tag:")
                            st.text_area("ALT", value=alt, height=75, key=f"alt_text_{base_id}", disabled=True, label_visibility="collapsed")
                            alt_json = json.dumps(alt)
                            components.html(
                                f"""
                                <button id="{alt_button_id}">ALT kopieren</button>
                                <script>
                                    document.getElementById("{alt_button_id}").addEventListener('click', function() {{
                                        navigator.clipboard.writeText({alt_json}).then(function() {{
                                            let btn = document.getElementById("{alt_button_id}");
                                            let originalText = btn.innerText;
                                            btn.innerText = 'Kopiert!';
                                            setTimeout(function(){{ btn.innerText = originalText; }}, 1500);
                                        }}, function(err) {{
                                            console.error('Fehler: Konnte ALT-Tag nicht kopieren: ', err);
                                            alert("Fehler beim Kopieren des ALT-Tags!");
                                        }});
                                    }});
                                </script>
                                <style>
                                    #{alt_button_id} {{ background-color: #007bff; color: white; border: none;
                                        padding: 5px 10px; border-radius: 5px; cursor: pointer; margin-top: 5px; }}
                                    #{alt_button_id}:hover {{ background-color: #0056b3; }}
                                </style>
                                """, height=45
                            )
                            st.write("")
                            st.text("TITLE Tag:")
                            st.text_area("TITLE", value=title, height=75, key=f"title_text_{base_id}", disabled=True, label_visibility="collapsed")
                            title_json = json.dumps(title)
                            components.html(
                                f"""
                                <button id="{title_button_id}">TITLE kopieren</button>
                                <script>
                                    document.getElementById("{title_button_id}").addEventListener('click', function() {{
                                        navigator.clipboard.writeText({title_json}).then(function() {{
                                            let btn = document.getElementById("{title_button_id}");
                                            let originalText = btn.innerText;
                                            btn.innerText = 'Kopiert!';
                                            setTimeout(function(){{ btn.innerText = originalText; }}, 1500);
                                        }}, function(err) {{
                                            console.error('Fehler: Konnte TITLE-Tag nicht kopieren: ', err);
                                            alert("Fehler beim Kopieren des TITLE-Tags!");
                                        }});
                                    }});
                                </script>
                                <style>
                                    #{title_button_id} {{ background-color: #007bff; color: white; border: none;
                                        padding: 5px 10px; border-radius: 5px; cursor: pointer; margin-top: 5px; }}
                                    #{title_button_id}:hover {{ background-color: #0056b3; }}
                                </style>
                                """, height=45
                            )
                    processed_count += 1
                else:
                    st.error(f"❌ Fehler bei der Tag-Generierung für '{file_name}'. Rate Limit erreicht oder Tags nicht extrahierbar (siehe Logs).")
                    failed_count += 1

            except Exception as e:
               st.error(f"🚨 Unerwarteter FEHLER bei der Hauptverarbeitung von '{file_name}': {e}")
               failed_count += 1
        
        status_placeholder.empty()
        st.divider()
        st.subheader("🏁 Zusammenfassung")
        col1, col2 = st.columns(2)
        col1.metric("Erfolgreich verarbeitet", processed_count)
        col2.metric("Fehlgeschlagen", failed_count, delta=None if failed_count == 0 else -failed_count, delta_color="inverse")
        st.success("Verarbeitung abgeschlossen.")
else:
    st.info("Bitte lade Bilder über den Uploader oben hoch.")

st.sidebar.title("ℹ️ Info")
st.sidebar.write("Diese App nutzt die Google Gemini API zur Generierung von Bild-Tags.")
st.sidebar.text(f"Unterstützte Formate: {', '.join(['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'tif', 'tiff'])}") # Sidebar aktualisiert
st.sidebar.text("Bei Fragen -> Gordon")