# -*- coding: utf-8 -*-

import os
import streamlit as st
import google.generativeai as genai
from PIL import Image
import time
from io import BytesIO
from typing import Union
import json # NEU: Import für sicheres Einbetten von Strings in JS

# Import für HTML/JS Komponenten
import streamlit.components.v1 as components

# --- Grundkonfiguration & API Key ---
st.set_page_config(page_title="SEO Bild-Tag Generator", layout="wide")
st.title("🤖 SEO Bild-Tag Generator (Cloud Version)")
# ... (Beschreibung, API Key check bleiben gleich) ...
api_key = st.secrets.get("GOOGLE_API_KEY")
if not api_key:
    st.error("🚨 Fehler: GOOGLE_API_KEY nicht in den Streamlit Secrets konfiguriert!")
    st.stop()
else:
    try:
        genai.configure(api_key=api_key)
    except Exception as e:
        st.error(f"🚨 Fehler bei der Konfiguration von Gemini: {e}")
        st.stop()

# --- Kernfunktion: Tag-Generierung (Gecacht) ---
@st.cache_data
def generate_image_tags_cached(image_bytes, file_name_for_log: str, model_name: str = "gemini-1.5-pro-latest") -> tuple[Union[str, None], Union[str, None]]:
    # ... (Funktionskörper bleibt unverändert) ...
    try:
        img = Image.open(BytesIO(image_bytes))
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
        response = model.generate_content([prompt, img], request_options={"timeout": 120})
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
             if response and hasattr(response, 'prompt_feedback'):
                 print(f"Prompt Feedback: {response.prompt_feedback}")
        except Exception:
            pass
        return None, None


# --- Streamlit UI & Verarbeitungslogik ---
st.divider()
uploaded_files = st.file_uploader(
    "Lade ein oder mehrere Bilder hoch...",
    accept_multiple_files=True,
    type=['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp'],
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
            # Erzeuge eindeutige IDs für HTML-Elemente dieses Bildes
            base_id = f"file_{i}_{file_name.replace('.', '_').replace(' ', '_')}" # Basis-ID aus Index und Dateinamen
            alt_button_id = f"alt_btn_{base_id}"
            title_button_id = f"title_btn_{base_id}"

            status_placeholder.info(f"Verarbeite Bild {i+1}/{len(uploaded_files)}: {file_name}...")

            try:
                image_bytes = uploaded_file.getvalue()
                with st.spinner(f"Warte wegen Rate Limit (~32s) für {file_name}..."):
                    time.sleep(32)
                title, alt = generate_image_tags_cached(image_bytes, file_name)

                if title and alt:
                    with st.expander(f"✅ Ergebnisse für: {file_name}", expanded=True):
                        col1, col2 = st.columns([1, 3], gap="medium")
                        with col1:
                            st.image(image_bytes, width=150, caption="Vorschau")
                        with col2:
                            st.text("ALT Tag:")
                            st.text_area("ALT", value=alt, height=75, key=f"alt_text_{base_id}", disabled=True, label_visibility="collapsed")
                            # === NEU: HTML/JS für ALT Copy Button ===
                            # Sicheres Einbetten des alt-Strings in JS mit json.dumps
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
                                            setTimeout(function(){{ btn.innerText = originalText; }}, 1500); // Text nach 1.5s zurücksetzen
                                        }}, function(err) {{
                                            console.error('Fehler: Konnte ALT-Tag nicht kopieren: ', err);
                                            alert("Fehler beim Kopieren des ALT-Tags!");
                                        }});
                                    }});
                                </script>
                                <style>
                                    #{alt_button_id} {{
                                        background-color: #007bff; color: white; border: none;
                                        padding: 5px 10px; border-radius: 5px; cursor: pointer; margin-top: 5px;
                                    }}
                                    #{alt_button_id}:hover {{ background-color: #0056b3; }}
                                </style>
                                """,
                                height=45 # Höhe für Button + etwas Platz
                            )

                            st.write("") # Abstand

                            st.text("TITLE Tag:")
                            st.text_area("TITLE", value=title, height=75, key=f"title_text_{base_id}", disabled=True, label_visibility="collapsed")
                            # === NEU: HTML/JS für TITLE Copy Button ===
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
                                    #{title_button_id} {{
                                        background-color: #007bff; color: white; border: none;
                                        padding: 5px 10px; border-radius: 5px; cursor: pointer; margin-top: 5px;
                                    }}
                                    #{title_button_id}:hover {{ background-color: #0056b3; }}
                                </style>
                                """,
                                height=45
                            )
                    processed_count += 1
                else:
                    st.error(f"❌ Fehler bei der Tag-Generierung für '{file_name}'. Keine Tags erhalten.")
                    failed_count += 1

            except Exception as e:
               st.error(f"🚨 Unerwarteter FEHLER bei der Verarbeitung von '{file_name}': {e}")
               failed_count += 1

        status_placeholder.empty()
        st.divider()
        st.subheader("🏁 Zusammenfassung")
        # ... (Zusammenfassung bleibt gleich) ...
        col1, col2 = st.columns(2)
        col1.metric("Erfolgreich verarbeitet", processed_count)
        col2.metric("Fehlgeschlagen", failed_count, delta=None if failed_count == 0 else -failed_count, delta_color="inverse")
        st.success("Verarbeitung abgeschlossen.")

else:
    st.info("Bitte lade Bilder über den Uploader oben hoch.")

st.sidebar.title("ℹ️ Info")
st.sidebar.write("Diese App nutzt die Google Gemini API zur Generierung von Bild-Tags.")
st.sidebar.caption("Entwickelt als Beispiel.")