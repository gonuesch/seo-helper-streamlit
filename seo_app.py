# -*- coding: utf-8 -*-

import os
import streamlit as st # Streamlit importieren
import google.generativeai as genai
from PIL import Image
from pathlib import Path
from dotenv import load_dotenv
import time

# --- Grundkonfiguration & API Key ---

# Lade Umgebungsvariablen (API Key) aus .env Datei
load_dotenv()
api_key = os.getenv("GOOGLE_API_KEY")

# Streamlit Seiten-Konfiguration (optional, aber nett)
st.set_page_config(page_title="SEO Bild-Tag Generator", layout="wide")

st.title("🤖 SEO Bild-Tag Generator")
st.write("""
    Dieses Tool analysiert Bilder in einem festgelegten Ordner mithilfe der Gemini API,
    generiert SEO-optimierte 'alt'- und 'title'-Attribute und verschiebt
    die verarbeiteten Bilder anschließend in einen anderen Ordner.
    **Wichtig:** Benötigt eine `.env`-Datei mit einem gültigen `GOOGLE_API_KEY` im selben Verzeichnis.
""")

# Prüfe API Key und konfiguriere Gemini (oder zeige Fehler in Streamlit)
if not api_key:
    st.error("🚨 Fehler: GOOGLE_API_KEY nicht in der .env Datei gefunden. Bitte die .env Datei erstellen und den Key eintragen.")
    st.stop() # Hält die Ausführung der App an
else:
    try:
        genai.configure(api_key=api_key)
        # st.success("Google API Key geladen und Gemini konfiguriert.") # Optionales Feedback
    except Exception as e:
        st.error(f"🚨 Fehler bei der Konfiguration von Gemini: {e}")
        st.stop()

# --- Kernfunktion: Tag-Generierung (fast unverändert) ---

# (Wir belassen die Funktion hier, könnten sie aber auch in eine separate utils.py auslagern)
def generate_image_tags(image_path: str, model_name: str = "gemini-1.5-pro-latest") -> tuple[str | None, str | None]:
    """
    Nimmt einen Bildpfad, sendet das Bild an Gemini und gibt
    SEO-optimierte title- und alt-Tags zurück. (Minimale print Anpassungen für Streamlit)
    """
    image_path_obj = Path(image_path)
    if not image_path_obj.is_file():
        # Fehler wird im Hauptteil behandelt, hier nur return
        return None, None

    try:
        img = Image.open(image_path_obj)
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

        # Längere Pause wegen Free Tier Rate Limit (nach dem API Call)
        # st.write(f"    (Warte ~32s...)") # Info in Streamlit UI während der Pause
        time.sleep(32)

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
            # Fehlerdetails für die Hauptschleife bereitstellen (oder hier loggen)
            # print(f"  Fehler: Konnte Tags nicht aus Gemini-Antwort extrahieren für {Path(image_path).name}.") # Debug Print
            # print(f"  Rohe Antwort: {generated_text}") # Debug Print
            return None, None # Fehler wird im Hauptteil angezeigt

    except Exception as e:
        st.warning(f"⚠️ Fehler während Gemini-API Call für {image_path_obj.name}: {e}") # Warnung in Streamlit
        try:
            if response:
               st.warning(f"Prompt Feedback: {response.prompt_feedback}")
        except Exception:
            pass
        return None, None

# --- Streamlit UI & Verarbeitungslogik ---

st.divider() # Visuelle Trennlinie

# Definiere die Verzeichnisse relativ zum Skriptpfad
# __file__ zeigt auf die aktuelle Datei (seo_app.py)
script_dir = Path(__file__).parent
input_folder_name = "pics_to_process"
output_folder_name = "pics_done"
input_dir = script_dir / input_folder_name
output_dir = script_dir / output_folder_name

st.subheader("Verzeichnisse")
st.info(f"**Input-Ordner:** `{input_dir}`\n\n**Output-Ordner:** `{output_dir}`")
st.caption(f"Das Skript erwartet die Ordner '{input_folder_name}' und '{output_folder_name}' im selben Verzeichnis wie die App selbst ({script_dir}). Der Output-Ordner wird bei Bedarf erstellt.")

st.divider()

