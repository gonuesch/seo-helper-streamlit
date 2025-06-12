# -*- coding: utf-8 -*-

import os
import streamlit as st
import google.generativeai as genai
from PIL import Image
import time
from io import BytesIO
from typing import Union, Tuple
import json
import streamlit.components.v1 as components
from google.api_core.exceptions import ResourceExhausted
from pathlib import Path
import pandas as pd

# --- Grundkonfiguration & API Key ---
st.set_page_config(page_title="Bildbeschreibungs-Generator", layout="wide")
st.title("🤖 Bildbeschreibungs-Generator (Cloud Version)")
st.write("""
    Lade ein oder mehrere Bilder hoch. Diese App analysiert sie mithilfe der Gemini API
    und generiert entweder SEO-optimierte 'alt'- und 'title'-Attribute oder
    eine detaillierte barrierefreie Bildbeschreibung (Kurz- & Langversion).
""")

api_key = st.secrets.get("GOOGLE_API_KEY")
if not api_key: st.error("🚨 Fehler: GOOGLE_API_KEY nicht konfiguriert!"); st.stop()
try: genai.configure(api_key=api_key)
except Exception as e: st.error(f"🚨 Fehler bei Konfiguration: {e}"); st.stop()

# --- Prompts für die verschiedenen Modi ---
ACCESSIBILITY_PROMPT_TEMPLATE = """Du bist eine KI, spezialisiert auf die Erstellung barrierefreier Bildbeschreibungen (Alternativtexte und gegebenenfalls erweiterte Beschreibungen) für E-Books. Deine Aufgabe ist es, Bilder für blinde und sehbehinderte Leser zugänglich zu machen, gemäß den WCAG-Richtlinien und den spezifischen Vorgaben unseres Verlags, wie sie dir hier dargelegt werden.
WICHTIGE ANWEISUNG FÜR DEINE ANTWORT: Deine Antwort muss ausschließlich die generierte Bildbeschreibung enthalten. Formuliere keine Einleitungssätze, keine abschließenden Bemerkungen, keine Höflichkeitsfloskeln oder sonstige Erklärungen zu deiner Vorgehensweise – nur der reine Text im vorgegebenen Format.
Buchkontext: $BUCHKONTEXT
Erstelle nun eine Bildbeschreibung unter strikter Beachtung folgender Richtlinien aus unserem Verlagshandout:
Zweck und Zielgruppe:
- Vermittle blinden oder sehbehinderten Menschen präzise, was auf dem Bild zu sehen ist und welche Inhalte es transportiert. Ermögliche einen barrierefreien Zugang.
- Die Beschreibung soll die Funktion des Bildes im jeweiligen $BUCHKONTEXT klarstellen.
Stil und Formulierung:
- Neutral und deskriptiv: Beschreibe objektiv, was visuell wahrnehmbar ist.
- Keine Interpretation: Vermeide persönliche Deutungen oder Wertungen.
- Direkter Einstieg: Verzichte zwingend auf einleitende Formulierungen wie „Das Foto zeigt…“ oder „Auf dem Bild ist zu sehen…“.
- Anführungszeichen: Verwende für Anführungszeichen ausschließlich französische Guillemets («Beispiel»).
- Sprache: Klar, präzise und allgemein verständlich.
Inhalt und Struktur:
- Vom Allgemeinen zum Speziellen: Beginne mit einer allgemeinen Erfassung und gehe dann auf Details ein.
- Wesentliche Elemente: Identifiziere und beschreibe alle relevanten Elemente.
- Bildtyp berücksichtigen: Gib ggf. den Bildtyp an.
- Bei Karten, Tabellen und Diagrammen: Erkläre die dargestellten Daten und deren Beziehungen.
- Relevanz und Redundanzvermeidung: Konzentriere dich auf die Informationen, die für das Verständnis im $BUCHKONTEXT notwendig sind.
Länge:
- So knapp wie möglich, aber so ausführlich wie nötig. Für einfache Bilder kann eine kurze Beschreibung (ca. 140 Zeichen) genügen. Komplexere Bilder erfordern eine ausführlichere Beschreibung.
Atmosphäre/Stimmung (falls relevant): Beschreibe diese kurz, wenn sie für das Verständnis wichtig ist.

FINALES AUSGABEFORMAT:
Basierend auf allen oben genannten Richtlinien, generiere jetzt bitte ZWEI Beschreibungen für das bereitgestellte Bild in genau dem folgenden Format, ohne zusätzliche Einleitungen oder Kommentare:

KURZBESCHREIBUNG (max. 140 Zeichen): [Hier die prägnante, eigenständige Kurzbeschreibung einfügen, die die 140-Zeichen-Grenze strikt einhält.]
---
LANGBESCHREIBUNG: [Hier die detaillierte, erweiterte Beschreibung ohne Längenbeschränkung einfügen.]
"""

