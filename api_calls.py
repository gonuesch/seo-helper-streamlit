# seo-helper-streamlit/api_calls.py

import streamlit as st
from PIL import Image
from io import BytesIO
from typing import Union, Tuple, Dict 
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted
import logging
import re
import requests
import json
import uuid
import vertexai
from vertexai.generative_models import GenerativeModel, Part
from google.cloud import firestore
import os

# Importiere die Prompt-Vorlagen aus der prompts.py Datei
from prompts import ACCESSIBILITY_PROMPT_TEMPLATE, SEO_PROMPT, SUMMARY_PROMPT, GUIDELINE_PROMPT_WITH_MATCHING, SSML_PROMPT, TRANSLATION_GUIDE_PROMPT, TRANSLATE_CHUNK_PROMPT
from utils import log_exceptions

# Richte ein einfaches Logging ein, um Fehler besser nachverfolgen zu können
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Gemini-Modell für die neuen Funktionen
model_gemini = genai.GenerativeModel('gemini-2.5-flash')

# --- Die Funktionen generate_seo_tags_cached und generate_accessibility_description_cached bleiben unverändert ---


@log_exceptions
def generate_text_summary(_text: str, gemini_api_key: str = None) -> str:
    """Erstellt eine Zusammenfassung des übergebenen Textes."""
    try:
        if gemini_api_key:
            genai.configure(api_key=gemini_api_key)
        
        full_prompt = SUMMARY_PROMPT + "\n\n--- ZU ZUSAMMENFASSENDER TEXT ---\n" + _text
        response = model_gemini.generate_content(full_prompt)
        return response.text
    except Exception as e:
        logger.error(f"Fehler bei der Text-Zusammenfassung: {e}", exc_info=True)
        return f"Fehler bei der Zusammenfassung: {e}"


@log_exceptions
def get_voice_recommendations(_summary: str, _voices_info: str, gemini_api_key: str = None) -> Tuple[str, list]:
    """Erstellt eine Regieleitlinie und extrahiert die Top 3 Stimmen."""
    try:
        if gemini_api_key:
            genai.configure(api_key=gemini_api_key)
            
        # Stelle sicher, dass _voices_info nicht leer ist, bevor der Prompt erstellt wird
        if not _voices_info or not _voices_info.strip():
            return "Fehler: Keine verfügbaren Stimmen mit Beschreibungen gefunden, um eine Empfehlung abzugeben.", []

        full_prompt = GUIDELINE_PROMPT_WITH_MATCHING.format(
            summary=_summary, 
            voices_with_descriptions=_voices_info
        )
        response = model_gemini.generate_content(full_prompt)
        guideline_text = response.text
        
        # Extrahiere die Top 3 Stimmen mit Regex
        top_1 = re.search(r"TOP_STIMME_1:\s*(.*)", guideline_text)
        top_2 = re.search(r"TOP_STIMME_2:\s*(.*)", guideline_text)
        top_3 = re.search(r"TOP_STIMME_3:\s*(.*)", guideline_text)
        
        recommendations = []
        if top_1: recommendations.append(top_1.group(1).strip())
        if top_2: recommendations.append(top_2.group(1).strip())
        if top_3: recommendations.append(top_3.group(1).strip())
        
        # Fallback, falls die KI die Anweisungen nicht befolgt
        if not recommendations:
             return guideline_text, ["KI konnte keine Stimmen auswählen."]

        return guideline_text, recommendations
    except Exception as e:
        logger.error(f"Fehler bei der Regie-Erstellung: {e}", exc_info=True)
        return f"Fehler bei der Regie-Erstellung: {e}", []


@log_exceptions
def generate_ssml_chunk(_guideline: str, _text_chunk: str, gemini_api_key: str = None) -> str:
    """Reichert einen Text-Chunk mit SSML an."""
    try:
        if gemini_api_key:
            genai.configure(api_key=gemini_api_key)
            
        full_prompt = SSML_PROMPT.format(guideline=_guideline, text_chunk=_text_chunk)
        response = model_gemini.generate_content(full_prompt)
        # Bereinige die XML-Deklaration, falls vorhanden
        cleaned_ssml = re.sub(r'<\?xml.*?\?>\s*', '', response.text, flags=re.IGNORECASE)
        return cleaned_ssml
    except Exception as e:
        logger.error(f"Fehler bei der SSML-Anreicherung: {e}", exc_info=True)
        # Im Fehlerfall geben wir den Original-Chunk zurück
        return _text_chunk


@st.cache_data
@log_exceptions
def generate_seo_tags_cached(image_source: Union[bytes, str], file_name_for_log: str, gemini_api_key: str = None, model_name: str = "gemini-2.5-pro") -> Tuple[Union[str, None], Union[str, None]]:
    """
    Nimmt Bild-Bytes oder eine URL, ruft die Gemini API mit dem SEO-Prompt auf
    und gibt (title, alt) als Tupel zurück.
    """
    try:
        if gemini_api_key:
            genai.configure(api_key=gemini_api_key)
            
        image_bytes = None
        # Prüft, ob die Quelle eine URL (string) ist
        if isinstance(image_source, str): 
            headers = {
                'User-Agent': 'hbu-toolbox/1.0 (Toolbox für den Holtzbrinck Buchverlag)'
            }
            response = requests.get(image_source, headers=headers, timeout=30)
            # Löst einen Fehler aus, wenn der Download fehlschlägt (z.B. 404 Not Found, 403 Forbidden)
            response.raise_for_status() 
            image_bytes = response.content
        else: # Ansonsten sind es Bytes von einem Upload
            image_bytes = image_source
        
        # Stellt sicher, dass wir am Ende gültige Bild-Bytes haben
        if not image_bytes:
            raise ValueError("Keine validen Bilddaten für die Verarbeitung erhalten.")

        img = Image.open(BytesIO(image_bytes))
        model = genai.GenerativeModel(model_name)
        
        try:
            response = model.generate_content([SEO_PROMPT, img], request_options={"timeout": 120})
        except ResourceExhausted as e:
            logger.warning(f"Rate limit exceeded for SEO tags {file_name_for_log}: {e}")
            st.warning(f"Rate Limit für SEO-Tags bei '{file_name_for_log}' erreicht. Bitte versuche es später erneut oder mit weniger Bildern.")
            return None, None
        
        generated_text = response.text.strip()
        alt_tag, title_tag = None, None
        for line in generated_text.split('\n'):
            if line.strip().upper().startswith("ALT:"):
                alt_tag = line.strip()[len("ALT:"):].strip()
            elif line.strip().upper().startswith("TITLE:"):
                title_tag = line.strip()[len("TITLE:"):].strip()
        
        if alt_tag and title_tag:
            return title_tag, alt_tag
        else:
            logger.warning(f"Could not extract SEO tags for {file_name_for_log}. Raw response: {generated_text}")
            return None, None
            
    except requests.exceptions.RequestException as e:
        logger.error(f"Error downloading image from URL for {file_name_for_log}: {e}")
        st.error(f"Bild konnte von der URL nicht heruntergeladen werden: {e}")
        return None, None
    except Exception as e:
        logger.error(f"Error during SEO tag generation for {file_name_for_log}: {e}")
        st.error(f"Ein unerwarteter Fehler ist bei der Generierung der SEO-Tags für '{file_name_for_log}' aufgetreten.")
        return None, None