# Button zum Starten der Verarbeitung
if st.button("🚀 Verarbeitung starten", type="primary"):

    st.info("Starte Verarbeitung...")

    # 1. Stelle sicher, dass Output-Verzeichnis existiert
    with st.spinner("Prüfe/Erstelle Output-Verzeichnis..."):
        try:
            output_dir.mkdir(parents=True, exist_ok=True)
            st.success(f"Output-Verzeichnis '{output_dir.name}' bereit.")
        except Exception as e:
            st.error(f"Konnte Output-Verzeichnis nicht erstellen: {e}")
            st.stop() # Anhalten, wenn das nicht klappt

    # 2. Finde Bilddateien
    with st.spinner(f"Suche nach Bildern in '{input_dir.name}'..."):
        image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp']
        try:
            image_files_to_process = [
                item for item in input_dir.iterdir()
                if item.is_file() and item.suffix.lower() in image_extensions
            ]
            if not image_files_to_process:
                st.warning("Keine passenden Bilddateien im Input-Verzeichnis gefunden.")
                st.stop() # Anhalten, wenn keine Bilder da sind
            else:
                st.success(f"{len(image_files_to_process)} Bilddatei(en) gefunden.")
        except FileNotFoundError:
            st.error(f"Input-Verzeichnis '{input_dir}' nicht gefunden!")
            st.stop()
        except Exception as e:
            st.error(f"Fehler beim Lesen des Input-Verzeichnisses: {e}")
            st.stop()


    # 3. Verarbeite jede Datei
    st.subheader("Verarbeitungsfortschritt")
    processed_count = 0
    failed_count = 0
    results_placeholder = st.empty() # Platzhalter für dynamische Updates
    current_results_text = ""

    for image_file_path in image_files_to_process:
        file_name = image_file_path.name
        current_results_text += f"\n\n**Verarbeite:** `{file_name}`"
        results_placeholder.info(current_results_text) # Update Platzhalter

        try:
            # Zeige Spinner während der Tag-Generierung (inkl. Wartezeit)
            with st.spinner(f"Generiere Tags für {file_name}... (inkl. Wartezeit ~32s)"):
                title, alt = generate_image_tags(str(image_file_path))

            # Prüfe Ergebnis und handle Verschiebung
            if title and alt:
                current_results_text += f"\n  ✅ **Erfolg!**\n  *ALT:* {alt}\n  *TITLE:* {title}"
                results_placeholder.info(current_results_text) # Update Platzhalter

                # Verschiebe die Datei
                destination_path = output_dir / file_name
                try:
                    image_file_path.rename(destination_path)
                    current_results_text += f"\n  -> Verschoben nach '{output_folder_name}'."
                    results_placeholder.info(current_results_text) # Update Platzhalter
                    processed_count += 1
                except OSError as move_error:
                    current_results_text += f"\n  ❌ **Fehler beim Verschieben:** {move_error}"
                    results_placeholder.warning(current_results_text) # Update Platzhalter mit Warnung
                    failed_count += 1 # Zählen als Fehler, da nicht verschoben

            else:
                current_results_text += f"\n  ❌ **Fehler:** Konnte keine Tags generieren. Nicht verschoben."
                results_placeholder.error(current_results_text) # Update Platzhalter mit Fehler
                failed_count += 1

        except Exception as e:
            current_results_text += f"\n  ❌ **Unerwarteter Fehler** bei Verarbeitung von '{file_name}': {e}"
            results_placeholder.error(current_results_text) # Update Platzhalter mit Fehler
            failed_count += 1

    # 4. Finale Zusammenfassung
    st.subheader("🏁 Zusammenfassung")
    col1, col2 = st.columns(2)
    col1.metric("Erfolgreich verarbeitet & verschoben", processed_count)
    col2.metric("Fehlgeschlagen / Nicht verschoben", failed_count, delta=None if failed_count == 0 else -failed_count, delta_color="inverse")

    st.info("Verarbeitung abgeschlossen.")

else:
    st.info("Klicke auf 'Verarbeitung starten', um die Bilder im Input-Ordner zu analysieren.")


# Hinweis zum Zurücksetzen
st.sidebar.title("🧪 Testen")
st.sidebar.write("Um die Verarbeitung erneut zu testen, musst du die Bilder manuell (oder mit dem separaten Hilfsskript) vom Ordner `pics_done` zurück in den Ordner `pics_to_process` verschieben.")