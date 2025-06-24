# seo-helper-streamlit/api_calls.py

import streamlit as st
from PIL import Image
from io import BytesIO
from typing import Union, Tuple, Dict 
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted
from elevenlabs.client import ElevenLabs
import logging
import re

# Importiere die Prompt-Vorlagen aus der prompts.py Datei
from prompts import ACCESSIBILITY_PROMPT_TEMPLATE, SEO_PROMPT, SUMMARY_PROMPT, GUIDELINE_PROMPT_WITH_MATCHING, SSML_PROMPT

# Richte ein einfaches Logging ein, um Fehler besser nachverfolgen zu können
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Gemini-Modell für die neuen Funktionen
model_gemini = genai.GenerativeModel('gemini-2.5-pro')

# --- Die Funktionen generate_seo_tags_cached und generate_accessibility_description_cached bleiben unverändert ---

@st.cache_data(ttl=3600) # Cache das Ergebnis für eine Stunde
def generate_text_summary(_text: str) -> str:
    """Erstellt eine Zusammenfassung des übergebenen Textes."""
    try:
        full_prompt = SUMMARY_PROMPT + "\n\n--- ZU ZUSAMMENFASSENDER TEXT ---\n" + _text
        response = model_gemini.generate_content(full_prompt)
        return response.text
    except Exception as e:
        logger.error(f"Fehler bei der Text-Zusammenfassung: {e}", exc_info=True)
        return f"Fehler bei der Zusammenfassung: {e}"

@st.cache_data(ttl=3600)
def get_voice_recommendations(_summary: str, _voices_info: str) -> Tuple[str, list]:
    """Erstellt eine Regieleitlinie und extrahiert die Top 3 Stimmen."""
    try:
        full_prompt = GUIDELINE_PROMPT_WITH_MATCHING.format(summary=_summary, voices_with_descriptions=_voices_info)
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
        
        return guideline_text, recommendations
    except Exception as e:
        logger.error(f"Fehler bei der Regie-Erstellung: {e}", exc_info=True)
        return f"Fehler bei der Regie-Erstellung: {e}", []

@st.cache_data(ttl=3600)
def generate_ssml_chunk(_guideline: str, _text_chunk: str) -> str:
    """Reichert einen Text-Chunk mit SSML an."""
    try:
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
def generate_seo_tags_cached(image_bytes_for_api, file_name_for_log: str, model_name: str = "gemini-1.5-pro-latest") -> Tuple[Union[str, None], Union[str, None]]:
    """
    Nimmt Bild-Bytes, ruft die Gemini API mit dem SEO-Prompt auf
    und gibt (title, alt) als Tupel zurück.
    """
    try:
        img = Image.open(BytesIO(image_bytes_for_api))
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
            logger.warning(f"Warning: Could not extract SEO tags for {file_name_for_log}. Raw response: {generated_text}")
            return None, None
            
    except Exception as e:
        logger.error(f"Error during SEO tag generation for {file_name_for_log}: {e}", exc_info=True)
        st.error(f"Ein unerwarteter Fehler ist bei der Generierung der SEO-Tags für '{file_name_for_log}' aufgetreten.")
        return None, None

@st.cache_data
def generate_accessibility_description_cached(image_bytes_for_api, file_name_for_log: str, ebook_context: str = "", model_name: str = "gemini-1.5-pro-latest") -> Tuple[Union[str, None], Union[str, None]]:
    """
    Nimmt Bild-Bytes und Kontext, ruft die Gemini API mit dem Barrierefreiheits-Prompt auf
    und gibt (kurzbeschreibung, langbeschreibung) als Tupel zurück.
    """
    try:
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

@st.cache_data(ttl=3600)
def get_available_voices(api_key: str) -> Dict[str, Dict[str, str]]:
    """
    Ruft die verfügbaren Stimmen von der ElevenLabs API ab.
    Gibt ein Dictionary zurück: 
    {'Stimmenname': {'voice_id': 'xyz', 'preview_url': 'http://...'}}
    """
    try:
        client = ElevenLabs(api_key=api_key, timeout=60.0)
        voices = client.voices.get_all()
        # Erstelle ein verschachteltes Dictionary mit allen relevanten Infos
        return {
            voice.name: {
                "voice_id": voice.voice_id,
                "preview_url": voice.preview_url
            }
            for voice in voices.voices if voice.preview_url
        }
    except Exception as e:
        logger.error(f"Fehler beim Abrufen der ElevenLabs-Stimmen: {e}", exc_info=True)
        return {"Fehler": {"voice_id": "", "preview_url": ""}}


@st.cache_data
def generate_audio_from_text(text: str, api_key: str, voice_id: str) -> Union[bytes, None]:
    """
    Generiert Audio aus Text mit der ElevenLabs API und gibt die Audio-Bytes zurück.
    Akzeptiert jetzt eine dynamische voice_id.
    """
    if not all([text, text.strip(), api_key, voice_id]):
        logger.warning("Kein Text, API-Schlüssel oder Voice-ID für die Audio-Generierung vorhanden.")
        return None
    
    try:
        # HIER DEN TIMEOUT HINZUFÜGEN
        client = ElevenLabs(api_key=api_key, timeout=300.0) # Timeout auf 300s (5 Minuten) setzen
        
        audio_generator = client.text_to_speech.convert(
            voice_id=voice_id,
            text=text,
            model_id="eleven_multilingual_v2", 
        )

        logger.info(f"Sammle Audio-Chunks von der ElevenLabs API für Stimme {voice_id}...")
        audio_chunks = [chunk for chunk in audio_generator]

        if not audio_chunks:
            logger.error("ElevenLabs API hat keine Audio-Daten zurückgegeben.")
            return None

        full_audio_bytes = b"".join(audio_chunks)

        if full_audio_bytes:
            logger.info("Audio-Bytes erfolgreich zusammengefügt.")
            return full_audio_bytes
        else:
            logger.error("Zusammenfügen der Audio-Chunks ergab keine Daten.")
            return None

    except Exception as e:
        logger.error(f"Fehler bei der Audio-Generierung durch ElevenLabs: {e}", exc_info=True)
        return None
