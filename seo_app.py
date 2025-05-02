# -*- coding: utf-8 -*-

import os
import streamlit as st
import google.generativeai as genai
from PIL import Image
from pathlib import Path
# from dotenv import load_dotenv # Nicht mehr für Cloud benötigt
import time
from io import BytesIO # Für die Verarbeitung von Upload-Bytes
from typing import Union
# Ggf. auch BytesIO importieren, falls im Code verwendet, aber nicht importiert
from io import BytesIO

# --- Grundkonfiguration & API Key ---

st.set_page_config(page_title="SEO Bild-Tag Generator", layout="wide")

st.title("🤖 SEO Bild-Tag Generator (Cloud Version)")
st.write("""
    Lade ein oder mehrere Bilder hoch. Diese App analysiert sie mithilfe der Gemini API
    und generiert SEO-optimierte 'alt'- und 'title'-Attribute.
""")

# === ÄNDERUNG: API Key aus Streamlit Secrets ===
# Versuche, den Key aus den Secrets zu lesen
api_key = st.secrets.get("GOOGLE_API_KEY")

if not api_key:
    st.error("🚨 Fehler: GOOGLE_API_KEY nicht in den Streamlit Secrets konfiguriert! Bitte füge ihn in den App-Einstellungen hinzu.")
    st.stop()
else:
    try:
        genai.configure(api_key=api_key)
    except Exception as e:
        st.error(f"🚨 Fehler bei der Konfiguration von Gemini: {e}")
        st.stop()

# --- Kernfunktion: Tag-Generierung (Angepasst für UploadedFile) ---

# === ÄNDERUNG: Akzeptiert BytesIO oder UploadedFile ===
def generate_image_tags(image_input, file_name_for_log: str, model_name: str = "gemini-1.5-pro-latest") -> tuple[Union[str, None], Union[str, None]]:
    """
    Nimmt ein Bild (als BytesIO oder Streamlit UploadedFile), sendet es an Gemini
    und gibt SEO-optimierte title- und alt-Tags zurück.
    """
    try:
        # PIL kann direkt mit file-like Objekten umgehen
        img = Image.open(image_input)

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

        # Längere Pause wegen Free Tier Rate Limit
        # Im Cloud-Deployment ist das Limit evtl. höher, aber sicher ist sicher
        time.sleep(32) # Behalte die Pause vorerst bei

        generated_text = response.text.strip()
        alt_tag = None
        title_tag = None
        lines = generated_text.split('\n')
        for line in lines:
            if line.upper().startswith("ALT:"):
                alt_tag = line[len("ALT:"):].strip()
            elif line.upper().startswith("TITLE:"):
                title_tag = line[len("TITLE:"):].strip()

        if alt_tag and title_tag:
            return title_tag, alt_tag
        else:
            st.warning(f"⚠️ Konnte Tags nicht korrekt aus Antwort extrahieren für {file_name_for_log}.")
            st.text(f"Rohe Antwort: {generated_text}") # Zeige die Antwort zur Fehlersuche
            return None, None

    # === ÄNDERUNG: Breitere Fehlerbehandlung für Uploads ===
    except Exception as e:
        st.error(f"🚨 Fehler bei der Verarbeitung/Analyse von '{file_name_for_log}': {e}")
        # Versuche, Prompt Feedback zu loggen, falls response existiert
        try:
            if response and hasattr(response, 'prompt_feedback'):
               st.warning(f"Prompt Feedback: {response.prompt_feedback}")
        except Exception:
            pass
        return None, None

# --- Streamlit UI & Verarbeitungslogik ---

st.divider()

# === ÄNDERUNG: File Uploader statt fester Ordner ===
uploaded_files = st.file_uploader(
    "Lade ein oder mehrere Bilder hoch...",
    accept_multiple_files=True,
    type=['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp'] # Erlaubte Dateitypen
)

st.divider()

if uploaded_files: # Prüfe, ob Dateien hochgeladen wurden
    st.info(f"{len(uploaded_files)} Bild(er) zum Hochladen ausgewählt.")

    if st.button("🚀 Ausgewählte Bilder verarbeiten", type="primary"):

        st.subheader("Verarbeitungsergebnisse")
        processed_count = 0
        failed_count = 0

        # Iteriere durch die hochgeladenen Dateien
        for uploaded_file in uploaded_files:
            file_name = uploaded_file.name
            st.markdown(f"--- \n**Verarbeite:** `{file_name}`")

            # Zeige Spinner während der Verarbeitung
            with st.spinner(f"Generiere Tags für {file_name}... (inkl. Wartezeit ~32s)"):
                # === ÄNDERUNG: Übergebe das file-like Objekt direkt ===
                # Die Funktion generate_image_tags wurde angepasst, um dies zu akzeptieren
                title, alt = generate_image_tags(uploaded_file, file_name)

            # Zeige Ergebnis für diese Datei
            if title and alt:
                st.success(f"Tags für '{file_name}' generiert:")
                # Verwende st.code oder st.text_area für gute Lesbarkeit
                st.code(f"ALT: {alt}\nTITLE: {title}", language=None)
                processed_count += 1
            else:
                # Fehlermeldung wurde schon in generate_image_tags via st.error/st.warning ausgegeben
                st.error(f"Fehler bei der Tag-Generierung für '{file_name}'. Details siehe oben.")
                failed_count += 1

        # Finale Zusammenfassung
        st.divider()
        st.subheader("🏁 Zusammenfassung")
        col1, col2 = st.columns(2)
        col1.metric("Erfolgreich verarbeitet", processed_count)
        col2.metric("Fehlgeschlagen", failed_count, delta=None if failed_count == 0 else -failed_count, delta_color="inverse")
        st.info("Verarbeitung abgeschlossen.")

else:
    st.info("Bitte lade Bilder über den Uploader oben hoch.")

# Optional: Link zur Doku oder Hinweise
st.sidebar.title("ℹ️ Info")
st.sidebar.write("Diese App nutzt die Google Gemini API zur Generierung von Bild-Tags.")
# (Kein Reset-Button mehr nötig, da keine Dateien verschoben werden)