@st.cache_data
@log_exceptions
def generate_accessibility_description_cached(image_bytes_for_api, file_name_for_log: str, ebook_context: str = "", gemini_api_key: str = None, model_name: str = "gemini-2.5-pro") -> Tuple[Union[str, None], Union[str, None]]:
    """
    Nimmt Bild-Bytes und Kontext, ruft die Gemini API mit dem Barrierefreiheits-Prompt auf
    und gibt (kurzbeschreibung, langbeschreibung) als Tupel zurück.
    """
    try:
        if gemini_api_key:
            genai.configure(api_key=gemini_api_key)
            
        img = Image.open(BytesIO(image_bytes_for_api))
        model = genai.GenerativeModel(model_name)
        context_for_prompt = ebook_context if ebook_context and ebook_context.strip() else "Es wurde kein spezifischer Buchkontext für dieses Bild bereitgestellt."
        final_prompt = ACCESSIBILITY_PROMPT_TEMPLATE.replace("$BUCHKONTEXT", context_for_prompt)
        
        try:
            response = model.generate_content([final_prompt, img], request_options={"timeout": 180})
        except ResourceExhausted as e:
            logger.warning(f"Rate limit exceeded for accessibility description {file_name_for_log}: {e}")
            st.warning(f"Rate Limit für Barrierefreiheits-Beschreibung bei '{file_name_for_log}' erreicht. Bitte versuche es später erneut oder mit weniger Bildern.")
            return None, None
        
        generated_text = response.text.strip()
        short_desc, long_desc = None, None
        try:
            parts = generated_text.split('---', 1)
            if parts[0]:
                short_desc_raw = parts[0].split(":", 1)
                if len(short_desc_raw) > 1:
                    short_desc = short_desc_raw[1].strip()
            if len(parts) > 1 and parts[1]:
                long_desc_raw = parts[1].split(":", 1)
                if len(long_desc_raw) > 1:
                    long_desc = long_desc_raw[1].strip()
        except Exception as e:
            logger.error(f"Error parsing short/long description for {file_name_for_log}: {e}. Raw Text: {generated_text}", exc_info=True)
            return None, None
            
        return short_desc, long_desc
            
    except Exception as e:
        logger.error(f"Error during accessibility description generation for {file_name_for_log}: {e}", exc_info=True)
        st.error(f"Ein unerwarteter Fehler ist bei der Generierung der Barrierefreiheits-Beschreibung für '{file_name_for_log}' aufgetreten.")
        return None, None


@log_exceptions
def generate_translation_guide(manuscript_bytes: bytes, job_id: str, gemini_api_key: str = None) -> dict:
    try:
        vertexai.init(project="avid-infinity-458913-p3")
        model_for_caching = GenerativeModel("gemini-2.5-flash") # Optimized for translation speed and cost
        
        # Convert manuscript bytes to text first (DOCX/PDF -> text)
        try:
            # Try to read as DOCX first
            manuscript_text = read_text_from_docx(BytesIO(manuscript_bytes))
        except:
            try:
                # Try to read as PDF if DOCX fails
                manuscript_text = read_text_from_pdf(BytesIO(manuscript_bytes))
            except:
                # Fallback: try to decode as UTF-8 text
                manuscript_text = manuscript_bytes.decode('utf-8', errors='ignore')
        
        if not manuscript_text or manuscript_text.strip() == "":
            raise ValueError("Konnte keinen lesbaren Text aus dem Manuskript extrahieren")
        
        # Create cached content with TEXT (not binary DOCX)
        manuscript_part = Part.from_data(data=manuscript_text.encode('utf-8'), mime_type="text/plain")
        cache = vertexai.caching.CachedContent.create(
            model_name=model_for_caching.model_name, 
            system_instruction="Du bist ein Experte für Literaturanalyse.", 
            contents=[manuscript_part]
        )
        
        # Store cache name in Firestore
        firestore_client = firestore.Client(project="avid-infinity-458913-p3", database="hbu-toolbox-firestone")
        firestore_client.collection("translation_jobs").document(job_id).update({
            "cached_content_name": cache.name
        })
        
        # Use cached content for analysis
        model_with_cache = GenerativeModel.from_cached_content(cached_content=cache)
        full_prompt = TRANSLATION_GUIDE_PROMPT.format(full_text="[Manuskript ist im Cache verfügbar]")
        response = model_with_cache.generate_content(full_prompt)
        
        # Robust JSON parsing with markdown removal
        raw_response_text = response.text.strip()
        style_guide_json_str = ""
        
        try:
            # Attempt 1: Direct parse
            json.loads(raw_response_text)
            style_guide_json_str = raw_response_text
        except json.JSONDecodeError:
            # Attempt 2: Remove markdown formatting
            print("JSON-Parse fehlgeschlagen. Versuche, Markdown-Formatierung zu entfernen...")
            if raw_response_text.startswith("```json") and raw_response_text.endswith("```"):
                cleaned_text = raw_response_text[7:-3].strip()
                try:
                    json.loads(cleaned_text)
                    style_guide_json_str = cleaned_text
                except json.JSONDecodeError as e:
                    error_message = f"Konnte JSON auch nach Bereinigung nicht parsen: {e}. Original-Antwort: {raw_response_text}"
                    raise ValueError(error_message)
            else:
                error_message = f"Antwort ist kein valides JSON. Original-Antwort: {raw_response_text}"
                raise ValueError(error_message)
        
        if not style_guide_json_str:
            raise ValueError("Die KI hat eine leere Antwort für den Styleguide zurückgegeben.")
        
        # Parse the JSON response
        guide_dict = json.loads(style_guide_json_str)
        
        # Validate structure
        if not isinstance(guide_dict, dict):
            raise ValueError("KI-Antwort ist kein Dictionary")
        
        if "style_guide" not in guide_dict or "key_terms" not in guide_dict:
            raise ValueError("KI-Antwort fehlt erforderliche Schlüssel 'style_guide' oder 'key_terms'")
        
        # Store style guide in Cloud Storage
        storage_client = storage.Client(project="avid-infinity-458913-p3")
        bucket = storage_client.bucket("manuskripte-upload-avid-infinity")
        style_guide_blob_name = f"{job_id}/style_guide.json"
        style_guide_blob = bucket.blob(style_guide_blob_name)
        style_guide_blob.upload_from_string(style_guide_json_str, content_type='application/json')
        
        # Update Firestore with style guide path and status
        style_guide_gcs_path = f"gs://manuskripte-upload-avid-infinity/{style_guide_blob_name}"
        firestore_client.collection("translation_jobs").document(job_id).update({
            "style_guide_gcs_path": style_guide_gcs_path,
            "status": "analyzed",
            "analyzed_at": datetime.datetime.utcnow()
        })
        
        print(f"✅ Style-Guide erfolgreich generiert und gespeichert: {style_guide_gcs_path}")
        return guide_dict
        
    except ValueError as e:
        print(f"❌ Validierungsfehler: {e}")
        # Update Firestore with error status
        try:
            firestore_client = firestore.Client(project="avid-infinity-458913-p3", database="hbu-toolbox-firestone")
            firestore_client.collection("translation_jobs").document(job_id).update({
                "status": "analysis_failed",
                "error_message": str(e),
                "analysis_failed_at": datetime.datetime.utcnow()
            })
        except Exception as firestore_error:
            print(f"⚠️ Konnte Fehler-Status nicht speichern: {firestore_error}")
        raise e
        
    except Exception as e:
        print(f"❌ Unerwarteter Fehler: {e}")
        # Update Firestore with error status
        try:
            firestore_client = firestore.Client(project="avid-infinity-458913-p3", database="hbu-toolbox-firestone")
            firestore_client.collection("translation_jobs").document(job_id).update({
                "status": "analysis_failed",
                "error_message": str(e),
                "analysis_failed_at": datetime.datetime.utcnow()
            })
        except Exception as firestore_error:
            print(f"⚠️ Konnte Fehler-Status nicht speichern: {firestore_error}")
        
        # Return fallback dictionary with new structure
        return {
            "style_guide": {
                "genre_audience": "Genre und Zielgruppe konnten nicht analysiert werden",
                "tone_mood": "Ton und Stimmung konnten nicht analysiert werden", 
                "narrative_perspective": "Erzählperspektive konnte nicht analysiert werden",
                "character_names": "Charakternamen konnten nicht analysiert werden",
                "key_concepts": "Schlüsselkonzepte konnten nicht analysiert werden",
                "stylistic_features": "Stilistische Merkmale konnten nicht analysiert werden"
            },
            "key_terms": {}
        }


