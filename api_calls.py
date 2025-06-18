# api_calls.py

import streamlit as st
from PIL import Image
from io import BytesIO
from typing import Union, Tuple
import google.generativeai as genai
from google.api_core.exceptions import ResourceExhausted
from elevenlabs.client import ElevenLabs # Stellen Sie sicher, dass elevenlabs installiert ist
from elevenlabs import Voice, VoiceSettings

# Importiere die Prompt-Vorlagen aus der prompts.py Datei
from prompts import ACCESSIBILITY_PROMPT_TEMPLATE, SEO_PROMPT

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
            print(f"Rate limit exceeded for SEO tags {file_name_for_log}: {e}")
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
            print(f"Warning: Could not extract SEO tags for {file_name_for_log}. Raw response: {generated_text}")
            return None, None
            
    except Exception as e:
        print(f"Error during SEO tag generation for {file_name_for_log}: {e}")
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
            print(f"Rate limit exceeded for accessibility description {file_name_for_log}: {e}")
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
            print(f"Error parsing short/long description for {file_name_for_log}: {e}. Raw Text: {generated_text}")
            return None, None
            
        return short_desc, long_desc
            
    except Exception as e:
        print(f"Error during accessibility description generation for {file_name_for_log}: {e}")
        st.error(f"Ein unerwarteter Fehler ist bei der Generierung der Barrierefreiheits-Beschreibung für '{file_name_for_log}' aufgetreten.")
        return None, None

@st.cache_data
def generate_audio_from_text(text: str, api_key: str) -> Union[bytes, None]:
    """
    Generiert Audio aus Text mit der ElevenLabs API und gibt die Audio-Bytes zurück.
    Angepasst für die ElevenLabs Python Bibliothek Version 1.x.x
    """
    if not text or not api_key:
        st.warning("Kein Text oder API-Schlüssel für die Audio-Generierung vorhanden.")
        return None
    
    try:
        client = ElevenLabs(api_key=api_key)
        
        # === ÄNDERUNG HIER: ANPASSUNG AN NEUE ELEVENLABS API (v1.x.x) ===
        # Die Methode ist jetzt client.text_to_speech.convert()
        # Voice-ID 'Rachel' (UUID) und Modell werden direkt übergeben.
        
        # Wähle eine Standardstimme (Voice ID für "Rachel" ist eine gängige Wahl)
        # Eine Liste deiner verfügbaren Voice IDs findest du in deinem ElevenLabs Konto
        # oder über client.voices.get_all()
        selected_voice_id = '21m00Tcm4NF8gDrvPhhE' # Beispiel Voice ID für eine Standardstimme (Rachel)

        audio_bytes = client.text_to_speech.convert(
            voice_id=selected_voice_id,
            text=text,
            model_id="eleven_multilingual_v2", # Modell-ID als Parameter
            # Optional: voice_settings können hier auch als Dictionary übergeben werden,
            # wenn du spezifische Einstellungen für Stabilität/Ähnlichkeit möchtest:
            # voice_settings=VoiceSettings(stability=0.71, similarity_boost=0.5)
        )
        # === ENDE ÄNDERUNG ===
        
        # Überprüfen, ob Bytes zurückgegeben wurden
        if isinstance(audio_bytes, bytes) and len(audio_bytes) > 0:
            return audio_bytes
        else:
            st.error("ElevenLabs API hat keine validen Audio-Daten zurückgegeben.")
            return None

    except Exception as e:
        print(f"Error calling ElevenLabs API: {e}")
        st.error(f"Fehler bei der Audio-Generierung durch ElevenLabs: {e}. Prüfe API-Key und Textlänge.")
        return None