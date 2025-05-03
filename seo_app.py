# -*- coding: utf-8 -*-

import os
import streamlit as st
import google.generativeai as genai
from PIL import Image
# from pathlib import Path # Nicht mehr direkt benötigt für Ordner
import time
from io import BytesIO # Für die Verarbeitung von Upload-Bytes
from typing import Union

# Import für die alternative Clipboard-Komponente
from streamlit_clipboard import st_clipboard

# --- Grundkonfiguration & API Key ---

# Streamlit Seiten-Konfiguration
st.set_page_config(page_title="SEO Bild-Tag Generator", layout="wide")

st.title("🤖 SEO Bild-Tag Generator (Cloud Version)")
st.write("""
    Lade ein oder mehrere Bilder hoch. Diese App analysiert sie mithilfe der Gemini API
    und generiert SEO-optimierte 'alt'- und 'title'-Attribute.
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

@st.cache_data # Cachet das Ergebnis basierend auf den Input-Argumenten
def generate_image_tags_cached(image_bytes, file_name_for_log: str, model_name: str = "gemini-1.5-pro-latest") -> tuple[Union[str, None], Union[str, None]]:
    """
    Nimmt Bild-Bytes, sendet sie an Gemini und gibt SEO-optimierte Tags zurück.
    Gecacht von Streamlit. ACHTUNG: Rate Limiting muss VOR dem Aufruf erfolgen.
    """
    try:
        # Erstelle PIL Image aus Bytes für die API
        img = Image.open(BytesIO(image_bytes))

        # Initialisiere das Gemini Modell
        model = genai.GenerativeModel(model_name)

        # Definiere den Prompt für die API
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

        # Führe den API Call aus
        # Kein try-except hier, wird außerhalb für Rate Limiting gefangen
        response = model.generate_content([prompt, img], request_options={"timeout": 120})

        # KEIN time.sleep() HIER IM GEC तनCHTEN TEIL! Muss außen erfolgen.

        # Extrahiere Text und parse Tags
        generated_text = response.text.strip()
        alt_tag = None
        title_tag = None
        lines = generated_text.split('\n')
        for line in lines:
            # Suche nach den Zeilen, ignoriere Groß-/Kleinschreibung und Leerzeichen
            if line.strip().upper().startswith("ALT:"):
                alt_tag = line.strip()[len("ALT:"):].strip()
            elif line.strip().upper().startswith("TITLE:"):
                title_tag = line.strip()[len("TITLE:"):].strip()

        # Gib Ergebnis zurück (oder None bei Fehlern)
        if alt_tag and title_tag:
            return title_tag, alt_tag
        else:
            # Logge das Problem, falls Tags nicht extrahiert werden konnten
            print(f"Warning: Could not extract tags for {file_name_for_log}. Raw response: {generated_text}") # Log geht in Streamlit Cloud Logs
            return None, None

    except Exception as e:
        # Logge unerwartete Fehler während der API-Verarbeitung
        print(f"Error during Gemini processing for {file_name_for_log}: {e}") # Log geht in Streamlit Cloud Logs
        # Versuche, Prompt Feedback zu loggen, falls response existiert
        try:
             if response and hasattr(response, 'prompt_feedback'):
                 print(f"Prompt Feedback: {response.prompt_feedback}") # Log
        except Exception:
            pass
        return None, None


# --- Streamlit UI & Verarbeitungslogik ---

st.divider() # Visuelle Trennlinie

# File Uploader für mehrere Bilder
uploaded_files = st.file_uploader(
    "Lade ein oder mehrere Bilder hoch...",
    accept_multiple_files=True,
    type=['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp'], # Erlaubte Dateitypen
    key="file_uploader" # Eindeutiger Key
)

st.divider()

# Verarbeitung starten, wenn Dateien hochgeladen wurden
if uploaded_files:
    st.info(f"{len(uploaded_files)} Bild(er) zum Hochladen ausgewählt.")

    # Button zum Starten der Verarbeitung
    if st.button("🚀 Ausgewählte Bilder verarbeiten", type="primary", key="process_button"):

        st.subheader("Verarbeitungsergebnisse")
        processed_count = 0
        failed_count = 0

        # Platzhalter für den aktuellen Verarbeitungsstatus
        status_placeholder = st.empty()

        # Iteriere durch jede hochgeladene Datei
        for i, uploaded_file in enumerate(uploaded_files):
            file_name = uploaded_file.name
            status_placeholder.info(f"Verarbeite Bild {i+1}/{len(uploaded_files)}: {file_name}...")

            try:
                # Lese Bild-Bytes (wird für Caching benötigt)
                image_bytes = uploaded_file.getvalue()

                # Wende Rate-Limiting an (vor dem Cache-Check/API-Call)
                # Muss außerhalb der gecachten Funktion sein.
                # TODO: Optimalerweise nur warten, wenn NICHT im Cache.
                with st.spinner(f"Warte wegen Rate Limit (~32s) für {file_name}..."):
                    time.sleep(32)

                # Rufe die (potenziell gecachte) Funktion zur Tag-Generierung auf
                title, alt = generate_image_tags_cached(image_bytes, file_name)

                # Zeige Ergebnis im Expander an, wenn erfolgreich
                if title and alt:
                    with st.expander(f"✅ Ergebnisse für: {file_name}", expanded=True):
                        # Teile Bereich auf für Bild und Text/Buttons
                        col1, col2 = st.columns([1, 3], gap="medium")
                        with col1:
                            # Zeige Thumbnail an
                            st.image(image_bytes, width=150, caption="Vorschau")
                        with col2:
                            # ALT Tag Anzeige + Copy Button
                            st.text("ALT Tag:")
                            st.text_area("ALT", value=alt, height=75, key=f"alt_text_{file_name}", disabled=True, label_visibility="collapsed")
                            st_clipboard(text=alt, label="ALT kopieren", key=f"alt_copy_{file_name}")

                            st.write("") # Kleiner Abstand

                            # TITLE Tag Anzeige + Copy Button
                            st.text("TITLE Tag:")
                            st.text_area("TITLE", value=title, height=75, key=f"title_text_{file_name}", disabled=True, label_visibility="collapsed")
                            st_clipboard(text=title, label="TITLE kopieren", key=f"title_copy_{file_name}")
                    processed_count += 1
                else:
                    # Zeige Fehler im Expander-Titel, wenn keine Tags zurückkamen
                    st.error(f"❌ Fehler bei der Tag-Generierung für '{file_name}'. Keine Tags erhalten.")
                    failed_count += 1

            except Exception as e:
               # Fange unerwartete Fehler während der Schleife ab
               st.error(f"🚨 Unerwarteter FEHLER bei der Verarbeitung von '{file_name}': {e}")
               failed_count += 1

        # Leere den Status-Text am Ende
        status_placeholder.empty()

        # Finale Zusammenfassung
        st.divider()
        st.subheader("🏁 Zusammenfassung")
        col1, col2 = st.columns(2)
        col1.metric("Erfolgreich verarbeitet", processed_count)
        col2.metric("Fehlgeschlagen", failed_count, delta=None if failed_count == 0 else -failed_count, delta_color="inverse")
        st.success("Verarbeitung abgeschlossen.") # Positiver Abschluss

else:
    # Hinweis, wenn keine Dateien hochgeladen sind
    st.info("Bitte lade Bilder über den Uploader oben hoch.")


# Informationen in der Seitenleiste
st.sidebar.title("ℹ️ Info")
st.sidebar.write("Diese App nutzt die Google Gemini API zur Generierung von Bild-Tags.")
st.sidebar.caption("Entwickelt als Beispiel.")