@log_exceptions
def translate_chunk(guide: dict, german_chunk: str, previous_english_chunk: str = None, gemini_api_key: str = None) -> str:
    """Übersetzt einen deutschen Textabschnitt ins Englische basierend auf dem Leitfaden."""
    try:
        if gemini_api_key:
            genai.configure(api_key=gemini_api_key)
        
        # Extrahiere die Style-Guide-Komponenten
        style_guide = guide.get("style_guide", {})
        key_terms = guide.get("key_terms", {})
        
        # Formatiere die Key Terms für den Prompt
        key_terms_formatted = "\n".join([f"  '{deutsch}' → '{englisch}'" for deutsch, englisch in key_terms.items()])
        if not key_terms_formatted:
            key_terms_formatted = "  Keine spezifischen Übersetzungen definiert"
        
        # Verwende leeren String falls kein vorheriger Chunk vorhanden
        prev_chunk = previous_english_chunk if previous_english_chunk else ""
        
        full_prompt = TRANSLATE_CHUNK_PROMPT.format(
            genre_audience=style_guide.get("genre_audience", "Nicht spezifiziert"),
            tone_mood=style_guide.get("tone_mood", "Nicht spezifiziert"),
            narrative_perspective=style_guide.get("narrative_perspective", "Nicht spezifiziert"),
            character_names=style_guide.get("character_names", "Nicht spezifiziert"),
            key_concepts=style_guide.get("key_concepts", "Nicht spezifiziert"),
            stylistic_features=style_guide.get("stylistic_features", "Nicht spezifiziert"),
            key_terms_formatted=key_terms_formatted,
            german_chunk=german_chunk,
            previous_english_chunk=prev_chunk
        )
        
        logger.info(f"Übersetze Chunk mit Style-Guide: Genre={style_guide.get('genre_audience', 'N/A')}, Ton={style_guide.get('tone_mood', 'N/A')}")
        logger.info(f"Verfügbare Key Terms: {list(key_terms.keys())}")
        
        response = model_gemini.generate_content(full_prompt)
        return response.text.strip()
    except Exception as e:
        logger.error(f"Fehler bei der Übersetzung des Chunks: {e}", exc_info=True)
        return f"[Übersetzungsfehler: {e}]"


@log_exceptions
def translate_manuscript_with_cache(cached_content_name: str, style_guide: dict, job_id: str, gemini_api_key: str = None) -> str:
    """Übersetzt ein komplettes Manuskript mit Vertex AI Cache und behält die Formatierung bei."""
    try:
        # Initialisiere Vertex AI
        vertexai.init(project="avid-infinity-458913-p3")
        
        # Lade den Cache
        cache = vertexai.caching.CachedContent.get(cached_content_name)
        if not cache:
            raise ValueError(f"Cache {cached_content_name} nicht gefunden")
        
        # Erstelle das Modell mit dem Cache
        model_with_cache = GenerativeModel.from_cached_content(cached_content=cache)
        
        # Erstelle den Übersetzungs-Prompt
        prompt = f"""Übersetze das folgende, vollständige deutsche Manuskript ins Englische. 
Gib NUR den übersetzten Text zurück, ohne zusätzliche Kommentare oder Formatierungen.

Beachte dabei strikt die folgenden Regeln aus dem Styleguide und dem Glossar, um Konsistenz zu gewährleisten:

STYLEGUIDE & GLOSSAR:
{json.dumps(style_guide, ensure_ascii=False, indent=2)}

DEUTSCHES MANUSKRIPT:
"""
        
        # Übersetzung durchführen
        response = model_with_cache.generate_content(prompt)
        
        if not response.text:
            raise ValueError("Gemini hat keine Antwort zurückgegeben")
        
        translated_text = response.text.strip()
        logger.info(f"Übersetzung erhalten: {len(translated_text)} Zeichen")
        
        return translated_text
        
    except Exception as e:
        logger.error(f"Fehler bei der Übersetzung mit Cache: {e}", exc_info=True)
        raise e


@log_exceptions
def create_formatted_docx(translated_text: str, output_filename: str) -> bytes:
    """Erstellt ein formatiertes DOCX-Dokument mit erhaltener Absatzstruktur."""
    try:
        from docx import Document
        from docx.shared import Inches
        import io
        
        # Neues Dokument erstellen
        doc = Document()
        
        # Standard-Seiteneinstellungen
        section = doc.sections[0]
        section.page_width = Inches(8.5)
        section.page_height = Inches(11)
        section.left_margin = Inches(1)
        section.right_margin = Inches(1)
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        
        # Teile den Gesamttext in einzelne Absätze auf
        paragraphs = translated_text.split('\n')
        for paragraph_text in paragraphs:
            # Füge leere Absätze für Zeilenumbrüche hinzu oder Text für normale Absätze
            if paragraph_text.strip():
                doc.add_paragraph(paragraph_text)
            else:
                doc.add_paragraph()  # Fügt einen leeren Absatz für die Formatierung hinzu
        
        # Dokument im Speicher speichern
        doc_stream = io.BytesIO()
        doc.save(doc_stream)
        doc_stream.seek(0)
        
        logger.info(f"Formatiertes DOCX-Dokument erstellt: {output_filename}")
        return doc_stream.getvalue()
        
    except Exception as e:
        logger.error(f"Fehler beim Erstellen des DOCX-Dokuments: {e}", exc_info=True)
        raise e