SEO_PROMPT = """Analysiere das folgende Bild sorgfältig.
Deine Aufgabe ist es, SEO-optimierte HTML-Attribute für dieses Bild zu generieren:
1. Ein 'alt'-Attribut (Alternativtext)
2. Ein 'title'-Attribut
Beachte dabei die aktuellen SEO Best Practices:
- Das 'alt'-Attribut muss das Bild präzise und prägnant beschreiben. Es ist entscheidend für Barrierefreiheit und das Verständnis des Bildinhalts durch Suchmaschinen. Beschreibe Objekte, Personen, Aktionen und ggf. Text im Bild. Vermeide Keyword-Stuffing.
- Das 'title'-Attribut kann zusätzliche kontextbezogene Informationen liefern.
Gib *nur* die beiden Attribute im folgenden Format zurück, ohne zusätzliche Erklärungen oder Formatierungen:
ALT: [Hier der generierte Alt-Text]
TITLE: [Hier der generierte Title-Text]
"""

# --- Kernfunktionen für Tag-Generierung ---

@st.cache_data
def generate_seo_tags_cached(image_bytes_for_api, file_name_for_log: str, model_name: str = "gemini-1.5-pro-latest") -> Tuple[Union[str, None], Union[str, None]]:
    try:
        img = Image.open(BytesIO(image_bytes_for_api))
        model = genai.GenerativeModel(model_name)
        try: response = model.generate_content([SEO_PROMPT, img], request_options={"timeout": 120})
        except ResourceExhausted as e: print(f"Rate limit exceeded for SEO tags {file_name_for_log}: {e}"); return None, None
        generated_text = response.text.strip()
        alt_tag, title_tag = None, None
        for line in generated_text.split('\n'):
            if line.strip().upper().startswith("ALT:"): alt_tag = line.strip()[len("ALT:"):].strip()
            elif line.strip().upper().startswith("TITLE:"): title_tag = line.strip()[len("TITLE:"):].strip()
        if alt_tag and title_tag: return title_tag, alt_tag
        else: print(f"Warning: Could not extract SEO tags for {file_name_for_log}. Raw: {generated_text}"); return None, None
    except Exception as e: print(f"Error during SEO tag generation for {file_name_for_log}: {e}"); return None, None

