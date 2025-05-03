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

# NEU: Import für den Copy-Button
from streamlit_copy_button import copy_button

# --- Grundkonfiguration & API Key ---

st.set_page_config(page_title="SEO Bild-Tag Generator", layout="wide")

st.title("🤖 SEO Bild-Tag Generator (Cloud Version)")
st.write("""
    Lade ein oder mehrere Bilder hoch. Diese App analysiert sie mithilfe der Gemini API
    und generiert SEO-optimierte 'alt'- und 'title'-Attribute.
""")

# API Key aus Streamlit Secrets
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

# --- Kernfunktion: Tag-Generierung (unverändert zur letzten Version) ---

@st.cache_data # Cache hinzufügen, um API-Aufrufe für gleiche Bilder zu sparen
def generate_image_tags_cached(image_bytes, file_name_for_log: str, model_name: str = "gemini-1.5-pro-latest") -> tuple[Union[str, None], Union[str, None]]:
    """
    Nimmt Bild-Bytes, sendet sie an Gemini und gibt SEO-optimierte Tags zurück.
    Gecacht von Streamlit. ACHTUNG: Rate Limiting muss VOR dem Aufruf erfolgen.
    """
    try:
        # Erstelle PIL Image aus Bytes
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

        # API Call mit Timeout
        response = model.generate_content([prompt, img], request_options={"timeout": 120})

        # KEIN time.sleep() HIER wegen @st.cache_data.
        # Rate-Limiting muss *vor* dem Funktionsaufruf erfolgen.

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
            # Gib None zurück, Fehlerbehandlung im Hauptteil
            # Loggen der Rohen Antwort kann hier sinnvoll sein (nicht mit st.write)
            # print(f"Raw response issue for {file_name_for_log}: {generated_text}")
            return None, None

    except Exception as e:
        # Loggen des Fehlers hier sinnvoll (nicht mit st.write)
        # print(f"Error processing/analyzing {file_name_for_log}: {e}")
        # Versuche, Prompt Feedback zu loggen, falls response existiert
        try:
             if response and hasattr(response, 'prompt_feedback'):
                 # print(f"Prompt Feedback: {response.prompt_feedback}")
                 pass
        except Exception:
            pass
        return None, None


# --- Streamlit UI & Verarbeitungslogik ---

st.divider()

uploaded_files = st.file_uploader(
    "Lade ein oder mehrere Bilder hoch...",
    accept_multiple_files=True,
    type=['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp']
)

st.divider()

if uploaded_files:
    st.info(f"{len(uploaded_files)} Bild(er) zum Hochladen ausgewählt.")

    if st.button("🚀 Ausgewählte Bilder verarbeiten", type="primary"):

        st.subheader("Verarbeitungsergebnisse")
        processed_count = 0
        failed_count = 0

        # Platzhalter für Fortschritt/Status (optional, aber nett)
        status_placeholder = st.empty()

        for i, uploaded_file in enumerate(uploaded_files):
            file_name = uploaded_file.name
            status_placeholder.info(f"Verarbeite Bild {i+1}/{len(uploaded_files)}: {file_name}...")

            try:
                # Lese Bytes für Caching und Verarbeitung
                image_bytes = uploaded_file.getvalue()

                # Wende Rate-Limiting an (vor dem Cache-Check/API-Call)
                # Beachte: Dies verlangsamt auch, wenn das Ergebnis gecached ist.
                # Eine bessere Implementierung würde das Caching prüfen, bevor sie schläft.
                # Aber für Einfachheit belassen wir es erstmal so.
                with st.spinner(f"Warte wegen Rate Limit (~32s) für {file_name}..."):
                    time.sleep(32)

                # Rufe die (potenziell gecachte) Funktion auf
                title, alt = generate_image_tags_cached(image_bytes, file_name)

                # === NEU: Ergebnisdarstellung mit Thumbnail und Copy-Buttons ===
                if title and alt:
                    with st.expander(f"✅ Ergebnisse für: {file_name}", expanded=True):
                        col1, col2 = st.columns([1, 3], gap="medium") # Verhältnis und Abstand anpassen
                        with col1:
                            st.image(image_bytes, width=150, caption="Vorschau") # Zeige hochgeladenes Bild
                        with col2:
                            st.text("ALT Tag:")
                            # Zeige den Tag-Text an
                            st.text_area("ALT", value=alt, height=75, key=f"alt_text_{file_name}", disabled=True, label_visibility="collapsed")
                            # Füge Copy-Button hinzu, der nur den 'alt'-Wert kopiert
                            copy_button(text_to_copy=alt, button_text="ALT kopieren", key=f"alt_copy_{file_name}")

                            st.write("") # Kleiner Abstand

                            st.text("TITLE Tag:")
                            # Zeige den Tag-Text an
                            st.text_area("TITLE", value=title, height=75, key=f"title_text_{file_name}", disabled=True, label_visibility="collapsed")
                             # Füge Copy-Button hinzu, der nur den 'title'-Wert kopiert
                            copy_button(text_to_copy=title, button_text="TITLE kopieren", key=f"title_copy_{file_name}")
                    processed_count += 1
                else:
                    # Zeige nur den Expander-Titel als Fehler an
                    st.error(f"❌ Fehler bei der Tag-Generierung für '{file_name}'. Keine Tags erhalten.")
                    failed_count += 1
                # === Ende Ergebnisdarstellung ===

            except Exception as e:
               st.error(f"🚨 Unerwarteter FEHLER bei Verarbeitung von '{file_name}': {e}")
               failed_count += 1

        # Leere den Status-Platzhalter am Ende
        status_placeholder.empty()

        # Finale Zusammenfassung
        st.divider()
        st.subheader("🏁 Zusammenfassung")
        col1, col2 = st.columns(2)
        col1.metric("Erfolgreich verarbeitet", processed_count)
        col2.metric("Fehlgeschlagen", failed_count, delta=None if failed_count == 0 else -failed_count, delta_color="inverse")
        st.success("Verarbeitung abgeschlossen.") # Geändert zu success für positiveren Abschluss

else:
    st.info("Bitte lade Bilder über den Uploader oben hoch.")


st.sidebar.title("ℹ️ Info")
st.sidebar.write("Diese App nutzt die Google Gemini API zur Generierung von Bild-Tags.")