@st.cache_data(ttl=3600)
@log_exceptions
def get_google_tts_voices() -> Dict[str, Dict[str, str]]:
    """
    Ruft die verfügbaren deutschen Google TTS Stimmen ab (WaveNet & Studio).
    Gibt ein Dictionary zurück:
    {'Stimmenname': {'voice_id': 'xyz', 'language': 'de-DE', 'gender': 'MALE/FEMALE'}}
    """
    try:
        from google.cloud import texttospeech

        client = texttospeech.TextToSpeechClient()
        response = client.list_voices(language_code="de-DE")
        
        voice_dict = {}
        for voice in response.voices:
            # Filtere für hochwertige Stimmen (WaveNet oder die neueren Studio-Stimmen)
            if "Wavenet" in voice.name or "Studio" in voice.name:
                gender = texttospeech.SsmlVoiceGender(voice.ssml_gender).name
                voice_name = f"{voice.name} ({gender})"
                voice_dict[voice_name] = {
                    "voice_id": voice.name,
                    "language": "de-DE",
                    "gender": gender
                }
        
        # Sortiere das Dictionary alphabetisch nach dem Anzeigenamen
        sorted_voice_dict = dict(sorted(voice_dict.items()))
        return sorted_voice_dict
        
    except Exception as e:
        logger.error(f"Fehler beim Abrufen der Google TTS Stimmen: {e}", exc_info=True)
        # Fallback auf eine bekannte gute Stimme
        return {
            "de-DE-Wavenet-F (FEMALE)": {"voice_id": "de-DE-Wavenet-F", "language": "de-DE", "gender": "FEMALE"}
        }

def wrap_in_speak_tags(content: str) -> str:
    """
    Ensures SSML content is properly wrapped in <speak> tags.
    If already wrapped, returns as is. If not, wraps the content.
    """
    # Remove leading/trailing whitespace
    content = content.strip()
    
    # Check if already wrapped in speak tags
    if content.startswith('<speak>') and content.endswith('</speak>'):
        return content
    
    # Remove any existing speak tags to avoid nesting
    content = re.sub(r'^\s*<speak>\s*', '', content, flags=re.IGNORECASE)
    content = re.sub(r'\s*</speak>\s*$', '', content, flags=re.IGNORECASE)
    
    # Wrap in speak tags
    return f'<speak>{content}</speak>'


def clean_ssml_for_studio_voices(ssml_content: str) -> str:
    """
    Removes SSML tags that are not supported by Studio voices.
    Studio voices don't support: <mark>, <emphasis>, <prosody pitch>, and <lang>
    """
    # Remove <emphasis> tags but keep the content
    ssml_content = re.sub(r'<emphasis[^>]*>(.*?)</emphasis>', r'', ssml_content, flags=re.IGNORECASE)
    
    # Remove <mark> tags but keep the content
    ssml_content = re.sub(r'<mark[^>]*>(.*?)</mark>', r'', ssml_content, flags=re.IGNORECASE)
    
    # Remove <prosody pitch> attributes but keep other prosody attributes
    ssml_content = re.sub(r'<prosody[^>]*pitch[^>]*>', '<prosody>', ssml_content, flags=re.IGNORECASE)
    
    # Remove <lang> tags but keep the content
    ssml_content = re.sub(r'<lang[^>]*>(.*?)</lang>', r'', ssml_content, flags=re.IGNORECASE)
    
    return ssml_content


def validate_and_clean_ssml(ssml_content: str) -> str:
    """
    Validates and cleans SSML content to ensure it's compatible with all voice types.
    Removes malformed tags, fixes common issues, and ensures proper structure.
    """
    if not ssml_content or not ssml_content.strip():
        return ssml_content
    
    # Remove any XML declaration
    ssml_content = re.sub(r'<\?xml.*?\?>\s*', '', ssml_content, flags=re.IGNORECASE)
    
    # Remove any leading/trailing whitespace
    ssml_content = ssml_content.strip()
    
    # Fix common malformed tags
    # Fix unclosed tags (basic fix)
    ssml_content = re.sub(r'<break\s+time="([^"]*)"\s*/>', r'<break time=""/>', ssml_content)
    ssml_content = re.sub(r'<break\s+time="([^"]*)"\s*>\s*</break>', r'<break time=""/>', ssml_content)
    
    # Remove any malformed prosody tags
    ssml_content = re.sub(r'<prosody[^>]*>\s*</prosody>', '', ssml_content)
    
    # Fix nested speak tags
    ssml_content = re.sub(r'<speak[^>]*>\s*<speak[^>]*>', '<speak>', ssml_content)
    ssml_content = re.sub(r'</speak>\s*</speak>', '</speak>', ssml_content)
    
    # Remove any empty tags
    ssml_content = re.sub(r'<(\w+)[^>]*>\s*</>', '', ssml_content)
    
    # Ensure proper break tag format
    ssml_content = re.sub(r'<break\s+time="([^"]*)"\s*/>', r'<break time=""/>', ssml_content)
    
    # Remove any invalid characters that might cause issues
    ssml_content = re.sub(r'[^ -~ -￿]', '', ssml_content)
    
    return ssml_content


def log_ssml_debug_info(ssml_content: str, voice_name: str, chunk_index: int = None):
    """
    Logs SSML content for debugging purposes.
    """
    try:
        # Log basic info
        logging.info(f"SSML Debug - Voice: {voice_name}, Chunk: {chunk_index}")
        logging.info(f"SSML Length: {len(ssml_content)} characters")
        
        # Log first 200 characters for debugging
        preview = ssml_content[:200] + "..." if len(ssml_content) > 200 else ssml_content
        logging.info(f"SSML Preview: {preview}")
        
        # Check for common issues
        if '<speak>' not in ssml_content.lower():
            logging.warning("SSML missing <speak> tags")
        if ssml_content.count('<speak>') != ssml_content.count('</speak>'):
            logging.warning("SSML has mismatched <speak> tags")
        if '<emphasis>' in ssml_content and 'Studio' in voice_name:
            logging.warning("SSML contains <emphasis> tags for Studio voice")
            
    except Exception as e:
        logging.error(f"Error in SSML debug logging: {e}")



def create_fallback_ssml(text_content: str) -> str:
    """
    Creates a simple, valid SSML fallback when the AI-generated SSML is invalid.
    """
    # Clean the text content
    text_content = text_content.strip()
    
    # Remove any existing SSML tags
    text_content = re.sub(r'<[^>]+>', '', text_content)
    
    # Create simple, valid SSML with just the text
    return f'<speak>{text_content}</speak>'