@st.cache_data
def generate_accessibility_description_cached(image_bytes_for_api, file_name_for_log: str, ebook_context: str = "", model_name: str = "gemini-2.5-flash-preview-05-20") -> Tuple[Union[str, None], Union[str, None]]:
    try:
        img = Image.open(BytesIO(image_bytes_for_api))
        model = genai.GenerativeModel(model_name)
        context_for_prompt = ebook_context if ebook_context and ebook_context.strip() else "Es wurde kein spezifischer Buchkontext bereitgestellt."
        final_prompt = ACCESSIBILITY_PROMPT_TEMPLATE.replace("$BUCHKONTEXT", context_for_prompt)
        try: response = model.generate_content([final_prompt, img], request_options={"timeout": 180})
        except ResourceExhausted as e: print(f"Rate limit exceeded for accessibility desc {file_name_for_log}: {e}"); return None, None
        generated_text = response.text.strip(); short_desc, long_desc = None, None
        try:
            parts = generated_text.split('---', 1)
            if parts[0]:
                short_desc_raw = parts[0].split(":", 1);
                if len(short_desc_raw) > 1: short_desc = short_desc_raw[1].strip()
            if len(parts) > 1 and parts[1]:
                long_desc_raw = parts[1].split(":", 1)
                if len(long_desc_raw) > 1: long_desc = long_desc_raw[1].strip()
        except Exception as e: print(f"Error parsing short/long desc for {file_name_for_log}: {e}. Raw: {generated_text}"); return None, None
        return short_desc, long_desc
    except Exception as e: print(f"Error during accessibility desc generation for {file_name_for_log}: {e}"); return None, None

# --- Streamlit UI & Verarbeitungslogik ---

st.sidebar.title("⚙️ Modusauswahl")
generation_mode = st.sidebar.radio("Welche Art von Text soll generiert werden?", ("SEO Tags (alt & title)", "Barrierefreie Bildbeschreibung"), key="generation_mode")
st.sidebar.divider()
ebook_context_input = ""
if generation_mode == "Barrierefreie Bildbeschreibung":
    ebook_context_input = st.sidebar.text_area("Optional: Kontext des E-Books (max. 500 Zeichen)", height=150, key="ebook_context", max_chars=500, placeholder="z.B. Titel, Kapitel, Thema des Abschnitts...", help="Erkläre kurz, welche Funktion das Bild im spezifischen Kontext des E-Book-Kapitels hat.")
    st.sidebar.caption(f"{len(ebook_context_input)}/500 Zeichen")

