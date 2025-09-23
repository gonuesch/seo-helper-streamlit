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
import vertexai
from vertexai.generative_models import GenerativeModel, Part
from google.cloud import firestore
import os
import base64
from google.cloud import aiplatform
from google.protobuf import json_format
from google.protobuf.struct_pb2 import Value

# Importiere die Prompt-Vorlagen aus der prompts.py Datei
from prompts import ACCESSIBILITY_PROMPT_TEMPLATE, SEO_PROMPT, SUMMARY_PROMPT, GUIDELINE_PROMPT_WITH_MATCHING, SSML_PROMPT, TRANSLATION_GUIDE_PROMPT, TRANSLATE_CHUNK_PROMPT
from utils import log_exceptions

# Richte ein einfaches Logging ein, um Fehler besser nachverfolgen zu können
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Gemini-Modell für die neuen Funktionen
model_gemini = genai.GenerativeModel('gemini-2.5-pro')

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
def generate_seo_tags_cached(image_source: Union[bytes, str], file_name_for_log: str, gemini_api_key: str = None, model_name: str = "gemini-1.5-pro-latest") -> Tuple[Union[str, None], Union[str, None]]:
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
def generate_accessibility_description_cached(image_bytes_for_api, file_name_for_log: str, ebook_context: str = "", gemini_api_key: str = None, model_name: str = "gemini-1.5-pro-latest") -> Tuple[Union[str, None], Union[str, None]]:
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
        model_for_caching = GenerativeModel("gemini-2.5-pro") # Updated from 1.5-pro-001
        
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
    Ruft die verfügbaren Google TTS Stimmen über Vertex AI ab.
    Gibt ein Dictionary zurück:
    {'Stimmenname': {'voice_id': 'xyz', 'language': 'en-US', 'gender': 'MALE/FEMALE'}}
    """
    try:
        vertexai.init(project="avid-infinity-458913-p3")
        model = GenerativeModel("text-to-speech")
        
        # NOTE: Vertex AI does not have a simple 'list_voices' API like the classic TTS API.
        # The models are the "voices". We will use a predefined list of high-quality voices
        # known to be available through the Vertex AI text-to-speech model.
        
        # Predefined list of high-quality, known voices for Vertex AI TTS
        known_voices = {
            "en-US-Studio-O": {"gender": "FEMALE"},
            "en-US-Studio-M": {"gender": "MALE"},
            "en-US-Wavenet-D": {"gender": "MALE"},
            "en-US-Wavenet-F": {"gender": "FEMALE"},
            "en-GB-Wavenet-A": {"gender": "FEMALE"},
            "en-GB-Wavenet-B": {"gender": "MALE"},
            "en-AU-Wavenet-C": {"gender": "FEMALE"},
            "en-AU-Wavenet-D": {"gender": "MALE"},
        }

        voice_dict = {}
        for voice_id, details in known_voices.items():
            language_code = "-".join(voice_id.split("-")[:2])
            voice_name = f"{voice_id} ({language_code})"
            voice_dict[voice_name] = {
                "voice_id": voice_id,
                "language": language_code,
                "gender": details["gender"]
            }
        return voice_dict
        
    except Exception as e:
        logger.error(f"Fehler beim Abrufen der Vertex AI TTS Stimmen: {e}")
        return {
            "en-US-Wavenet-D (en-US)": {"voice_id": "en-US-Wavenet-D", "language": "en-US", "gender": "MALE"},
            "en-US-Wavenet-F (en-US)": {"voice_id": "en-US-Wavenet-F", "language": "en-US", "gender": "FEMALE"}
        }

@log_exceptions
def generate_audio_google_tts(ssml: str, voice_id: str, language_code: str) -> bytes:
    """
    Generiert Audio mit der Vertex AI Text-to-Speech API über den Prediction Service Endpoint.
    
    Args:
        ssml: Der zu synthetisierende SSML-formatierte Text
        voice_id: Die Voice-ID (z.B. 'en-US-Wavenet-D')
        language_code: Der BCP-47 Sprachcode (z.B. 'en-US')
    
    Returns:
        bytes: Audio-Daten im MP3-Format
    """
    try:
        project_id = "avid-infinity-458913-p3"
        # Hardcode the location to us-central1 where the model is available
        location = "us-central1"
        api_endpoint = f"{location}-aiplatform.googleapis.com"
        
        # 1. Client initialisieren
        client_options = {"api_endpoint": api_endpoint}
        client = aiplatform.gapic.PredictionServiceClient(client_options=client_options)

        # 2. SSML-Payload (Instanz) erstellen
        instance_dict = {
            "input": {"ssml": f"<speak>{ssml}</speak>"},
            "voice": {"languageCode": language_code, "name": voice_id},
            "audioConfig": {"audioEncoding": "MP3"},
        }
        instance = json_format.ParseDict(instance_dict, Value())
        instances = [instance]

        # 3. Den Endpunkt des Modells definieren
        # Dies ist der feste Pfad zum vortrainierten TTS-Modell auf Vertex AI.
        endpoint = (
            f"projects/{project_id}/locations/{location}"
            "/publishers/google/models/texttospeech-1"
        )

        # 4. Die Anfrage an den Endpunkt senden
        try:
            response = client.predict(endpoint=endpoint, instances=instances)
        except Exception as e:
            logger.error(f"Fehler bei der Vertex AI TTS Audio-Generierung: {e}")
            return None
        
        # 5. Die Antwort verarbeiten
        audio_content_base64 = response.predictions[0]["audioContent"]
        audio_content_bytes = base64.b64decode(audio_content_base64)
        
        return audio_content_bytes

    except Exception as e:
        logger.error(f"Fehler bei der Vertex AI TTS Audio-Generierung: {e}")
        return None