def create_minimal_valid_ssml(text_content: str) -> str:
    """
    Creates minimal, guaranteed valid SSML by stripping all tags and using only basic structure.
    This is a last resort when AI-generated SSML is completely invalid.
    """
    if not text_content or not text_content.strip():
        return '<speak>Text content is empty.</speak>'
    
    # Strip all SSML tags and get clean text
    clean_text = re.sub(r'<[^>]+>', '', text_content)
    clean_text = clean_text.strip()
    
    # If text is too short, return a simple message
    if len(clean_text) < 3:
        return '<speak>Content is too short to process.</speak>'
    
    # Create minimal valid SSML with just the text
    return f'<speak>{clean_text}</speak>'

def is_ssml_valid(ssml_content: str) -> bool:
    """
    Basic validation to check if SSML content is likely valid.
    """
    if not ssml_content or not ssml_content.strip():
        return False
    
    # Check for basic SSML structure
    if '<speak>' not in ssml_content.lower() or '</speak>' not in ssml_content.lower():
        return False
    
    # Check for balanced tags
    open_tags = ssml_content.count('<')
    close_tags = ssml_content.count('>')
    if open_tags != close_tags:
        return False
    
    # Check for common problematic patterns
    problematic_patterns = [
        r'<[^>]*>[^<]*<[^>]*>[^<]*</[^>]*>',  # Nested tags without proper structure
        r'<break[^>]*>[^<]*</break>',  # Break tags with content
        r'<prosody[^>]*pitch[^>]*>',  # Pitch attributes (not supported by Studio)
    ]
    
    for pattern in problematic_patterns:
        if re.search(pattern, ssml_content, re.IGNORECASE):
            return False
    
    return True



def safe_synthesize_speech(client, synthesis_input, voice, audio_config, max_retries=2):
    """
    Safely calls synthesize_speech with fallback mechanisms for SSML errors.
    """
    for attempt in range(max_retries + 1):
        try:
            response = client.synthesize_speech(
                input=synthesis_input,
                voice=voice,
                audio_config=audio_config
            )
            return response
        except Exception as e:
            error_msg = str(e)
            logging.warning(f"TTS API call failed (attempt {attempt + 1}): {error_msg}")
            
            # If it's an SSML error and we have retries left, try with minimal SSML
            if "Invalid SSML" in error_msg and attempt < max_retries:
                logging.info("Retrying with minimal SSML...")
                # Extract text content and create minimal SSML
                ssml_text = synthesis_input.ssml
                clean_text = re.sub(r'<[^>]+>', '', ssml_text)
                minimal_ssml = f'<speak>{clean_text.strip()}</speak>'
                synthesis_input = texttospeech.SynthesisInput(ssml=minimal_ssml)
                continue
            else:
                # If all retries failed, raise the original exception
                raise e

def generate_long_audio_gcs(ssml_content: str, voice_name: str, language_code: str, project_id: str, gcs_output_bucket: str) -> bytes:
    """
    Synthesizes audio from SSML content using standard TTS API (not Long Audio API).
    Processes in chunks if needed and returns the audio data as bytes.
    """
    try:
        from google.cloud import texttospeech
        import io
        from pydub import AudioSegment
        
        # Initialize standard TTS client (not Long Audio client)
        client = texttospeech.TextToSpeechClient()
        
        # Check if SSML content is too long for standard API (limit is ~5000 characters)
        max_chunk_size = 4500  # Leave some buffer
        
        if len(ssml_content) <= max_chunk_size:
            # Single request for shorter content
            st.info("Generiere Audio mit Standard TTS API...")
            
            synthesis_input = texttospeech.SynthesisInput(ssml=ssml_content)
            voice = texttospeech.VoiceSelectionParams(
                language_code=language_code,
                name=voice_name
            )
            audio_config = texttospeech.AudioConfig(
                audio_encoding=texttospeech.AudioEncoding.LINEAR16
            )
            
            response = safe_synthesize_speech(
                client, synthesis_input, voice, audio_config
            )
            
            st.success("Audio erfolgreich generiert!")
            return response.audio_content
            
        else:
            # Split into chunks for longer content
            st.info("Langer Text erkannt. Verarbeite in mehreren Chunks...")
            
            # Simple SSML-aware chunking (split on sentence boundaries)
            chunks = []
            current_chunk = ""
            
            # Split by sentences but preserve SSML tags
            sentences = ssml_content.split('.')
            
            for sentence in sentences:
                if len(current_chunk + sentence + '.') <= max_chunk_size:
                    current_chunk += sentence + '.'
                else:
                    if current_chunk:
                        chunks.append(current_chunk.strip())
                    current_chunk = sentence + '.'
            
            if current_chunk:
                chunks.append(current_chunk.strip())
            
            # Synthesize each chunk
            audio_segments = []
            progress_bar = st.progress(0, text=f"Verarbeite Chunk 1/{len(chunks)}")
            
            for i, chunk in enumerate(chunks):
                # Ensure chunk is wrapped in speak tags

                # Clean SSML for Studio voices if needed


                # Validate and clean SSML content


                chunk = validate_and_clean_ssml(chunk)


                # Log SSML debug info


                log_ssml_debug_info(chunk, voice_name, i)


                # If SSML is still invalid, use fallback


                if not chunk or len(chunk.strip()) < 10 or not is_ssml_valid(chunk):


                    chunk = create_minimal_valid_ssml(chunk)


                if "Studio" in voice_name:


                    chunk = clean_ssml_for_studio_voices(chunk)


                wrapped_chunk = wrap_in_speak_tags(chunk)

                synthesis_input = texttospeech.SynthesisInput(ssml=wrapped_chunk)
                voice = texttospeech.VoiceSelectionParams(
                    language_code=language_code,
                    name=voice_name
                )
                audio_config = texttospeech.AudioConfig(
                    audio_encoding=texttospeech.AudioEncoding.LINEAR16
                )
                
                response = safe_synthesize_speech(
                    client, synthesis_input, voice, audio_config
                )
                
                # Convert to AudioSegment for combining
                audio_segment = AudioSegment.from_wav(io.BytesIO(response.audio_content))
                audio_segments.append(audio_segment)
                
                progress_bar.progress((i + 1) / len(chunks), text=f"Verarbeite Chunk {i+1}/{len(chunks)}")
            
            # Combine all audio segments
            st.info("Kombiniere Audio-Segmente...")
            combined_audio = audio_segments[0]
            for segment in audio_segments[1:]:
                combined_audio += segment
            
            # Export to bytes
            output_buffer = io.BytesIO()
            combined_audio.export(output_buffer, format="wav")
            output_buffer.seek(0)
            
            st.success(f"Audio erfolgreich aus {len(chunks)} Chunks kombiniert!")
            return output_buffer.getvalue()

    except Exception as e:
        logging.error(f"Error in generate_long_audio_gcs: {e}", exc_info=True)
        st.error(f"Fehler bei der Audiosynthese: {e}")
        return None