st.divider()
uploaded_files = st.file_uploader("Lade ein oder mehrere Bilder hoch...", accept_multiple_files=True, type=['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'tif', 'tiff'], key="file_uploader")
st.divider()

if uploaded_files:
    if st.button("🚀 Ausgewählte Bilder verarbeiten", type="primary", key="process_button"):
        st.subheader("Verarbeitungsergebnisse")
        processed_count, failed_count = 0, 0
        status_placeholder = st.empty()
        results_for_export = []

        for i, uploaded_file in enumerate(uploaded_files):
            file_name = uploaded_file.name; safe_file_name_part = "".join(c if c.isalnum() else "_" for c in file_name); base_id = f"file_{i}_{safe_file_name_part}"
            status_placeholder.info(f"Verarbeite Bild {i+1}/{len(uploaded_files)}: {file_name}...")
            try:
                original_image_bytes = uploaded_file.getvalue(); image_bytes_for_api = original_image_bytes
                if Path(file_name).suffix.lower() in ['.tif', '.tiff']:
                    try:
                        with st.spinner(f"Konvertiere {file_name} (TIFF) zu PNG..."):
                            pil_image = Image.open(BytesIO(original_image_bytes))
                            if getattr(pil_image, "n_frames", 1) > 1: pil_image.seek(0)
                            if pil_image.mode not in ('RGB', 'RGBA', 'L'): pil_image = pil_image.convert('RGB')
                            output_buffer = BytesIO(); pil_image.save(output_buffer, format="PNG"); image_bytes_for_api = output_buffer.getvalue()
                    except Exception as conv_e: st.error(f"🚨 Fehler beim Konvertieren der TIFF-Datei '{file_name}': {conv_e}"); failed_count += 1; continue
                
                if generation_mode == "SEO Tags (alt & title)":
                    with st.spinner(f"Generiere SEO Tags für {file_name}..."):
                        title, alt = generate_seo_tags_cached(image_bytes_for_api, file_name)
                    if title and alt:
                        with st.expander(f"✅ SEO Tags für: {file_name}", expanded=True):
                            alt_button_id, title_button_id = f"alt_btn_{base_id}", f"title_btn_{base_id}"
                            col1, col2 = st.columns([1, 3], gap="medium");
                            with col1: st.image(original_image_bytes, width=150, caption="Vorschau")
                            with col2:
                                st.text("ALT Tag:"); st.text_area("ALT", value=alt, height=75, key=f"alt_text_{base_id}", disabled=True, label_visibility="collapsed")
                                alt_json = json.dumps(alt); components.html(f"""<button id="{alt_button_id}">ALT kopieren</button><script>document.getElementById("{alt_button_id}").addEventListener('click', function(){{navigator.clipboard.writeText({alt_json}).then(function(){{let b=document.getElementById("{alt_button_id}");let o=b.innerText;b.innerText='Kopiert!';setTimeout(function(){{b.innerText=o}},1500)}})}});</script><style>#{alt_button_id}{{background-color:#007bff;color:white;border:none;padding:5px 10px;border-radius:5px;cursor:pointer;margin-top:5px}}#{alt_button_id}:hover{{background-color:#0056b3}}</style>""",height=45)
                                st.write(""); st.text("TITLE Tag:")
                                st.text_area("TITLE", value=title, height=75, key=f"title_text_{base_id}", disabled=True, label_visibility="collapsed")
                                title_json = json.dumps(title); components.html(f"""<button id="{title_button_id}">TITLE kopieren</button><script>document.getElementById("{title_button_id}").addEventListener('click', function(){{navigator.clipboard.writeText({title_json}).then(function(){{let b=document.getElementById("{title_button_id}");let o=b.innerText;b.innerText='Kopiert!';setTimeout(function(){{b.innerText=o}},1500)}})}});</script><style>#{title_button_id}{{background-color:#007bff;color:white;border:none;padding:5px 10px;border-radius:5px;cursor:pointer;margin-top:5px}}#{title_button_id}:hover{{background-color:#0056b3}}</style>""",height=45)
                        processed_count += 1
                    else: st.error(f"❌ Fehler bei SEO Tag-Generierung für '{file_name}'."); failed_count += 1

                elif generation_mode == "Barrierefreie Bildbeschreibung":
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
                        results_for_export.append({"Bildname": file_name, "Dateiname Produktion": "", "Alternativtext": short_desc, "Bildlegende": "", "Anmerkung": "", "Langbeschreibung": long_desc, "(Platzierung/Größe/Übersetzungstexte in der Abbildung/...)": ""})
                    else: st.error(f"❌ Fehler bei Erstellung der barrierefreien Beschreibung für '{file_name}'."); failed_count += 1
            except Exception as e: st.error(f"🚨 Unerwarteter FEHLER bei der Hauptverarbeitung von '{file_name}': {e}"); failed_count += 1
        
        status_placeholder.empty()
        if results_for_export:
            st.divider(); st.subheader("📊 Ergebnisse exportieren")
            df = pd.DataFrame(results_for_export)
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer: df.to_excel(writer, index=False, sheet_name='Bildbeschreibungen')
            excel_data = output.getvalue()
            st.download_button(label="💾 Excel-Datei herunterladen", data=excel_data, file_name="barrierefreie_bildbeschreibungen.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        st.divider(); st.subheader("🏁 Zusammenfassung")
        col1, col2 = st.columns(2); col1.metric("Erfolgreich verarbeitet", processed_count); col2.metric("Fehlgeschlagen", failed_count, delta=None if failed_count == 0 else -failed_count, delta_color="inverse"); st.success("Verarbeitung abgeschlossen.")
else: st.info("Bitte lade Bilder über den Uploader oben hoch.")

st.sidebar.title("ℹ️ Info")
st.sidebar.write("Diese App nutzt die Google Gemini API zur Generierung von Bild-Tags.")
st.sidebar.text(f"Unterstützte Formate: {', '.join(['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'tif', 'tiff'])}")
st.sidebar.text("Bei Fragen -> Gordon")