def simple_generate_audio(text_content: str, voice_name: str, language_code: str = "de-DE") -> bytes:
    """
    Simple TTS function: truncate text to API limit and generate audio.
    No complex SSML, no chunking, just straightforward text-to-speech.
    """
    try:
        from google.cloud import texttospeech
        
        # Initialize TTS client
        client = texttospeech.TextToSpeechClient()
        
        # Truncate text to API limit (5000 characters)
        max_length = 4500  # Leave some buffer
        if len(text_content) > max_length:
            text_content = text_content[:max_length]
            st.warning(f"Text truncated to {max_length} characters due to API limits")
        
        # Create synthesis input with plain text (no SSML)
        synthesis_input = texttospeech.SynthesisInput(text=text_content)
        
        # Set up voice parameters
        voice = texttospeech.VoiceSelectionParams(
            language_code=language_code,
            name=voice_name
        )
        
        # Set up audio configuration
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3
        )
        
        # Generate speech
        response = client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )
        
        st.success("Audio generated successfully!")
        return response.audio_content
        
    except Exception as e:
        st.error(f"Error generating audio: {e}")
        return None



# ==============================================================================
# SIMPLE TTS IMPLEMENTATION
# ==============================================================================

def detect_language(text_content: str) -> str:
    """
    Detects the language of the given text using Google Cloud Translation API.
    Returns a language code (e.g., 'en', 'de', 'fr').
    """
    try:
        from google.cloud import translate_v2 as translate
        
        # Initialize Translation client
        translate_client = translate.Client()
        
        # Detect language (use first 1000 chars for detection)
        sample_text = text_content[:1000]
        result = translate_client.detect_language(sample_text)
        
        detected_lang = result['language']
        confidence = result['confidence']
        
        logging.info(f"Detected language: {detected_lang} (confidence: {confidence})")
        return detected_lang
        
    except Exception as e:
        logging.error(f"Error detecting language: {e}", exc_info=True)
        return "en"  # Default to English

def get_voices_for_language(language_code: str) -> dict:
    """
    Returns appropriate voices for the detected language.
    """
    # Map language codes to voice options
    voice_map = {
        'de': {
            "Deutsch - Standard A (Female)": {"name": "de-DE-Standard-A", "language_code": "de-DE"},
            "Deutsch - Standard B (Male)": {"name": "de-DE-Standard-B", "language_code": "de-DE"},
            "Deutsch - Wavenet A (Female)": {"name": "de-DE-Wavenet-A", "language_code": "de-DE"},
            "Deutsch - Wavenet B (Male)": {"name": "de-DE-Wavenet-B", "language_code": "de-DE"},
            "Deutsch - Wavenet C (Female)": {"name": "de-DE-Wavenet-C", "language_code": "de-DE"},
            "Deutsch - Wavenet D (Male)": {"name": "de-DE-Wavenet-D", "language_code": "de-DE"},
        },
        'en': {
            "English (US) - Standard A (Female)": {"name": "en-US-Standard-A", "language_code": "en-US"},
            "English (US) - Standard B (Male)": {"name": "en-US-Standard-B", "language_code": "en-US"},
            "English (US) - Standard C (Female)": {"name": "en-US-Standard-C", "language_code": "en-US"},
            "English (US) - Standard D (Male)": {"name": "en-US-Standard-D", "language_code": "en-US"},
            "English (US) - Wavenet A (Female)": {"name": "en-US-Wavenet-A", "language_code": "en-US"},
            "English (US) - Wavenet B (Male)": {"name": "en-US-Wavenet-B", "language_code": "en-US"},
            "English (US) - Wavenet C (Female)": {"name": "en-US-Wavenet-C", "language_code": "en-US"},
            "English (US) - Wavenet D (Male)": {"name": "en-US-Wavenet-D", "language_code": "en-US"},
        },
        'fr': {
            "Français - Standard A (Female)": {"name": "fr-FR-Standard-A", "language_code": "fr-FR"},
            "Français - Standard B (Male)": {"name": "fr-FR-Standard-B", "language_code": "fr-FR"},
            "Français - Wavenet A (Female)": {"name": "fr-FR-Wavenet-A", "language_code": "fr-FR"},
            "Français - Wavenet B (Male)": {"name": "fr-FR-Wavenet-B", "language_code": "fr-FR"},
        },
        'es': {
            "Español - Standard A (Female)": {"name": "es-ES-Standard-A", "language_code": "es-ES"},
            "Español - Standard B (Male)": {"name": "es-ES-Standard-B", "language_code": "es-ES"},
            "Español - Wavenet B (Male)": {"name": "es-ES-Wavenet-B", "language_code": "es-ES"},
            "Español - Wavenet C (Female)": {"name": "es-ES-Wavenet-C", "language_code": "es-ES"},
        },
        'it': {
            "Italiano - Standard A (Female)": {"name": "it-IT-Standard-A", "language_code": "it-IT"},
            "Italiano - Wavenet A (Female)": {"name": "it-IT-Wavenet-A", "language_code": "it-IT"},
            "Italiano - Wavenet B (Female)": {"name": "it-IT-Wavenet-B", "language_code": "it-IT"},
            "Italiano - Wavenet C (Male)": {"name": "it-IT-Wavenet-C", "language_code": "it-IT"},
        },
    }
    
    # Return voices for the detected language, default to English
    return voice_map.get(language_code, voice_map['en'])

def simple_text_to_speech(text_content: str, voice_name: str, language_code: str) -> bytes:
    """
    Simple TTS function that converts text directly to audio.
    Truncates text to API limits and generates audio.
    """
    try:
        from google.cloud import texttospeech
        
        # Initialize TTS client
        client = texttospeech.TextToSpeechClient()
        
        # Truncate text to API limit (5000 characters for standard API)
        max_chars = 4500  # Leave some buffer
        if len(text_content) > max_chars:
            text_content = text_content[:max_chars]
            logging.info(f"Text truncated to {max_chars} characters")
        
        # Create synthesis input
        synthesis_input = texttospeech.SynthesisInput(text=text_content)
        
        # Voice selection with detected language
        voice = texttospeech.VoiceSelectionParams(
            language_code=language_code,
            name=voice_name
        )
        
        # Audio config
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.LINEAR16
        )
        
        # Generate speech
        response = client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )
        
        return response.audio_content
        
    except Exception as e:
        logging.error(f"Error in simple_text_to_speech: {e}", exc_info=True)
        return None

def get_simple_voices() -> dict:
    """
    Returns a simple list of common voices (kept for backward compatibility).
    """
    return {
        "en-US-Standard-A (Female)": "en-US-Standard-A",
        "en-US-Standard-B (Male)": "en-US-Standard-B", 
        "en-US-Standard-C (Female)": "en-US-Standard-C",
        "en-US-Standard-D (Male)": "en-US-Standard-D",
        "en-US-Wavenet-A (Female)": "en-US-Wavenet-A",
        "en-US-Wavenet-B (Male)": "en-US-Wavenet-B",
        "en-US-Wavenet-C (Female)": "en-US-Wavenet-C",
        "en-US-Wavenet-D (Male)": "en-US-Wavenet-D",
        "de-DE-Standard-A (Female)": "de-DE-Standard-A",
        "de-DE-Standard-B (Male)": "de-DE-Standard-B",
        "de-DE-Wavenet-A (Female)": "de-DE-Wavenet-A",
        "de-DE-Wavenet-B (Male)": "de-DE-Wavenet-B"
    }

def long_audio_synthesis(text_content: str, voice_name: str, language_code: str, gcs_bucket: str, project_id: str) -> dict:
    """
    Uses Google Cloud TTS Long Audio Synthesis API for texts longer than 5000 characters.
    Supports up to 1,000,000 characters.
    Returns a dict with status and GCS URI or audio content.
    """
    try:
        from google.cloud import texttospeech_v1
        from google.cloud import storage
        import time
        
        # Initialize TTS client
        client = texttospeech_v1.TextToSpeechLongAudioSynthesizeClient()
        
        # Check text length
        max_chars = 1000000  # Long Audio API supports up to 1 million characters
        if len(text_content) > max_chars:
            logging.warning(f"Text too long ({len(text_content)} chars). Truncating to {max_chars} characters.")
            text_content = text_content[:max_chars]
        
        logging.info(f"Starting long audio synthesis for {len(text_content)} characters")
        
        # Create unique output filename
        output_gcs_uri = f"gs://{gcs_bucket}/tts_output_{int(time.time())}.wav"
        
        # Create synthesis input
        input_config = texttospeech_v1.SynthesisInput(text=text_content)
        
        # Voice selection
        voice_config = texttospeech_v1.VoiceSelectionParams(
            language_code=language_code,
            name=voice_name
        )
        
        # Audio config - Long Audio API currently only supports LINEAR16 (WAV)
        audio_config = texttospeech_v1.AudioConfig(
            audio_encoding=texttospeech_v1.AudioEncoding.LINEAR16
        )
        
        # Create the request
        request = texttospeech_v1.SynthesizeLongAudioRequest(
            parent=f"projects/{project_id}/locations/global",
            input=input_config,
            voice=voice_config,
            audio_config=audio_config,
            output_gcs_uri=output_gcs_uri
        )
        
        # Start the long audio synthesis operation
        logging.info(f"Submitting long audio synthesis request to GCS: {output_gcs_uri}")
        operation = client.synthesize_long_audio(request=request)
        
        logging.info("Waiting for long audio synthesis to complete...")
        # Wait for the operation to complete
        response = operation.result(timeout=600)  # 10 minute timeout
        
        logging.info(f"Long audio synthesis completed. Output: {output_gcs_uri}")
        
        # Download the audio from GCS
        storage_client = storage.Client()
        bucket = storage_client.bucket(gcs_bucket)
        blob_name = output_gcs_uri.replace(f"gs://{gcs_bucket}/", "")
        blob = bucket.blob(blob_name)
        
        # Download audio content
        audio_bytes = blob.download_as_bytes()
        logging.info(f"Downloaded audio from GCS: {len(audio_bytes)} bytes")
        
        # Optionally delete the file from GCS after download
        try:
            blob.delete()
            logging.info(f"Deleted temporary file from GCS: {blob_name}")
        except Exception as e:
            logging.warning(f"Could not delete temporary file from GCS: {e}")
        
        return {
            'status': 'success',
            'audio_content': audio_bytes,
            'gcs_uri': output_gcs_uri,
            'format': 'wav'
        }
        
    except Exception as e:
        logging.error(f"Error in long_audio_synthesis: {e}", exc_info=True)
        return {
            'status': 'error',
            'error': str(e)
        }

def smart_text_to_speech(text_content: str, voice_name: str, language_code: str, gcs_bucket: str = None, project_id: str = None) -> tuple:
    """
    Smart TTS function that automatically chooses between standard and long audio synthesis
    based on text length.
    Returns: (audio_bytes, format) tuple where format is 'wav'
    Note: Both standard and long audio synthesis return WAV format.
    """
    try:
        # Threshold for switching to long audio synthesis
        long_audio_threshold = 4500
        
        if len(text_content) <= long_audio_threshold:
            # Use standard synthesis for short texts
            logging.info(f"Using standard synthesis for {len(text_content)} characters")
            audio_data = simple_text_to_speech(text_content, voice_name, language_code)
            return (audio_data, 'wav') if audio_data else (None, None)
        else:
            # Use long audio synthesis for long texts
            if not gcs_bucket or not project_id:
                logging.error("GCS bucket and project ID required for long audio synthesis")
                return (None, None)
            
            logging.info(f"Using long audio synthesis for {len(text_content)} characters")
            result = long_audio_synthesis(text_content, voice_name, language_code, gcs_bucket, project_id)
            
            if result['status'] == 'success':
                return (result['audio_content'], result['format'])
            else:
                logging.error(f"Long audio synthesis failed: {result.get('error')}")
                return (None, None)
                
    except Exception as e:
        logging.error(f"Error in smart_text_to_speech: {e}", exc_info=True)
        return (None, None)

def generate_simple_ssml(text_content: str, gemini_api_key: str) -> str:
    """
    Uses Gemini to generate simple, natural SSML for text-to-speech.
    Handles size management to avoid exceeding API limits.
    Returns SSML-enriched text or original text if generation fails.
    """
    try:
        import google.generativeai as genai
        
        # Configure Gemini
        genai.configure(api_key=gemini_api_key)
        model = genai.GenerativeModel('gemini-2.5-flash')
        
        # Estimate SSML expansion (typically 30-50% increase)
        estimated_ssml_size = int(len(text_content) * 1.4)
        
        # Define size limits based on expected usage
        standard_api_limit = 4500
        long_api_limit = 1000000
        
        # If text is too long even with expansion, we need to be more conservative
        if estimated_ssml_size > long_api_limit:
            logging.warning(f"Text too long for SSML enrichment ({len(text_content)} chars, estimated {estimated_ssml_size} with SSML). Using plain text.")
            return text_content
        
        # Create a simplified SSML prompt for TTS
        ssml_prompt = f"""Generate natural SSML markup for text-to-speech. 

Rules:
1. DO NOT change or modify the original text in any way
2. ONLY add these SSML tags where appropriate:
   - <break time="0.5s"/> for short pauses
   - <break time="1s"/> for longer pauses
   - <prosody rate="slow">text</prosody> for slower speech
   - <prosody rate="fast">text</prosody> for faster speech
3. Use pauses at sentence breaks and paragraph boundaries
4. Keep it SIMPLE - don't over-tag
5. Return ONLY the SSML-enriched text, WITHOUT <speak> tags
6. Maximum expansion: 30% of original text length

Text to enrich:
---
{text_content[:5000]}
---

Return the SSML-enriched text:"""

        # Generate SSML
        logging.info(f"Generating SSML with Gemini for {len(text_content)} characters...")
        response = model.generate_content(ssml_prompt)
        ssml_text = response.text.strip()
        
        # Validate SSML size
        if len(ssml_text) > long_api_limit:
            logging.warning(f"Generated SSML too long ({len(ssml_text)} chars). Using plain text.")
            return text_content
        
        # Basic SSML validation
        if '<' not in ssml_text or '>' not in ssml_text:
            logging.warning("Generated text doesn't appear to contain SSML tags. Using original text.")
            return text_content
        
        logging.info(f"SSML generated successfully. Original: {len(text_content)} chars, SSML: {len(ssml_text)} chars (expansion: {((len(ssml_text)/len(text_content))-1)*100:.1f}%)")
        return ssml_text
        
    except Exception as e:
        logging.error(f"Error generating SSML: {e}. Using plain text.", exc_info=True)
        return text_content

def text_to_speech_with_ssml(text_content: str, voice_name: str, language_code: str, gcs_bucket: str = None, project_id: str = None, gemini_api_key: str = None, use_ssml: bool = True) -> tuple:
    """
    Advanced TTS function that optionally generates SSML for more natural speech.
    
    Args:
        text_content: The text to convert to speech
        voice_name: The voice to use
        language_code: The language code
        gcs_bucket: GCS bucket for long audio synthesis
        project_id: Google Cloud project ID
        gemini_api_key: Gemini API key for SSML generation
        use_ssml: Whether to use SSML enrichment (default: True)
    
    Returns: (audio_bytes, format, ssml_used) tuple
    """
    try:
        ssml_used = False
        final_text = text_content
        
        # Generate SSML if enabled and Gemini key is available
        if use_ssml and gemini_api_key and len(text_content) > 100:
            logging.info("Attempting to generate SSML for more natural speech...")
            ssml_text = generate_simple_ssml(text_content, gemini_api_key)
            
            # Only use SSML if it's different from original and within limits
            if ssml_text != text_content:
                final_text = ssml_text
                ssml_used = True
                logging.info("Using SSML-enriched text for synthesis")
            else:
                logging.info("SSML generation failed or returned original text. Using plain text.")
        
        # Use the appropriate TTS method based on text length
        long_audio_threshold = 4500
        
        if len(final_text) <= long_audio_threshold:
            # Standard synthesis
            logging.info(f"Using standard synthesis for {len(final_text)} characters")
            
            # Use SSML input if we generated SSML
            if ssml_used:
                audio_data = simple_text_to_speech_ssml(final_text, voice_name, language_code)
            else:
                audio_data = simple_text_to_speech(final_text, voice_name, language_code)
            
            return (audio_data, 'wav', ssml_used) if audio_data else (None, None, False)
        else:
            # Long audio synthesis
            if not gcs_bucket or not project_id:
                logging.error("GCS bucket and project ID required for long audio synthesis")
                return (None, None, False)
            
            logging.info(f"Using long audio synthesis for {len(final_text)} characters")
            result = long_audio_synthesis_ssml(final_text, voice_name, language_code, gcs_bucket, project_id, use_ssml=ssml_used)
            
            if result['status'] == 'success':
                return (result['audio_content'], result['format'], ssml_used)
            else:
                logging.error(f"Long audio synthesis failed: {result.get('error')}")
                return (None, None, False)
                
    except Exception as e:
        logging.error(f"Error in text_to_speech_with_ssml: {e}", exc_info=True)
        return (None, None, False)

def simple_text_to_speech_ssml(ssml_content: str, voice_name: str, language_code: str) -> bytes:
    """
    TTS function that uses SSML input instead of plain text.
    """
    try:
        from google.cloud import texttospeech
        
        # Initialize TTS client
        client = texttospeech.TextToSpeechClient()
        
        # Wrap SSML in speak tags
        if not ssml_content.strip().startswith('<speak>'):
            ssml_content = f'<speak>{ssml_content}</speak>'
        
        # Create synthesis input with SSML
        synthesis_input = texttospeech.SynthesisInput(ssml=ssml_content)
        
        # Voice selection
        voice = texttospeech.VoiceSelectionParams(
            language_code=language_code,
            name=voice_name
        )
        
        # Audio config
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.LINEAR16
        )
        
        # Generate speech
        response = client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config
        )
        
        return response.audio_content
        
    except Exception as e:
        logging.error(f"Error in simple_text_to_speech_ssml: {e}", exc_info=True)
        return None

def long_audio_synthesis_ssml(content: str, voice_name: str, language_code: str, gcs_bucket: str, project_id: str, use_ssml: bool = False) -> dict:
    """
    Long audio synthesis that supports both text and SSML input.
    """
    try:
        from google.cloud import texttospeech_v1
        from google.cloud import storage
        import time
        
        # Initialize TTS client
        client = texttospeech_v1.TextToSpeechLongAudioSynthesizeClient()
        
        # Check content length
        max_chars = 1000000
        if len(content) > max_chars:
            logging.warning(f"Content too long ({len(content)} chars). Truncating to {max_chars} characters.")
            content = content[:max_chars]
        
        logging.info(f"Starting long audio synthesis for {len(content)} characters (SSML: {use_ssml})")
        
        # Create unique output filename
        output_gcs_uri = f"gs://{gcs_bucket}/tts_output_{int(time.time())}.wav"
        
        # Create synthesis input (SSML or text)
        if use_ssml:
            # Wrap SSML in speak tags if not already wrapped
            if not content.strip().startswith('<speak>'):
                content = f'<speak>{content}</speak>'
            input_config = texttospeech_v1.SynthesisInput(ssml=content)
        else:
            input_config = texttospeech_v1.SynthesisInput(text=content)
        
        # Voice selection
        voice_config = texttospeech_v1.VoiceSelectionParams(
            language_code=language_code,
            name=voice_name
        )
        
        # Audio config
        audio_config = texttospeech_v1.AudioConfig(
            audio_encoding=texttospeech_v1.AudioEncoding.LINEAR16
        )
        
        # Create the request
        request = texttospeech_v1.SynthesizeLongAudioRequest(
            parent=f"projects/{project_id}/locations/global",
            input=input_config,
            voice=voice_config,
            audio_config=audio_config,
            output_gcs_uri=output_gcs_uri
        )
        
        # Start the operation
        logging.info(f"Submitting long audio synthesis request to GCS: {output_gcs_uri}")
        operation = client.synthesize_long_audio(request=request)
        
        logging.info("Waiting for long audio synthesis to complete...")
        response = operation.result(timeout=600)
        
        logging.info(f"Long audio synthesis completed. Output: {output_gcs_uri}")
        
        # Download the audio from GCS
        storage_client = storage.Client()
        bucket = storage_client.bucket(gcs_bucket)
        blob_name = output_gcs_uri.replace(f"gs://{gcs_bucket}/", "")
        blob = bucket.blob(blob_name)
        
        audio_bytes = blob.download_as_bytes()
        logging.info(f"Downloaded audio from GCS: {len(audio_bytes)} bytes")
        
        # Delete temporary file
        try:
            blob.delete()
            logging.info(f"Deleted temporary file from GCS: {blob_name}")
        except Exception as e:
            logging.warning(f"Could not delete temporary file from GCS: {e}")
        
        return {
            'status': 'success',
            'audio_content': audio_bytes,
            'gcs_uri': output_gcs_uri,
            'format': 'wav'
        }
        
    except Exception as e:
        logging.error(f"Error in long_audio_synthesis_ssml: {e}", exc_info=True)
        return {
            'status': 'error',
            'error': str(e)
        }

