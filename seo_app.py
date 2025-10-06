# seo_app.py - Finale, bereinigte Version für IAP-Authentifizierung

import asyncio

# Behebt den "RuntimeError: no running event loop" in bestimmten Umgebungen
try:
    loop = asyncio.get_running_loop()
except RuntimeError:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

import streamlit as st
from pathlib import Path
import pandas as pd
from io import BytesIO
import json
import streamlit.components.v1 as components
from streamlit_option_menu import option_menu
import logging
import google.cloud.pubsub_v1 as pubsub_v1
import uuid
import time
import datetime
from google.cloud import storage, firestore, pubsub_v1
from google.cloud import texttospeech
import random
from typing import Tuple, Dict
import re
import requests
import os
import asyncio

# Richte ein einfaches Logging ein
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Importiere Funktionen aus deinen Modulen
from utils import convert_tiff_to_png_bytes, read_text_from_docx, read_text_from_pdf, chunk_text, chunk_text_by_paragraphs, log_exceptions, upload_to_gcs, download_from_gcs
from api_calls import (
    generate_seo_tags_cached, 
    generate_accessibility_description_cached,
    simple_text_to_speech,
    get_simple_voices,
    detect_language,
    get_voices_for_language,
    smart_text_to_speech,
    long_audio_synthesis,
    text_to_speech_with_ssml
    # Commented out complex TTS functions
    # generate_text_summary,
    # generate_ssml_chunk,
    # get_google_tts_voices,
    # get_voice_recommendations,
    # generate_long_audio_gcs
)

# Importiere die Manuskript-Agents
from manuscript_agents import (
    ManuscriptAnalyzerAgent,
    TargetAudienceAgent, 
    MarketingStrategyAgent,
    ManuscriptWorkflowAgent
)

# --- SICHERHEITSKONFIGURATION FÜR TTS ---
MAX_TTS_COST_USD = 10.0  # Maximal 10 USD pro TTS-Job (erhöht von 5.0)
MAX_TTS_RUNTIME_MINUTES = 30  # Maximal 30 Minuten Laufzeit
TTS_STATUS_CHECK_INTERVAL = 2  # Status alle 2 Sekunden prüfen
MAX_TTS_RETRIES = 3  # Maximal 3 Wiederholungen bei Fehlern

# Google TTS Preise (pro 1 Million Zeichen)
GOOGLE_TTS_PRICE_PER_1M_CHARS = 4.0  # $4 pro 1 Million Zeichen

# Berechnung der maximalen Seitenanzahl
# Annahme: 250 Wörter/Seite × 5 Zeichen/Wort = 1250 Zeichen/Seite
# SSML-Expansion: +25% = 1562.5 Zeichen/Seite
# $10 ÷ $0.18 × 1000 Zeichen = 55.556 Zeichen
# 55.556 ÷ 1562.5 = ~35.5 Seiten
MAX_PAGES_FOR_TTS = 35  # Maximale Seitenanzahl für TTS

# API Limit für Long Audio Synthesis (in Bytes)
# Wir setzen ein konservatives Limit für den reinen Text, um SSML-Expansion zu berücksichtigen
LONG_AUDIO_API_LIMIT_BYTES = 1_000_000
SSML_EXPANSION_FACTOR = 1.25 # Annahme: 25% Längenzunahme durch SSML
SAFE_CHAR_LIMIT_FOR_TTS = int(LONG_AUDIO_API_LIMIT_BYTES / SSML_EXPANSION_FACTOR)

def calculate_tts_cost(text_length_chars):
    """Berechnet die Kosten für Google TTS basierend auf Textlänge."""
    return (text_length_chars / 1000000) * GOOGLE_TTS_PRICE_PER_1M_CHARS

def estimate_total_tts_cost(text_content):
    """Schätzt die Gesamtkosten für einen TTS-Job."""
    if not text_content:
        return 0.0
    
    # Schätze SSML-Expansion (SSML ist meist 20-30% länger als Originaltext)
    estimated_ssml_length = len(text_content) * 1.25
    return calculate_tts_cost(estimated_ssml_length)

def estimate_page_count(text_content):
    """Schätzt die Seitenanzahl basierend auf Textlänge."""
    if not text_content:
        return 0
    
    # Annahme: 250 Wörter/Seite × 5 Zeichen/Wort = 1250 Zeichen/Seite
    chars_per_page = 1250
    return max(1, len(text_content) // chars_per_page)

def check_tts_safety(start_time, current_cost=0.0, chunks_processed=0, total_chunks=0):
    """
    Prüft alle Sicherheitsbedingungen für den TTS-Job.
    Gibt True zurück wenn Job sicher weiterlaufen kann, False wenn gestoppt werden muss.
    """
    try:
        # 1. Zeit-Limit prüfen
        runtime_minutes = (datetime.datetime.utcnow() - start_time).total_seconds() / 60
        if runtime_minutes > MAX_TTS_RUNTIME_MINUTES:
            st.error(f"🚨 SICHERHEIT: TTS-Job läuft seit {runtime_minutes:.1f} Minuten. Maximal {MAX_TTS_RUNTIME_MINUTES} Minuten erlaubt.")
            return False
        
        # 2. Kosten-Limit prüfen
        if current_cost > MAX_TTS_COST_USD:
            st.error(f" SICHERHEIT: Kosten von ${current_cost:.2f} überschreiten Limit von ${MAX_TTS_COST_USD}")
            return False
        
        # 3. Kill Switch prüfen (aus Session State)
        if st.session_state.get("tts_kill_switch", False):
            st.error(" KILL SWITCH: TTS-Job wurde manuell gestoppt")
            return False
        
        return True
        
    except Exception as e:
        st.error(f"⚠️ Fehler bei TTS-Sicherheitsprüfung: {e}")
        return False

# Google Cloud Credentials Setup
def get_google_credentials():
    """Lädt Google Cloud Credentials aus dem Secret Manager."""
    try:
        from google.cloud import secretmanager
        from google.oauth2 import service_account
        import json
        
        # Hole die komplette Service Account JSON aus dem Secret Manager
        client = secretmanager.SecretManagerServiceClient()
        project_id = "avid-infinity-458913-p3"
        secret_name = "google-tts-service-account"  # Updated to match correct service account
        name = f"projects/{project_id}/secrets/{secret_name}/versions/latest"
        response = client.access_secret_version(request={"name": name})
        service_account_json = response.payload.data.decode("UTF-8")
        
        # Parse die JSON-Datei
        service_account_info = json.loads(service_account_json)
        
        # Erstelle Credentials-Objekt direkt aus der JSON
        credentials = service_account.Credentials.from_service_account_info(service_account_info)
        
        logger.info("✅ Google Cloud Credentials aus Secret Manager geladen")
        return credentials
    except Exception as e:
        logger.warning(f"⚠️ Fehler beim Laden der Google Cloud Credentials: {e}")
        return None

# Entferne die problematische Umgebungsvariable
if 'GOOGLE_APPLICATION_CREDENTIALS' in os.environ:
    del os.environ['GOOGLE_APPLICATION_CREDENTIALS']
    logger.info("🗑️ GOOGLE_APPLICATION_CREDENTIALS Umgebungsvariable entfernt")

# Lade Credentials
# TTS credentials will be loaded when needed in TTS functions

# Richte den Google Cloud Pub/Sub Publisher ein
# Verwende immer Cloud Run Default Service Account für Pub/Sub
publisher = pubsub_v1.PublisherClient()
logger.info("✅ Pub/Sub Client mit Cloud Run Default Service Account initialisiert")

topic_path = publisher.topic_path("avid-infinity-458913-p3", "event-tracking-toolbox")

# Google Cloud Clients für asynchrone Übersetzung initialisieren
PROJECT_ID = "avid-infinity-458913-p3"
BUCKET_NAME = "manuskripte-upload-avid-infinity"
FIRESTORE_DB_ID = "hbu-toolbox-firestone"
PUB_SUB_TOPIC = "start-translation"

# GCS Buckets für Text-to-Speech
GCS_TTS_OUTPUT_BUCKET = "tts-output-europe-west4-6899" # Bucket für MP3-Dateien

# Verwende immer Cloud Run Default Service Account für Storage und Firestore
storage_client = storage.Client(project=PROJECT_ID)
firestore_client = firestore.Client(project=PROJECT_ID, database=FIRESTORE_DB_ID)
logger.info("✅ Storage und Firestore Clients mit Cloud Run Default Service Account initialisiert")

# Pub/Sub Publisher für Translation Jobs
pubsub_publisher = publisher  # Verwende den bereits initialisierten Publisher
translation_topic_path = publisher.topic_path(PROJECT_ID, PUB_SUB_TOPIC)
logger.info("✅ Translation Pub/Sub Publisher und Topic Path initialisiert")


# Pub/Sub Event Tracking Funktion
def send_event_to_pubsub(event_data):
    """Sendet ein Event an Google Cloud Pub/Sub."""
    try:
        # Konvertiere das Wörterbuch in einen JSON-String und dann in Bytes
        message_json = json.dumps(event_data)
        message_bytes = message_json.encode('utf-8')
        
        # Sende die Nachricht an Pub/Sub
        publish_future = publisher.publish(topic_path, data=message_bytes)
        publish_future.result()  # Wartet auf das Ergebnis (optional)
    except Exception as e:
        st.error(f"Fehler beim Senden des Tracking-Events: {e}")
        logging.error(f"Pub/Sub Fehler: {e}")



# State Management Callback Functions
def set_button_clicked_true(state_key):
    """Callback function that sets a button click state to True."""
    st.session_state[state_key] = True

# Button click tracking for logging
def get_button_click_id():
    """Generates a unique click ID for tracking button clicks."""
    # Ensure click_counter is initialized
    if 'click_counter' not in st.session_state:
        st.session_state.click_counter = 0
    st.session_state.click_counter += 1
    return f"click_{st.session_state.click_counter}_{int(time.time())}"

def start_translation_job(uploaded_file):
    """Startet einen asynchronen Übersetzungsauftrag."""
    if not uploaded_file:
        st.warning("Bitte zuerst eine Datei auswählen.")
        return

    job_id = str(uuid.uuid4())
    gcs_file_name = f"{job_id}-{uploaded_file.name}"

    try:
        # 1. Datei in Cloud Storage hochladen
        bucket = storage_client.bucket(BUCKET_NAME)
        blob = bucket.blob(gcs_file_name)
        blob.upload_from_file(uploaded_file, content_type=uploaded_file.type)
        gcs_path = f"gs://{BUCKET_NAME}/{gcs_file_name}"

        # 2. Job-Eintrag in Firestore erstellen
        job_ref = firestore_client.collection("translation_jobs").document(job_id)
        job_ref.set({
            "status": "pending",
            "source_gcs_path": gcs_path,
            "user_email": st.session_state.get("email", "unknown"),  # Nutzt E-Mail aus dem session_state
            "created_at": datetime.datetime.utcnow(),
            "file_name": uploaded_file.name
        })

        # 3. Nachricht in Pub/Sub veröffentlichen (startet die Analyse)
        message_data = json.dumps({"job_id": job_id}).encode('utf-8')
        future = pubsub_publisher.publish(translation_topic_path, data=message_data)
        future.result()  # Stellt sicher, dass die Nachricht gesendet wurde

        st.success(f"Übersetzungsauftrag '{uploaded_file.name}' wurde gestartet! Job-ID: {job_id}")
        
        # Store job info in session state for tracking
        st.session_state.translation_job_id = job_id
        st.session_state.translation_job_status = "pending"

    except Exception as e:
        st.error(f"Ein Fehler ist aufgetreten: {e}")
        logging.error(f"Translation job error: {e}")

def refresh_translation_status():
    """Aktualisiert den Status eines Übersetzungsauftrags und lädt bei Bedarf den Style-Guide herunter."""
    job_id = st.session_state.get("translation_job_id")
    if not job_id:
        st.warning("Kein aktiver Job gefunden.")
        return

    try:
        # Job-Status aus Firestore abrufen
        job_ref = firestore_client.collection("translation_jobs").document(job_id)
        job_doc = job_ref.get()
        
        if not job_doc.exists:
            st.warning("Job nicht gefunden")
            return
        
        job_data = job_doc.to_dict()
        job_status = job_data.get("status", "unknown")
        
        # Status im Session State aktualisieren
        st.session_state.translation_job_status = job_status
        
        # Kosten- und Token-Informationen aus Firestore lesen
        st.session_state.job_cost = job_data.get("estimated_cost_usd")
        st.session_state.input_tokens = job_data.get("input_tokens")
        st.session_state.output_tokens = job_data.get("output_tokens")
        
        # Neue Felder für Übersetzung
        st.session_state.cached_content_name = job_data.get("cached_content_name")
        st.session_state.translation_cost_usd = job_data.get("translation_cost_usd")
        st.session_state.input_tokens_translation = job_data.get("input_tokens_translation")
        st.session_state.output_tokens_translation = job_data.get("output_tokens_translation")
        st.session_state.final_gcs_path = job_data.get("final_gcs_path")

        # Wenn der Status "analyzed" ist, Style-Guide herunterladen
        if job_status == "analyzed":
            style_guide_gcs_path = job_data.get("style_guide_gcs_path")
            if style_guide_gcs_path:
                try:
                    # GCS-Pfad parsen (Format: gs://bucket-name/path/to/file)
                    if style_guide_gcs_path.startswith("gs://"):
                        path_parts = style_guide_gcs_path[5:].split("/", 1)
                        if len(path_parts) == 2:
                            bucket_name = path_parts[0]
                            blob_path = path_parts[1]
                            
                            # Style-Guide aus Cloud Storage herunterladen
                            bucket = storage_client.bucket(bucket_name)
                            blob = bucket.blob(blob_path)
                            style_guide_content = blob.download_as_text()
                            
                            # JSON parsen und im Session State speichern
                            parsed_style_guide = json.loads(style_guide_content)
                            st.session_state.current_style_guide = parsed_style_guide
                            st.session_state.editable_style_guide = parsed_style_guide.copy()  # Kopie für Bearbeitung
                            
                            st.success(f"Status aktualisiert: {job_status} - Style-Guide erfolgreich heruntergeladen!")
                            logging.info(f"Style guide downloaded successfully for job {job_id}")
                        else:
                            st.error("Ungültiger GCS-Pfad für Style-Guide")
                            logging.error(f"Invalid GCS path format: {style_guide_gcs_path}")
                    else:
                        st.error("Ungültiger GCS-Pfad für Style-Guide")
                        logging.error(f"Invalid GCS path format: {style_guide_gcs_path}")
                except json.JSONDecodeError as e:
                    st.error(f"Fehler beim Parsen des Style-Guides (ungültiges JSON): {e}")
                    logging.error(f"JSON parsing error for style guide: {e}")
                except Exception as e:
                    st.error(f"Fehler beim Herunterladen des Style-Guides: {e}")
                    logging.error(f"Style guide download error: {e}")
            else:
                st.warning("Style-Guide-Pfad nicht in Job-Daten gefunden")
                logging.warning(f"Style guide path not found in job data for job {job_id}")
        else:
            st.success(f"Status aktualisiert: {job_status}")
            logging.info(f"Job status updated to {job_status} for job {job_id}")
        
    except Exception as e:
        st.error(f"Fehler beim Abrufen des Status: {e}")
        logging.error(f"Translation status refresh error: {e}")

def save_edited_style_guide():
    """Speichert die bearbeiteten Style-Guide-Änderungen zurück in Cloud Storage."""
    job_id = st.session_state.get("translation_job_id")
    if not job_id:
        st.error("Kein aktiver Job gefunden.")
        return

    try:
        # Hole die bearbeiteten Werte direkt aus den Widget-Keys
        edited_genre_audience = st.session_state.get("edited_genre_audience", "")
        edited_tone_mood = st.session_state.get("edited_tone_mood", "")
        edited_narrative_perspective = st.session_state.get("edited_narrative_perspective", "")
        edited_character_names = st.session_state.get("edited_character_names", "")
        edited_key_concepts = st.session_state.get("edited_key_concepts", "")
        edited_stylistic_features = st.session_state.get("edited_stylistic_features", "")
        edited_key_terms_df = st.session_state.get("edited_key_terms_data", pd.DataFrame())
        
        # Konvertiere DataFrame zu Dictionary
        edited_key_terms = {}
        if not edited_key_terms_df.empty:
            for _, row in edited_key_terms_df.iterrows():
                if pd.notna(row["Deutscher Begriff"]) and pd.notna(row["Englische Übersetzung"]):
                    edited_key_terms[row["Deutscher Begriff"]] = row["Englische Übersetzung"]
        
        # Baue das Style-Guide-Dictionary neu zusammen
        updated_style_guide = {
            "style_guide": {
                "genre_audience": edited_genre_audience,
                "tone_mood": edited_tone_mood,
                "narrative_perspective": edited_narrative_perspective,
                "character_names": edited_character_names,
                "key_concepts": edited_key_concepts,
                "stylistic_features": edited_stylistic_features
            },
            "key_terms": edited_key_terms
        }
        
        # Konvertiere zu JSON-String
        style_guide_json = json.dumps(updated_style_guide, indent=2, ensure_ascii=False)
        
        # Hole den ursprünglichen GCS-Pfad aus Firestore
        job_ref = firestore_client.collection("translation_jobs").document(job_id)
        job_doc = job_ref.get()
        
        if not job_doc.exists:
            st.error("Job nicht gefunden")
            return
        
        job_data = job_ref.to_dict()
        style_guide_gcs_path = job_data.get("style_guide_gcs_path")
        
        if not style_guide_gcs_path:
            st.error("Style-Guide-Pfad nicht gefunden")
            return
        
        # Parse GCS-Pfad
        if style_guide_gcs_path.startswith("gs://"):
            path_parts = style_guide_gcs_path[5:].split("/", 1)
            if len(path_parts) == 2:
                bucket_name = path_parts[0]
                blob_path = path_parts[1]
                
                # Überschreibe die Datei in Cloud Storage
                bucket = storage_client.bucket(bucket_name)
                blob = bucket.blob(blob_path)
                blob.upload_from_string(style_guide_json, content_type='application/json')
                
                # Aktualisiere den Job-Status in Firestore
                job_ref.update({
                    "status": "guide_approved",
                    "updated_at": datetime.datetime.utcnow()
                })
                
                # Aktualisiere Session State
                st.session_state.current_style_guide = updated_style_guide
                st.session_state.editable_style_guide = updated_style_guide.copy()
                st.session_state.translation_job_status = "guide_approved"
                
                st.success("✅ Style-Guide erfolgreich aktualisiert und freigegeben!")
                logging.info(f"Style guide updated and approved for job {job_id}")
                
            else:
                st.error("Ungültiger GCS-Pfad")
        else:
            st.error("Ungültiger GCS-Pfad")
            
    except Exception as e:
        st.error(f"Fehler beim Speichern des Style-Guides: {e}")
        logging.error(f"Style guide save error: {e}")

def auto_refresh_translation_status():
    """Automatische Status-Aktualisierung alle 30 Sekunden für aktive Übersetzungsaufträge."""
    if st.session_state.get("translation_job_id") and st.session_state.get("translation_job_status"):
        # Bei allen Jobs automatisch aktualisieren (auch bei completed/failed)
        try:
            # Job-Status aus Firestore abrufen
            job_ref = firestore_client.collection("translation_jobs").document(st.session_state.translation_job_id)
            job_doc = job_ref.get()
            
            if job_doc.exists:
                job_data = job_doc.to_dict()
                new_status = job_data.get("status", "unknown")
                
                # Nur aktualisieren, wenn sich der Status geändert hat
                if new_status != st.session_state.translation_job_status:
                    st.session_state.translation_job_status = new_status
                    
                    # Aktualisiere alle relevanten Session State Werte
                    st.session_state.job_cost = job_data.get("estimated_cost_usd")
                    st.session_state.input_tokens = job_data.get("input_tokens")
                    st.session_state.output_tokens = job_data.get("output_tokens")
                    st.session_state.translation_cost_usd = job_data.get("translation_cost_usd")
                    st.session_state.input_tokens_translation = job_data.get("input_tokens_translation")
                    st.session_state.output_tokens_translation = job_data.get("output_tokens_translation")
                    st.session_state.final_gcs_path = job_data.get("final_gcs_path")
                    
                    # Wenn der Status "analyzed" ist, Style-Guide herunterladen
                    if new_status == "analyzed":
                        style_guide_gcs_path = job_data.get("style_guide_gcs_path")
                        if style_guide_gcs_path:
                            try:
                                # GCS-Pfad parsen und Style-Guide herunterladen
                                if style_guide_gcs_path.startswith("gs://"):
                                    path_parts = style_guide_gcs_path[5:].split("/", 1)
                                    if len(path_parts) == 2:
                                        bucket_name = path_parts[0]
                                        blob_path = path_parts[1]
                                        
                                        bucket = storage_client.bucket(bucket_name)
                                        blob = bucket.blob(blob_path)
                                        
                                        # Prüfe Dateigröße
                                        blob.reload()
                                        if blob.size == 0:
                                            st.warning("⚠️ Style-Guide ist leer (0 Bytes). Übersetzung kann nicht gestartet werden.")
                                            logging.warning(f"Empty style guide file for job {st.session_state.translation_job_id}")
                                            # Style-Guide nicht laden, aber Status-Update fortsetzen
                                        else:
                                            style_guide_content = blob.download_as_text()
                                            
                                            # Prüfe ob der Inhalt leer ist
                                            if not style_guide_content or not style_guide_content.strip():
                                                st.warning("⚠️ Style-Guide ist leer. Übersetzung kann nicht gestartet werden.")
                                                logging.warning(f"Empty style guide content for job {st.session_state.translation_job_id}")
                                                # Style-Guide nicht laden, aber Status-Update fortsetzen
                                            else:
                                                # Prüfe ob es gültiges JSON ist
                                                try:
                                                    parsed_style_guide = json.loads(style_guide_content)
                                                    
                                                    # Prüfe ob der Style-Guide die erwartete Struktur hat
                                                    if not isinstance(parsed_style_guide, dict) or 'style_guide' not in parsed_style_guide:
                                                        st.warning("⚠️ Style-Guide hat ungültige Struktur. Übersetzung kann nicht gestartet werden.")
                                                        logging.warning(f"Invalid style guide structure for job {st.session_state.translation_job_id}")
                                                        # Style-Guide nicht laden, aber Status-Update fortsetzen
                                                    else:
                                                        st.session_state.current_style_guide = parsed_style_guide
                                                        st.session_state.editable_style_guide = parsed_style_guide.copy()
                                                        
                                                        st.success("✅ Style-Guide erfolgreich geladen!")
                                                        logging.info(f"Style guide auto-downloaded for job {st.session_state.translation_job_id}")
                                                        
                                                except json.JSONDecodeError as json_error:
                                                    st.error(f"❌ Style-Guide enthält ungültiges JSON: {json_error}")
                                                    st.info("💡 Der Style-Guide wird neu generiert...")
                                                    logging.error(f"Invalid JSON in style guide for job {st.session_state.translation_job_id}: {json_error}")
                                                    
                                                    # Style-Guide nicht laden, aber Status-Update fortsetzen
                                            
                            except Exception as e:
                                st.error(f"❌ Fehler beim Laden des Style-Guides: {e}")
                                logging.error(f"Style guide download error via status update: {e}")
                                # Fehler beim Laden, aber Status-Update fortsetzen
                    
                    logging.info(f"Auto-status update: {st.session_state.translation_job_status} -> {new_status}")
                    
                    # Rerun nur bei Status-Änderungen
                    st.rerun()
                    
        except Exception as e:
            logging.error(f"Auto-refresh error: {e}")

def get_time_estimate(status, file_size_mb=None):
    """Gibt eine Zeitabschätzung für den aktuellen Status zurück."""
    if status == "pending":
        return "⏱️ **Geschätzte Dauer:** 2-5 Minuten"
    elif status == "analyzing":
        if file_size_mb:
            if file_size_mb < 1:
                return "⏱️ **Geschätzte Dauer:** 3-7 Minuten"
            elif file_size_mb < 5:
                return "⏱️ **Geschätzte Dauer:** 5-12 Minuten"
            else:
                return "⏱️ **Geschätzte Dauer:** 8-20 Minuten"
        return "⏱️ **Geschätzte Dauer:** 5-15 Minuten"
    elif status == "translation_queued":
        return "⏱️ **Geschätzte Dauer:** 1-3 Minuten (Warteschlange)"
    elif status == "translating":
        if file_size_mb:
            if file_size_mb < 1:
                return "⏱️ **Geschätzte Dauer:** 10-25 Minuten"
            elif file_size_mb < 5:
                return "⏱️ **Geschätzte Dauer:** 20-45 Minuten"
            else:
                return "⏱️ **Geschätzte Dauer:** 35-80 Minuten"
        return "⏱️ **Geschätzte Dauer:** 20-60 Minuten"
    else:
        return ""

def trigger_translation_runner(job_id):
    """Sendet eine Nachricht an das 'run-translation' Pub/Sub-Thema."""
    try:
        # Job-Status in Firestore aktualisieren
        firestore_client.collection("translation_jobs").document(job_id).update({"status": "translation_queued"})

        # Nachricht an Pub/Sub senden (startet die Übersetzung)
        topic_path = pubsub_publisher.topic_path(PROJECT_ID, "run-translation")
        message_data = json.dumps({"job_id": job_id}).encode('utf-8')
        future = pubsub_publisher.publish(topic_path, data=message_data)
        future.result()

        st.success("Der Übersetzungs-Job wurde erfolgreich an die Pipeline übergeben!")
        # Optional: Status in der App direkt aktualisieren
        st.session_state.translation_job_status = "translation_queued"

    except Exception as e:
        st.error(f"Fehler beim Starten des Übersetzungs-Jobs: {e}")
        logging.error(f"Translation runner trigger error: {e}")

# Comprehensive Processing Functions
def run_seo_processing_and_logging(files_to_process):
    """Comprehensive SEO processing function that handles everything in one place."""
    # Generate unique click ID for this button click
    click_id = get_button_click_id()
    
    # Store results in session state instead of displaying immediately
    results = []
    
    with st.spinner("Verarbeite SEO Tags..."):
        for i, uploaded_file in enumerate(files_to_process):
            file_name = uploaded_file.name
            safe_file_name_part = "".join(c if c.isalnum() else "_" for c in file_name)
            base_id = f"seo_file_{i}_{safe_file_name_part}"
            try:
                original_image_bytes = uploaded_file.getvalue()
                
                logging.info("Generiere SEO Tags für Datei: %s", file_name)
                title, alt = generate_seo_tags_cached(original_image_bytes, file_name, gemini_api_key)
                
                if title and alt:
                    logging.info("SEO Tags erfolgreich generiert für: %s", file_name)
                    results.append({
                        "file_name": file_name,
                        "title": title,
                        "alt": alt,
                        "image_bytes": original_image_bytes,
                        "base_id": base_id,
                        "status": "success"
                    })
                else:
                    logging.error("SEO Tag-Generierung fehlgeschlagen für: %s", file_name)
                    results.append({
                        "file_name": file_name,
                        "error": f"❌ Fehler bei SEO Tag-Generierung für '{file_name}'.",
                        "status": "failed"
                    })
            except Exception as e:
                logging.error("Unerwarteter Fehler bei SEO Tag-Generierung für %s: %s", file_name, str(e))
                results.append({
                    "file_name": file_name,
                    "error": f"🚨 Unerwarteter FEHLER bei '{file_name}': {e}",
                    "status": "error",
                    "error_message": str(e)
                })
    
    # Store results and click ID in session state
    st.session_state.seo_results = results
    st.session_state.seo_click_id = click_id
    
    st.success("SEO-Verarbeitung abgeschlossen.")

def run_seo_url_processing_and_logging(image_url):
    """Comprehensive SEO URL processing function that handles everything in one place."""
    # Generate unique click ID for this button click
    click_id = get_button_click_id()
    
    with st.spinner(f"Verarbeite Bild von URL..."):
        try:
            title, alt = generate_seo_tags_cached(image_url, image_url, gemini_api_key)
            
            if title and alt:
                st.session_state.seo_url_result = {
                    "title": title,
                    "alt": alt,
                    "image_url": image_url,
                    "status": "success"
                }
            else:
                st.session_state.seo_url_result = {
                    "error": "❌ Fehler bei SEO Tag-Generierung für die URL.",
                    "status": "failed"
                }
        except Exception as e:
            st.session_state.seo_url_result = {
                "error": f"🚨 Unerwarteter FEHLER bei der Verarbeitung der URL: {e}",
                "status": "error",
                "error_message": str(e)
            }
    
    # Store click ID for logging
    st.session_state.seo_url_click_id = click_id

def run_accessibility_processing_and_logging(files_to_process, context):
    """Comprehensive accessibility processing function that handles everything in one place."""
    # Generate unique click ID for this button click
    click_id = get_button_click_id()
    
    processed_count, failed_count = 0, 0
    results = []
    results_for_export = []
    
    with st.spinner("Verarbeite barrierefreie Beschreibungen..."):
        for i, uploaded_file in enumerate(files_to_process):
            file_name = uploaded_file.name
            safe_file_name_part = "".join(c if c.isalnum() else "_" for c in file_name)
            base_id = f"access_{i}_{safe_file_name_part}"
            try:
                original_image_bytes = uploaded_file.getvalue()
                image_bytes_for_api = original_image_bytes
                if Path(file_name).suffix.lower() in ['.tif', '.tiff']:
                    with st.spinner(f"Konvertiere {file_name} (TIFF) zu PNG..."):
                        try:
                            image_bytes_for_api = convert_tiff_to_png_bytes(original_image_bytes)
                        except Exception as conv_e:
                            st.error(f"🚨 Fehler beim Konvertieren von '{file_name}': {conv_e}")
                            failed_count += 1
                            results.append({
                                "file_name": file_name,
                                "error": f"🚨 Fehler beim Konvertieren von '{file_name}': {conv_e}",
                                "status": "conversion_error",
                                "error_message": str(conv_e)
                            })
                            continue
                
                    logging.info("Generiere barrierefreie Beschreibung für Datei: %s", file_name)
                    short_desc, long_desc = generate_accessibility_description_cached(image_bytes_for_api, file_name, context, gemini_api_key)
                    
                    if short_desc and long_desc:
                        logging.info("Barrierefreie Beschreibung erfolgreich generiert für: %s", file_name)
                        results.append({
                            "file_name": file_name,
                            "short_desc": short_desc,
                            "long_desc": long_desc,
                            "image_bytes": original_image_bytes,
                            "base_id": base_id,
                            "status": "success"
                        })
                        processed_count += 1
                        results_for_export.append({
                            "Bildname": file_name, "Dateiname Produktion": "", "Alternativtext": short_desc,
                            "Bildlegende": "", "Anmerkung": "", "Langbeschreibung": long_desc,
                            "(Platzierung/Größe/Übersetzungstexte in der Abbildung/...)": ""
                        })
                    else:
                        logging.error("Barrierefreie Beschreibung fehlgeschlagen für: %s", file_name)
                        results.append({
                            "file_name": file_name,
                            "error": f"❌ Fehler bei Erstellung der barrierefreien Beschreibung für '{file_name}'.",
                            "status": "failed"
                        })
                        failed_count += 1
            except Exception as e:
                logging.error("Unerwarteter Fehler bei barrierefreier Beschreibung für %s: %s", file_name, str(e))
                results.append({
                    "file_name": file_name,
                    "error": f"🚨 Unerwarteter FEHLER bei der Hauptverarbeitung von '{file_name}': {e}",
                    "status": "error",
                    "error_message": str(e)
                })
                failed_count += 1
    
    # Store results in session state
    st.session_state.accessibility_results = results
    st.session_state.accessibility_export_data = results_for_export
    st.session_state.accessibility_summary = {"processed_count": processed_count, "failed_count": failed_count}
    
    # Store click ID for logging
    st.session_state.accessibility_click_id = click_id
    
    st.success("Verarbeitung abgeschlossen.")

def run_tts_processing_and_logging():
    """Logs the successful TTS generation event."""
    # Generate unique click ID for this button click
    click_id = get_button_click_id()
    
    # Store click ID for logging
    st.session_state.tts_click_id = click_id
    
    # Send tracking event
    log_data = {
        "event_type": "text_to_speech_processed",
        "file_count": 1,
        "status": "success",
        "chunks_processed": len(st.session_state.get("tts_result", {}).get("chunks_processed", 0))
    }
    send_event_to_pubsub(log_data)



# Page config MUSS der erste Streamlit-Befehl sein
st.set_page_config(page_title="Toolbox", page_icon="app_icon.png", layout="wide")

# ==============================================================================
# HIER BEGINNT DIE ANWENDUNG
# Da IAP-Authentifizierung aktiviert ist, wird dieser Code nur von
# bereits authentifizierten und autorisierten Nutzern erreicht.
# ==============================================================================

# --- Session State Initialisierung ---
# Stellt sicher, dass alle benötigten Schlüssel im Session State existieren.

# Für SEO-Tool
if 'seo_button_clicked' not in st.session_state:
    st.session_state.seo_button_clicked = False
if 'seo_url_button_clicked' not in st.session_state:
    st.session_state.seo_url_button_clicked = False
if 'seo_results' not in st.session_state:
    st.session_state.seo_results = None
if 'seo_url_result' not in st.session_state:
    st.session_state.seo_url_result = None

# Für Barrierefreiheit-Tool
if 'accessibility_button_clicked' not in st.session_state:
    st.session_state.accessibility_button_clicked = False
if 'accessibility_results' not in st.session_state:
    st.session_state.accessibility_results = None
if 'accessibility_export_data' not in st.session_state:
    st.session_state.accessibility_export_data = None
if 'accessibility_summary' not in st.session_state:
    st.session_state.accessibility_summary = None

# Für Text-to-Speech-Tool
if 'tts_button_clicked' not in st.session_state:
    st.session_state.tts_button_clicked = False
if 'tts_step' not in st.session_state:
    st.session_state.tts_step = 1
if 'guideline' not in st.session_state:
    st.session_state.guideline = None
if 'top_3_voices' not in st.session_state:
    st.session_state.top_3_voices = []
if 'text_content' not in st.session_state:
    st.session_state.text_content = None
if 'summary' not in st.session_state:
    st.session_state.summary = None
if 'selected_voice_name' not in st.session_state:
    st.session_state.selected_voice_name = ""
if 'uploaded_file_name' not in st.session_state:
    st.session_state.uploaded_file_name = None
if 'tts_result' not in st.session_state:
    st.session_state.tts_result = None
if 'ssml_generated' not in st.session_state:
    st.session_state.ssml_generated = False

# Für Übersetzungs-Tool
if 'translation_job_id' not in st.session_state:
    st.session_state.translation_job_id = None
if 'translation_job_status' not in st.session_state:
    st.session_state.translation_job_status = None
if 'current_style_guide' not in st.session_state:
    st.session_state.current_style_guide = None
if 'editable_style_guide' not in st.session_state:
    st.session_state.editable_style_guide = None
if 'job_cost' not in st.session_state:
    st.session_state.job_cost = None
if 'input_tokens' not in st.session_state:
    st.session_state.input_tokens = None
if 'output_tokens' not in st.session_state:
    st.session_state.output_tokens = None
if 'cached_content_name' not in st.session_state:
    st.session_state.cached_content_name = None
if 'translation_cost_usd' not in st.session_state:
    st.session_state.translation_cost_usd = None
if 'input_tokens_translation' not in st.session_state:
    st.session_state.input_tokens_translation = None
if 'output_tokens_translation' not in st.session_state:
    st.session_state.output_tokens_translation = None
if 'final_gcs_path' not in st.session_state:
    st.session_state.final_gcs_path = None

# Für Manuskript-Agent
if 'manuscript_agent_results' not in st.session_state:
    st.session_state.manuscript_agent_results = None
if 'manuscript_agent_analysis' not in st.session_state:
    st.session_state.manuscript_agent_analysis = None
if 'manuscript_agent_audience' not in st.session_state:
    st.session_state.manuscript_agent_audience = None
if 'manuscript_agent_marketing' not in st.session_state:
    st.session_state.manuscript_agent_marketing = None
if 'manuscript_agent_button_clicked' not in st.session_state:
    st.session_state.manuscript_agent_button_clicked = False

# Für allgemeine App-Funktionalität
if 'last_selected_tool' not in st.session_state:
    st.session_state.last_selected_tool = ""
if 'click_counter' not in st.session_state:
    st.session_state.click_counter = 0

# API-Schlüssel direkt aus st.secrets laden
gemini_api_key = st.secrets.get("gemini_api_key")

# Prüfe, ob die API-Schlüssel vorhanden sind.
missing_keys = []
if not gemini_api_key:
    missing_keys.append("gemini-api-key")

if missing_keys:
    st.error(f" Folgende API-Schlüssel sind nicht konfiguriert: {', '.join(missing_keys)}")
    st.info("Die App läuft im Demo-Modus. Funktionen sind eingeschränkt.")
    logging.warning("API-Schlüssel fehlen: %s", missing_keys)

# --- Seitenleiste ---
with st.sidebar:
    st.image("app_icon.png", width=100)
    st.markdown("Willkommen!")
    st.divider()
    st.markdown("# 🧰 Toolbox")
    st.markdown("##### AI-Tools für dich")
    st.divider()
    st.subheader("ℹ️ Info")

# --- Hauptbereich mit Navigation ---
# Bestimme den Standard-Index basierend auf dem letzten ausgewählten Tool
default_index = 0
if st.session_state.get("last_selected_tool") == "Manuskript-Übersetzung":
    default_index = 3

selected_tool = option_menu(
    menu_title=None,
    options=["SEO Tags", "Barrierefreie Bildbeschreibung", "Text-to-Speech", "Manuskript-Übersetzung", "Manuskript-Agent"],
    icons=['search', 'universal-access-circle', 'sound-wave', 'translate', 'robot'],
    menu_icon="cast", default_index=default_index, orientation="horizontal",
    styles={
        "container": {"padding": "5px !important", "background-color": "#fafafa", "border-radius": "10px"},
        "icon": {"color": "#4A90E2", "font-size": "24px"},
        "nav-link": {"font-size": "16px", "font-weight": "600", "text-align": "center", "margin": "0px 5px", "--hover-color": "#eee", "border-radius": "10px"},
        "nav-link-selected": {"background-color": "#007bff"},
    }
)

# Update der Sidebar-Info basierend auf der Tool-Auswahl
with st.sidebar:
    supported_formats_images = "jpg, jpeg, png, gif, bmp, webp, tif, tiff"
    if selected_tool == "SEO Tags":
        st.markdown(f"Erzeuge **Alt** und **Title Tags** mit Gemini.\n\n**Unterstützte Formate:** `{supported_formats_images}`\n\nBei Fragen -> Gordon")
    elif selected_tool == "Barrierefreie Bildbeschreibung":
        st.markdown(f"Erzeuge **Bildbeschreibungen** mit Gemini.\n\n**Unterstützte Formate:** `{supported_formats_images}`\n\n**Download möglich:** Die Ergebnisse können als Excel-Datei heruntergeladen werden.\n\nBei Fragen -> Gordon")
    elif selected_tool == "Text-to-Speech":
        st.markdown("**Unterstützte Formate:** `.docx`, `.pdf`\n\n**🎤 TTS:** Google Cloud Text-to-Speech\n\nBei Fragen -> Gordon")
    elif selected_tool == "Manuskript-Übersetzung":
        st.markdown("Übersetze **deutsche Manuskripte** ins Englische im Hintergrund.\n\n**Unterstützte Formate:** `.docx`, `.pdf`\n\n**Features:** Asynchrone Verarbeitung, Job-Tracking\n\nBei Fragen -> Gordon")
    elif selected_tool == "Manuskript-Agent":
        st.markdown("🤖 **AI-Agent für Manuskript-Analyse**\n\n**Features:**\n- Manuskript-Analyse & Bewertung\n- Zielgruppen-Identifikation\n- Marketing-Strategien\n- ROI-Analyse\n\n**Unterstützte Formate:** `.docx`, `.pdf`\n\nBei Fragen -> Gordon")

st.divider()

logging.info("Streamlit-App gestartet, Tool ausgewählt: %s", selected_tool)


# --- Logik für jedes Werkzeug ---


# Clear state when switching tools
if selected_tool != st.session_state.get("last_selected_tool", ""):
    st.session_state.tts_step = 1
    st.session_state.guideline = None
    st.session_state.top_3_voices = []
    st.session_state.text_content = None
    st.session_state.summary = None
    st.session_state.selected_voice_name = ""
    st.session_state.uploaded_file_name = None
    st.session_state.seo_results = None
    st.session_state.seo_url_result = None
    st.session_state.accessibility_results = None
    st.session_state.accessibility_export_data = None
    st.session_state.accessibility_summary = None
    st.session_state.tts_result = None
    st.session_state.ssml_generated = False
    st.session_state.translation_job_id = None
    st.session_state.translation_job_status = None
    st.session_state.current_style_guide = None
    st.session_state.editable_style_guide = None
    st.session_state.job_cost = None
    st.session_state.input_tokens = None
    st.session_state.output_tokens = None
    st.session_state.cached_content_name = None
    st.session_state.translation_cost_usd = None
    st.session_state.input_tokens_translation = None
    st.session_state.output_tokens_translation = None
    st.session_state.final_gcs_path = None
    st.session_state.manuscript_agent_results = None
    st.session_state.manuscript_agent_analysis = None
    st.session_state.manuscript_agent_audience = None
    st.session_state.manuscript_agent_marketing = None
    
    # Reset button click states
    st.session_state.seo_button_clicked = False
    st.session_state.seo_url_button_clicked = False
    st.session_state.accessibility_button_clicked = False
    st.session_state.tts_button_clicked = False
    st.session_state.manuscript_agent_button_clicked = False
    
    # Clear all logging guards and click IDs when switching tools
    for key in list(st.session_state.keys()):
        if key.startswith("logged_") or key.endswith("_click_id") or key.endswith("_logged") or key.endswith("_button_clicked"):
            del st.session_state[key]
    
    st.session_state.last_selected_tool = selected_tool

if selected_tool == "SEO Tags":
    st.header("SEO Tags (Alt & Title) generieren")
    st.caption("Dieses Werkzeug erstellt prägnante `alt`- und `title`-Tags für Bilder.")

    # Tab-Auswahl für Upload oder URL
    input_method = st.radio(
        "Wähle die Eingabemethode:",
        ("Datei-Upload", "Bild-URL"),
        horizontal=True,
        key="seo_input_method"
    )
    st.divider()

    # --- Logik für Datei-Upload ---
    if input_method == "Datei-Upload":
        seo_uploaded_files = st.file_uploader(
            "Bilder für SEO Tags hochladen...", accept_multiple_files=True,
            type=['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'tif', 'tiff'], key="seo_uploader"
        )

        if seo_uploaded_files:
            st.button(
                "🚀 SEO Tags für Dateien verarbeiten",
                key="process_seo_files_button",
                on_click=set_button_clicked_true,
                args=("seo_button_clicked",)
            )
    
    # --- Block 1: Verarbeitung und Event-Senden ---
    if st.session_state.get("seo_button_clicked", False) and seo_uploaded_files:
        # Führe die Verarbeitung aus
        results = []
        with st.spinner("Verarbeite SEO Tags..."):
            for i, uploaded_file in enumerate(seo_uploaded_files):
                file_name = uploaded_file.name
                safe_file_name_part = "".join(c if c.isalnum() else "_" for c in file_name)
                base_id = f"seo_file_{i}_{safe_file_name_part}"
                try:
                    original_image_bytes = uploaded_file.getvalue()
                    
                    logging.info("Generiere SEO Tags für Datei: %s", file_name)
                    title, alt = generate_seo_tags_cached(original_image_bytes, file_name, gemini_api_key)
                    
                    if title and alt:
                        logging.info("SEO Tags erfolgreich generiert für: %s", file_name)
                        results.append({
                            "file_name": file_name,
                            "title": title,
                            "alt": alt,
                            "image_bytes": original_image_bytes,
                            "base_id": base_id,
                            "status": "success"
                        })
                    else:
                        logging.error("SEO Tag-Generierung fehlgeschlagen für: %s", file_name)
                        results.append({
                            "file_name": file_name,
                            "error": f"❌ Fehler bei SEO Tag-Generierung für '{file_name}'.",
                            "status": "failed"
                        })
                except Exception as e:
                    logging.error("Unerwarteter Fehler bei SEO Tag-Generierung für %s: %s", file_name, str(e))
                    results.append({
                        "file_name": file_name,
                        "error": f"🚨 Unerwarteter FEHLER bei '{file_name}': {e}",
                        "status": "error",
                        "error_message": str(e)
                    })

        # Speichere Ergebnisse im Session State
        st.session_state.seo_results = results

        # Sende das Tracking-Event GENAU EINMAL
        for result in results:
            log_data = {
                "event_type": "seo_tags_processed",
                "file_name": result["file_name"],
                "file_count": 1,
                "status": result["status"]
            }
            if "error_message" in result:
                log_data["error_message"] = result["error_message"]
            send_event_to_pubsub(log_data)

        # Setze den Zustand zurück, um erneute Ausführung zu verhindern
        st.session_state.seo_button_clicked = False
        st.success("SEO-Verarbeitung abgeschlossen.")
    
    # --- Block 2: Ergebnisse anzeigen, wenn sie im State vorhanden sind ---
    if st.session_state.get("seo_results"):
        st.divider()
        st.subheader("Verarbeitungsergebnisse")
        
        for result in st.session_state.get("seo_results", []):
            if "error" in result:
                st.error(result["error"])
            else:
                with st.expander(f"✅ SEO Tags für: {result['file_name']}", expanded=True):
                    alt_button_id = f"alt_btn_{result['base_id']}"
                    title_button_id = f"title_btn_{result['base_id']}"
                    col1, col2 = st.columns([1, 3], gap="medium")
                    with col1:
                        st.image(result['image_bytes'], width=150, caption="Vorschau")
                    with col2:
                        st.text("ALT Tag:")
                        st.text_area("ALT", value=result['alt'], height=75, key=f"alt_text_{result['base_id']}", disabled=True, label_visibility="collapsed")
                        alt_json = json.dumps(result['alt'])
                        components.html(f"""<button id="{alt_button_id}">ALT kopieren</button><script>document.getElementById("{alt_button_id}").addEventListener('click', function(){{navigator.clipboard.writeText({alt_json}).then(function(){{let b=document.getElementById("{alt_button_id}");let o=b.innerText;b.innerText='Kopiert!';setTimeout(function(){{b.innerText=o}},1500)}})}});</script><style>#{alt_button_id}{{background-color:#007bff;color:white;border:none;padding:5px 10px;border-radius:5px;cursor:pointer;margin-top:5px}}#{alt_button_id}:hover{{background-color:#0056b3}}</style>""", height=45)
                        
                        st.write("")
                        
                        st.text("TITLE Tag:")
                        st.text_area("TITLE", value=result['title'], height=75, key=f"title_text_{result['base_id']}", disabled=True, label_visibility="collapsed")
                        title_json = json.dumps(result['title'])
                        components.html(f"""<button id="{title_button_id}">TITLE kopieren</button><script>document.getElementById("{title_button_id}").addEventListener('click', function(){{navigator.clipboard.writeText({title_json}).then(function(){{let b=document.getElementById("{title_button_id}");let o=b.innerText;b.innerText='Kopiert!';setTimeout(function(){{b.innerText=o}},1500)}})}});</script><style>#{title_button_id}{{background-color:#007bff;color:white;border:none;padding:5px 10px;border-radius:5px;cursor:pointer;margin-top:5px}}#{title_button_id}:hover{{background-color:#0056b3}}</style>""", height=45)
    
    # --- Logik für Bild-URL ---
    elif input_method == "Bild-URL":
        image_url = st.text_input("Bild-URL einfügen:", placeholder="https://...", key="seo_url_input")
        st.caption("Bitte füge einen direkten Link zu einer Bilddatei ein (z.B. endend auf .jpg, .png).")

        if image_url:
            st.button("🚀 SEO Tags für URL verarbeiten", type="primary", key="process_seo_url_button", on_click=set_button_clicked_true, args=("seo_url_button_clicked",))
    
    # --- Block 1: URL Verarbeitung und Event-Senden ---
    if st.session_state.get("seo_url_button_clicked", False) and image_url:
        with st.spinner(f"Verarbeite Bild von URL..."):
            try:
                title, alt = generate_seo_tags_cached(image_url, image_url, gemini_api_key)
                
                if title and alt:
                    st.session_state.seo_url_result = {
                        "title": title,
                        "alt": alt,
                        "image_url": image_url,
                        "status": "success"
                    }
                else:
                    st.session_state.seo_url_result = {
                        "error": "❌ Fehler bei SEO Tag-Generierung für die URL.",
                        "status": "failed"
                    }
            except Exception as e:
                st.session_state.seo_url_result = {
                    "error": f"🚨 Unerwarteter FEHLER bei der Verarbeitung der URL: {e}",
                    "status": "error",
                    "error_message": str(e)
                }

        # Sende das Tracking-Event GENAU EINMAL
        result = st.session_state.get("seo_url_result")
        log_data = {
            "event_type": "seo_url_processed",
            "file_count": 1,
            "status": result["status"]
        }
        if "error_message" in result:
            log_data["error_message"] = result["error_message"]
        send_event_to_pubsub(log_data)

        # Setze den Zustand zurück, um erneute Ausführung zu verhindern
        st.session_state.seo_url_button_clicked = False
    
    # --- Block 2: URL Ergebnisse anzeigen ---
    if st.session_state.get("seo_url_result"):
        st.divider()
        st.subheader("Verarbeitungsergebnis")
        
        result = st.session_state.get("seo_url_result")
        if "error" in result:
            st.error(result["error"])
        else:
            base_id = "seo_url_result"
            alt_button_id = f"alt_btn_{base_id}"
            title_button_id = f"title_btn_{base_id}"
            with st.expander(f"✅ SEO Tags für die URL", expanded=True):
                col1, col2 = st.columns([1, 3], gap="medium")
                with col1:
                    st.image(result["image_url"], width=150, caption="Vorschau")
                with col2:
                    st.text("ALT Tag:")
                    st.text_area("ALT", value=result["alt"], height=75, key=f"alt_text_{base_id}", disabled=True, label_visibility="collapsed")
                    alt_json = json.dumps(result["alt"])
                    components.html(f"""<button id="{alt_button_id}">ALT kopieren</button><script>document.getElementById("{alt_button_id}").addEventListener('click', function(){{navigator.clipboard.writeText({alt_json}).then(function(){{let b=document.getElementById("{alt_button_id}");let o=b.innerText;b.innerText='Kopiert!';setTimeout(function(){{b.innerText=o}},1500)}})}});</script><style>#{alt_button_id}{{background-color:#007bff;color:white;border:none;padding:5px 10px;border-radius:5px;cursor:pointer;margin-top:5px}}#{alt_button_id}:hover{{background-color:#0056b3}}</style>""", height=45)

                    st.write("")

                    st.text("TITLE Tag:")
                    st.text_area("TITLE", value=result["title"], height=75, key=f"title_text_{base_id}", disabled=True, label_visibility="collapsed")
                    title_json = json.dumps(result["title"])
                    components.html(f"""<button id="{title_button_id}">TITLE kopieren</button><script>document.getElementById("{title_button_id}").addEventListener('click', function(){{navigator.clipboard.writeText({title_json}).then(function(){{let b=document.getElementById("{title_button_id}");let o=b.innerText;b.innerText='Kopiert!';setTimeout(function(){{b.innerText=o}},1500)}})}});</script><style>#{title_button_id}{{background-color:#007bff;color:white;border:none;padding:5px 10px;border-radius:5px;cursor:pointer;margin-top:5px}}#{title_button_id}:hover{{background-color:#0056b3}}</style>""", height=45)

elif selected_tool == "Barrierefreie Bildbeschreibung":
    st.header("Barrierefreie Bildbeschreibung (Kurz & Lang)")
    st.caption("Dieses Werkzeug erstellt eine prägnante Kurzbeschreibung (Alt-Text) und eine detaillierte Langbeschreibung für E-Books und barrierefreie Inhalte.")

    ebook_context_input = st.text_area(
        "Kontext des E-Books eingeben (optional, aber empfohlen)",
        height=100, key="ebook_context_main", max_chars=500,
        placeholder="z.B. Titel, Kapitel, Thema des Abschnitts, oder was das Bild illustrieren soll.",
        help="Dieser Kontext wird an die KI weitergegeben."
    )
    st.caption(f"{len(ebook_context_input)}/500 Zeichen")

    accessibility_uploaded_files = st.file_uploader(
        "Bilder für barrierefreie Beschreibungen hochladen...", accept_multiple_files=True,
        type=['jpg', 'jpeg', 'png', 'gif', 'bmp', 'webp', 'tif', 'tiff'], key="accessibility_uploader"
    )

    if accessibility_uploaded_files:
        st.button(
            "🚀 Beschreibungen verarbeiten",
            key="process_accessibility_button",
            on_click=set_button_clicked_true,
            args=("accessibility_button_clicked",)
        )
    
    # --- Block 1: Verarbeitung und Event-Senden ---
    if st.session_state.get("accessibility_button_clicked", False) and accessibility_uploaded_files:
        processed_count, failed_count = 0, 0
        results = []
        results_for_export = []
        
        with st.spinner("Verarbeite barrierefreie Beschreibungen..."):
            for i, uploaded_file in enumerate(accessibility_uploaded_files):
                file_name = uploaded_file.name
                safe_file_name_part = "".join(c if c.isalnum() else "_" for c in file_name)
                base_id = f"access_{i}_{safe_file_name_part}"
                try:
                    original_image_bytes = uploaded_file.getvalue()
                    image_bytes_for_api = original_image_bytes
                    if Path(file_name).suffix.lower() in ['.tif', '.tiff']:
                        with st.spinner(f"Konvertiere {file_name} (TIFF) zu PNG..."):
                            try:
                                image_bytes_for_api = convert_tiff_to_png_bytes(original_image_bytes)
                            except Exception as conv_e:
                                st.error(f"🚨 Fehler beim Konvertieren von '{file_name}': {conv_e}")
                                failed_count += 1
                                results.append({
                                    "file_name": file_name,
                                    "error": f"🚨 Fehler beim Konvertieren von '{file_name}': {conv_e}",
                                    "status": "conversion_error",
                                    "error_message": str(conv_e)
                                })
                                continue
                
                    logging.info("Generiere barrierefreie Beschreibung für Datei: %s", file_name)
                    short_desc, long_desc = generate_accessibility_description_cached(image_bytes_for_api, file_name, ebook_context_input, gemini_api_key)
                    
                    if short_desc and long_desc:
                        logging.info("Barrierefreie Beschreibung erfolgreich generiert für: %s", file_name)
                        results.append({
                            "file_name": file_name,
                            "short_desc": short_desc,
                            "long_desc": long_desc,
                            "image_bytes": original_image_bytes,
                            "base_id": base_id,
                            "status": "success"
                        })
                        processed_count += 1
                        results_for_export.append({
                            "Bildname": file_name, "Dateiname Produktion": "", "Alternativtext": short_desc,
                            "Bildlegende": "", "Anmerkung": "", "Langbeschreibung": long_desc,
                            "(Platzierung/Größe/Übersetzungstexte in der Abbildung/...)": ""
                        })
                    else:
                        logging.error("Barrierefreie Beschreibung fehlgeschlagen für: %s", file_name)
                        results.append({
                            "file_name": file_name,
                            "error": f"❌ Fehler bei Erstellung der barrierefreien Beschreibung für '{file_name}'.",
                            "status": "failed"
                        })
                        failed_count += 1
                except Exception as e:
                    logging.error("Unerwarteter Fehler bei barrierefreier Beschreibung für %s: %s", file_name, str(e))
                    results.append({
                        "file_name": file_name,
                        "error": f"🚨 Unerwarteter FEHLER bei der Hauptverarbeitung von '{file_name}': {e}",
                        "status": "error",
                        "error_message": str(e)
                    })
                    failed_count += 1

        # Speichere Ergebnisse im Session State
        st.session_state.accessibility_results = results
        st.session_state.accessibility_export_data = results_for_export
        st.session_state.accessibility_summary = {"processed_count": processed_count, "failed_count": failed_count}

        # Sende das Tracking-Event GENAU EINMAL
        for result in results:
            log_data = {
                "event_type": "accessibility_description_processed",
                "file_name": result["file_name"],
                "file_count": 1,
                "status": result["status"]
            }
            if "error_message" in result:
                log_data["error_message"] = result["error_message"]
            send_event_to_pubsub(log_data)

        # Setze den Zustand zurück, um erneute Ausführung zu verhindern
        st.session_state.accessibility_button_clicked = False
        st.success("Verarbeitung abgeschlossen.")
    
    # --- Block 2: Ergebnisse anzeigen, wenn sie im State vorhanden sind ---
    if st.session_state.get("accessibility_results"):
        st.divider()
        st.subheader("Verarbeitungsergebnisse")
        
        for result in st.session_state.get("accessibility_results", []):
            if "error" in result:
                st.error(result["error"])
            else:
                st.markdown(f"--- \n#### ✅ Ergebnisse für: `{result['file_name']}`")
                col1, col2 = st.columns([1, 3], gap="medium")
                with col1:
                    st.image(result['image_bytes'], width=150, caption="Vorschau")
                with col2:
                    st.text("Kurzbeschreibung (max. 140 Zeichen):")
                    st.text_area("Kurz", value=result['short_desc'], height=100, key=f"short_text_{result['base_id']}", disabled=True, label_visibility="collapsed")
                    short_desc_button_id = f"short_copy_{result['base_id']}"
                    short_json = json.dumps(result['short_desc'])
                    components.html(f"""<button id="{short_desc_button_id}">Kurzbeschreibung kopieren</button><script>document.getElementById("{short_desc_button_id}").addEventListener('click', function(){{navigator.clipboard.writeText({short_json}).then(function(){{let b=document.getElementById("{short_desc_button_id}");let o=b.innerText;b.innerText='Kopiert!';setTimeout(function(){{b.innerText=o}},1500)}})}});</script><style>#{short_desc_button_id}{{background-color:#007bff;color:white;border:none;padding:5px 10px;border-radius:5px;cursor:pointer;margin-top:5px}}#{short_desc_button_id}:hover{{background-color:#0056b3}}</style>""", height=45)
                    
                    with st.expander("Zeige/verberge Langbeschreibung"):
                        st.text_area("Lang", value=result['long_desc'], height=200, key=f"long_text_{result['base_id']}", disabled=True, label_visibility="collapsed")
                        long_desc_button_id = f"long_copy_{result['base_id']}"
                        long_json = json.dumps(result['long_desc'])
                        components.html(f"""<button id="{long_desc_button_id}">Langbeschreibung kopieren</button><script>document.getElementById("{long_desc_button_id}").addEventListener('click', function(){{navigator.clipboard.writeText({long_json}).then(function(){{let b=document.getElementById("{long_desc_button_id}");let o=b.innerText;b.innerText='Kopiert!';setTimeout(function(){{b.innerText=o}},1500)}})}});</script><style>#{long_desc_button_id}{{background-color:#007bff;color:white;border:none;padding:5px 10px;border-radius:5px;cursor:pointer;margin-top:5px}}#{long_desc_button_id}:hover{{background-color:#0056b3}}</style>""", height=45)
        
        # Export section
        if st.session_state.get("accessibility_export_data"):
            st.divider()
            st.subheader("📊 Ergebnisse exportieren")
            df = pd.DataFrame(st.session_state.get("accessibility_export_data", []))
            output = BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Bildbeschreibungen')
            excel_data = output.getvalue()
            st.download_button(
                label="💾 Excel-Datei herunterladen", data=excel_data,
                file_name="barrierefreie_bildbeschreibungen.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
        
        # Summary section
        if st.session_state.get("accessibility_summary"):
            st.divider()
            st.subheader("🏁 Zusammenfassung")
            summary = st.session_state.get("accessibility_summary")
            col1, col2 = st.columns(2)
            col1.metric("Erfolgreich verarbeitet", summary["processed_count"])
            col2.metric("Fehlgeschlagen", summary["failed_count"], delta=None if summary["failed_count"] == 0 else -summary["failed_count"], delta_color="inverse")

elif selected_tool == "Text-to-Speech":
    st.header("🎤 Text-to-Speech")
    st.caption("Upload a document and convert it to audio. Supports up to 1,000,000 characters. Select the document language to get appropriate voice options.")
    
    # Document upload
    uploaded_file = st.file_uploader(
        "Upload your document (.docx or .pdf)",
        type=['docx', 'pdf'],
        key="simple_tts_uploader"
    )
    
    if uploaded_file:
        st.write(f"📄 File uploaded: {uploaded_file.name}")
        
        # Extract text
        if uploaded_file.name.endswith('.pdf'):
            text_content = read_text_from_pdf(BytesIO(uploaded_file.getvalue()))
        elif uploaded_file.name.endswith('.docx'):
            text_content = read_text_from_docx(BytesIO(uploaded_file.getvalue()))
        else:
            text_content = None
        
        if text_content:
            st.success(f"✅ Text extracted: {len(text_content):,} characters")
            
            # Show preview
            with st.expander("📄 Text Preview"):
                st.text(text_content[:500] + "..." if len(text_content) > 500 else text_content)
            
            # Language selection dropdown
            language_options = {
                '🇩🇪 Deutsch': 'de',
                '🇬🇧 English': 'en',
                '🇫🇷 Français': 'fr',
                '🇪🇸 Español': 'es',
                '🇮🇹 Italiano': 'it'
            }
            
            selected_language_name = st.selectbox(
                "🌍 Select document language:",
                list(language_options.keys()),
                key="language_selection"
            )
            
            selected_lang = language_options[selected_language_name]
            
            # Get appropriate voices for the selected language
            available_voices = get_voices_for_language(selected_lang)
            
            # Voice selection with language-appropriate voices
            selected_voice = st.selectbox(
                "🎤 Choose Voice:",
                list(available_voices.keys()),
                key="simple_voice_selection"
            )
            
            # SSML option
            use_ssml = st.checkbox(
                "🎭 Use AI-enhanced speech (SSML)",
                value=True,
                help="Uses Gemini AI to add natural pauses and pacing for more expressive audio. May increase processing time."
            )
            
            # Generate button
            if st.button("🎵 Generate Audio", type="primary"):
                # Show different spinner message based on options
                if use_ssml:
                    if len(text_content) <= 4500:
                        spinner_message = "Generating SSML and audio..."
                    else:
                        spinner_message = "Generating SSML and long audio (this may take a few minutes)..."
                else:
                    spinner_message = "Generating audio..." if len(text_content) <= 4500 else "Generating long audio (this may take a few minutes)..."
                
                with st.spinner(spinner_message):
                    try:
                        voice_info = available_voices[selected_voice]
                        
                        # Use SSML-enhanced TTS if enabled
                        if use_ssml:
                            audio_data, audio_format, ssml_used = text_to_speech_with_ssml(
                                text_content, 
                                voice_info['name'],
                                voice_info['language_code'],
                                GCS_TTS_OUTPUT_BUCKET,
                                PROJECT_ID,
                                gemini_api_key,
                                use_ssml=True
                            )
                        else:
                            # Use standard TTS without SSML
                            audio_data, audio_format = smart_text_to_speech(
                                text_content, 
                                voice_info['name'],
                                voice_info['language_code'],
                                GCS_TTS_OUTPUT_BUCKET,
                                PROJECT_ID
                            )
                            ssml_used = False
                        
                        if audio_data:
                            st.session_state.simple_audio_data = audio_data
                            st.session_state.simple_audio_format = audio_format
                            st.session_state.simple_audio_filename = f"audio_{selected_lang}_{int(time.time())}.{audio_format}"
                            
                            # Show success message with details
                            if len(text_content) > 4500:
                                success_msg = f"✅ Long audio generated successfully! ({len(text_content):,} characters"
                            else:
                                success_msg = f"✅ Audio generated successfully! ({len(text_content):,} characters"
                            
                            if ssml_used:
                                success_msg += ", SSML-enhanced)"
                            else:
                                success_msg += ")"
                            
                            st.success(success_msg)
                        else:
                            st.error("❌ Audio generation failed!")
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")
                        logging.error(f"TTS error: {e}", exc_info=True)
        else:
            st.error("❌ Could not extract text from document")
    
    # Audio player
    if st.session_state.get("simple_audio_data"):
        st.divider()
        st.subheader("🎵 Generated Audio")
        
        # Get audio format (wav or mp3)
        audio_format = st.session_state.get("simple_audio_format", "wav")
        mime_type = f"audio/{audio_format}"
        
        st.audio(st.session_state.simple_audio_data, format=mime_type)
        
        # Download button
        audio_filename = st.session_state.get("simple_audio_filename", f"audio.{audio_format}")
        st.download_button(
            f"📥 Download Audio (.{audio_format})",
            data=st.session_state.simple_audio_data,
            file_name=audio_filename,
            mime=mime_type
        )

elif selected_tool == "Manuskript-Übersetzung":
    st.header("Manuskript-Übersetzung (Deutsch → Englisch)")
    st.caption("Dieses Tool übersetzt deutsche Manuskripte im Hintergrund.")

    uploaded_file = st.file_uploader(
        label="Lade dein deutsches Manuskript hoch (.docx oder .pdf)",
        type=['docx', 'pdf'],
        key="translation_uploader"
    )

    if uploaded_file:
        if st.button("🚀 Analyse starten", type="primary"):
            with st.spinner("Starte Übersetzungsauftrag..."):
                start_translation_job(uploaded_file)
            st.rerun()
    
    # Job Status Anzeige
    if st.session_state.get("translation_job_id"):
        st.divider()
        st.subheader("📋 Übersetzungsauftrag Status")
        
        # Erweiterte Status-Anzeige mit Icons
        status = st.session_state.translation_job_status
        if status == "pending":
            st.info("⏳ **Status:** Wartet auf Analyse...")
        elif status == "analyzing":
            st.info("🔍 **Status:** Analysiere Manuskript...")
        elif status == "analyzed":
            st.success("✅ **Status:** Analyse abgeschlossen!")
        elif status == "guide_approved":
            st.success("✅ **Status:** Style-Guide freigegeben!")
        elif status == "translation_queued":
            st.info("🚀 **Status:** Übersetzung in Warteschlange...")
        elif status == "translating":
            st.info("🤖 **Status:** Übersetze Manuskript...")
        elif status == "completed":
            st.success("🎉 **Status:** Übersetzung abgeschlossen!")
        elif status == "translation_failed":
            st.error("❌ **Status:** Übersetzung fehlgeschlagen!")
        else:
            st.info(f"**Status:** {status}")
        
        # Zeitabschätzung anzeigen
        time_estimate = get_time_estimate(status)
        if time_estimate:
            st.info(time_estimate)
        
        # Status-Updates
        st.info("🔄 **Status-Updates:** Klicke den Button unten, um den aktuellen Status zu prüfen.")
        st.caption("💡 **Tipp:** Bei langen Jobs regelmäßig den Status prüfen.")
        
        # Manueller Status-Update Button (empfohlen)
        if st.button("🔄 Status jetzt aktualisieren"):
            refresh_translation_status()
            st.rerun()

    
    # Kosten-Informationen anzeigen (wenn verfügbar)
    if st.session_state.get("job_cost") is not None or st.session_state.get("translation_cost_usd") is not None:
        st.divider()
        st.subheader("💰 Kosten-Übersicht")
        
        col1, col2, col3, col4 = st.columns(4)
        
        # Analyse-Kosten
        with col1:
            if st.session_state.get("job_cost") is not None:
                st.metric(
                    label="📊 Analyse-Kosten (USD)", 
                    value=f"${st.session_state.job_cost:.4f}"
                )
            else:
                st.metric(label="📊 Analyse-Kosten (USD)", value="N/A")
        
        # Übersetzungs-Kosten
        with col2:
            if st.session_state.get("translation_cost_usd") is not None:
                st.metric(
                    label="🤖 Übersetzungs-Kosten (USD)", 
                    value=f"${st.session_state.translation_cost_usd:.4f}"
                )
            else:
                st.metric(label="🤖 Übersetzungs-Kosten (USD)", value="N/A")
        
        # Gesamtkosten
        with col3:
            total_cost = 0
            if st.session_state.get("job_cost"):
                total_cost += st.session_state.job_cost
            if st.session_state.get("translation_cost_usd"):
                total_cost += st.session_state.translation_cost_usd
            
            if total_cost > 0:
                st.metric(
                    label="💵 Gesamtkosten (USD)", 
                    value=f"${total_cost:.4f}"
                )
            else:
                st.metric(label="💵 Gesamtkosten (USD)", value="N/A")
        
        # Token-Informationen
        with col4:
            if st.session_state.get("input_tokens") or st.session_state.get("input_tokens_translation"):
                total_input = (st.session_state.get("input_tokens") or 0) + (st.session_state.get("input_tokens_translation") or 0)
                st.metric(label="📝 Input Tokens", value=total_input)
            else:
                st.metric(label="📝 Input Tokens", value="N/A")

    # Style-Guide Anzeige (wenn verfügbar)
    if 'current_style_guide' in st.session_state and st.session_state.current_style_guide:
        st.divider()
        st.subheader("📋 Analyse-Ergebnis: Style-Guide & Glossar")
        
        # Erfolgsmeldung
        st.success("✅ Dokumentanalyse abgeschlossen! Der Style-Guide wurde erfolgreich generiert.")
        
        # Interaktive Bearbeitung des Style-Guides
        with st.expander("✏️ Style-Guide & Glossar bearbeiten", expanded=True):
            if st.session_state.editable_style_guide:
                style_guide = st.session_state.editable_style_guide
                
                # Style-Guide Details bearbeiten
                st.subheader("📝 Style-Guide Details")
                
                # Genre und Zielgruppe
                genre_audience = style_guide.get("style_guide", {}).get("genre_audience", "")
                edited_genre_audience = st.text_area(
                    "Genre und Zielgruppe:",
                    value=genre_audience,
                    height=60,
                    key="edited_genre_audience",
                    help="Bearbeite die Genre- und Zielgruppen-Analyse."
                )
                
                # Ton und Stimmung
                tone_mood = style_guide.get("style_guide", {}).get("tone_mood", "")
                edited_tone_mood = st.text_area(
                    "Ton und Stimmung:",
                    value=tone_mood,
                    height=60,
                    key="edited_tone_mood",
                    help="Bearbeite die Beschreibung von Ton und Stimmung."
                )
                
                # Erzählperspektive
                narrative_perspective = style_guide.get("style_guide", {}).get("narrative_perspective", "")
                edited_narrative_perspective = st.text_area(
                    "Erzählperspektive:",
                    value=narrative_perspective,
                    height=60,
                    key="edited_narrative_perspective",
                    help="Bearbeite die Erzählperspektive."
                )
                
                # Charakternamen
                character_names = style_guide.get("style_guide", {}).get("character_names", "")
                edited_character_names = st.text_area(
                    "Charakternamen:",
                    value=character_names,
                    height=60,
                    key="edited_character_names",
                    help="Bearbeite die Liste der Hauptcharaktere."
                )
                
                # Schlüsselkonzepte
                key_concepts = style_guide.get("style_guide", {}).get("key_concepts", "")
                edited_key_concepts = st.text_area(
                    "Schlüsselkonzepte:",
                    value=key_concepts,
                    height=60,
                    key="edited_key_concepts",
                    help="Bearbeite die zentralen Begriffe der Geschichte."
                )
                
                # Stilistische Merkmale
                stylistic_features = style_guide.get("style_guide", {}).get("stylistic_features", "")
                edited_stylistic_features = st.text_area(
                    "Stilistische Merkmale:",
                    value=stylistic_features,
                    height=60,
                    key="edited_stylistic_features",
                    help="Bearbeite die Beschreibung der sprachlichen Stilmittel."
                )
                
                # Key Terms (Glossar) bearbeiten
                st.subheader("📚 Key Terms (Glossar)")
                key_terms = style_guide.get("key_terms", {})
                
                # Konvertiere Dictionary zu DataFrame für bessere Bearbeitung
                if key_terms:
                    # Erstelle DataFrame aus Dictionary
                    key_terms_df = pd.DataFrame([
                        {"Deutscher Begriff": key, "Englische Übersetzung": value} 
                        for key, value in key_terms.items()
                    ])
                else:
                    # Leerer DataFrame mit korrekten Spalten
                    key_terms_df = pd.DataFrame(columns=["Deutscher Begriff", "Englische Übersetzung"])
                
                # Data Editor für Key Terms
                edited_key_terms_df = st.data_editor(
                    key_terms_df,
                    key="edited_key_terms_data",
                    num_rows="dynamic",
                    use_container_width=True
                )
                
                # Konvertiere DataFrame zurück zu Dictionary
                edited_key_terms = {}
                for _, row in edited_key_terms_df.iterrows():
                    if pd.notna(row["Deutscher Begriff"]) and pd.notna(row["Englische Übersetzung"]):
                        edited_key_terms[row["Deutscher Begriff"]] = row["Englische Übersetzung"]
                
                # Prüfe, ob Änderungen vorgenommen wurden
                has_changes = (
                    edited_genre_audience != genre_audience or
                    edited_tone_mood != tone_mood or
                    edited_narrative_perspective != narrative_perspective or
                    edited_character_names != character_names or
                    edited_key_concepts != key_concepts or
                    edited_stylistic_features != stylistic_features or
                    edited_key_terms != key_terms
                )
                
                # Speichern Button
                st.divider()
                col1, col2 = st.columns([1, 3])
                with col1:
                    button_type = "primary" if has_changes else "secondary"
                    button_text = "💾 Änderungen speichern" if has_changes else "💾 Keine Änderungen"
                    button_disabled = not has_changes
                    
                    if st.button(button_text, type=button_type, disabled=button_disabled, on_click=save_edited_style_guide):
                        st.rerun()
                with col2:
                    if has_changes:
                        st.info("💡 Nach dem Speichern wird der Job-Status auf 'guide_approved' gesetzt.")
                    else:
                        st.info("ℹ️ Keine Änderungen zum Speichern vorhanden.")
                
                # Übersetzung starten Button (nur aktiv wenn Status "analyzed" oder "guide_approved" ist)
                st.divider()
                current_status = st.session_state.get("translation_job_status")
                is_ready_for_translation = current_status in ["analyzed", "guide_approved"]
                
                if is_ready_for_translation:
                    st.subheader("🚀 Übersetzung starten")
                    st.info("Der Style-Guide wurde geprüft. Du kannst jetzt die finale Übersetzung starten.")
                    
                    if st.button(
                        "✅ Übersetzung jetzt starten",
                        on_click=trigger_translation_runner,
                        args=(st.session_state.translation_job_id,),
                        type="primary"
                    ):
                        st.rerun()
                else:
                    st.info(f"⏳ Übersetzung kann gestartet werden, sobald der Status 'analyzed' oder 'guide_approved' ist. Aktueller Status: {current_status}")
        
        # Download-Bereich
        st.divider()
        st.subheader("📥 Downloads")
        
        col1, col2 = st.columns(2)
        
        # Style-Guide Download
        with col1:
            style_guide_json = json.dumps(st.session_state.current_style_guide, indent=2, ensure_ascii=False)
            st.download_button(
                label="💾 Style-Guide herunterladen (.json)",
                data=style_guide_json.encode('utf-8'),
                file_name="style_guide.json",
                mime="application/json"
            )
        
        # Übersetztes Dokument Download (falls verfügbar)
        with col2:
            if st.session_state.get("final_gcs_path"):
                st.success("🎉 Übersetzung verfügbar!")
                
                # Download-Button für die übersetzte Datei
                if st.button("📥 Übersetztes Dokument herunterladen", type="primary"):
                    try:
                        # Lade Datei aus Cloud Storage
                        from google.cloud import storage
                        storage_client = storage.Client()
                        
                        # Parse GCS-Pfad
                        gcs_path = st.session_state.final_gcs_path
                        if gcs_path.startswith("gs://"):
                            path_parts = gcs_path[5:].split("/", 1)
                            if len(path_parts) == 2:
                                bucket_name = path_parts[0]
                                blob_path = path_parts[1]
                                
                                # Datei herunterladen
                                bucket = storage_client.bucket(bucket_name)
                                blob = bucket.blob(blob_path)
                                file_bytes = blob.download_as_bytes()
                                
                                # Dateiname extrahieren
                                file_name = blob_path.split("/")[-1]
                                
                                # Download-Button anzeigen
                                st.download_button(
                                    label=f"💾 {file_name} herunterladen",
                                    data=file_bytes,
                                    file_name=file_name,
                                    mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                                )
                                
                                st.success("✅ Download bereit!")
                            else:
                                st.error("❌ Ungültiger GCS-Pfad")
                        else:
                            st.error("❌ Ungültiger GCS-Pfad")
                    except Exception as e:
                        st.error(f"❌ Fehler beim Laden der Datei: {e}")
                        st.info("Du kannst die Datei auch direkt über den GCS-Pfad herunterladen:")
                        st.code(st.session_state.final_gcs_path)
                
                st.caption("Klicke den Button oben, um die übersetzte Datei direkt herunterzuladen.")
            else:
                st.info("⏳ Übersetzung noch nicht verfügbar")
                st.caption("Das übersetzte Dokument wird nach Abschluss der Übersetzung hier angezeigt.")

elif selected_tool == "Manuskript-Agent":
    st.header("🤖 Manuskript-Agent")
    st.caption("AI-Agent für umfassende Manuskript-Analyse, Zielgruppen-Identifikation und Marketing-Strategien.")

    # Manuskript-Upload
    uploaded_file = st.file_uploader(
        label="Lade dein Manuskript hoch (.docx oder .pdf)",
        type=['docx', 'pdf'],
        key="manuscript_agent_uploader"
    )

    if uploaded_file:
        st.write(f"📄 Manuskript hochgeladen: {uploaded_file.name}")
        
        # Text extrahieren
        if uploaded_file.name.endswith('.pdf'):
            text_content = read_text_from_pdf(BytesIO(uploaded_file.getvalue()))
        elif uploaded_file.name.endswith('.docx'):
            text_content = read_text_from_docx(BytesIO(uploaded_file.getvalue()))
        else:
            text_content = None
        
        if text_content:
            st.success(f"✅ Text extrahiert: {len(text_content):,} Zeichen")
            
            # Text-Vorschau
            with st.expander("📄 Manuskript-Vorschau"):
                st.text(text_content[:1000] + "..." if len(text_content) > 1000 else text_content)
            
            # Agent-Auswahl
            agent_mode = st.radio(
                "🤖 Wähle den Agent-Modus:",
                ("Kompletter Workflow", "Nur Manuskript-Analyse", "Nur Zielgruppen-Analyse", "Nur Marketing-Strategie"),
                horizontal=True
            )
            
            # Start-Button
            if st.button("🚀 Agent starten", type="primary"):
                with st.spinner("🤖 Agent arbeitet..."):
                    try:
                        # Initialisiere Agents
                        manuscript_analyzer = ManuscriptAnalyzerAgent(gemini_api_key)
                        target_audience = TargetAudienceAgent(gemini_api_key)
                        marketing_strategy = MarketingStrategyAgent(gemini_api_key)
                        workflow_agent = ManuscriptWorkflowAgent(gemini_api_key)
                        
                        results = {}
                        
                        if agent_mode == "Kompletter Workflow":
                            # Kompletter Workflow
                            result = asyncio.run(workflow_agent.process_manuscript(text_content))
                            results["workflow"] = result
                            
                        elif agent_mode == "Nur Manuskript-Analyse":
                            # Nur Analyse
                            analysis_result = manuscript_analyzer.tools[0].function(text_content)
                            summary_result = manuscript_analyzer.tools[1].function(text_content)
                            evaluation_result = manuscript_analyzer.tools[2].function(text_content)
                            
                            results["analysis"] = analysis_result
                            results["summary"] = summary_result
                            results["evaluation"] = evaluation_result
                            
                        elif agent_mode == "Nur Zielgruppen-Analyse":
                            # Nur Zielgruppen
                            summary_result = manuscript_analyzer.tools[1].function(text_content)
                            audience_result = target_audience.tools[0].function(summary_result["summary"])
                            channels_result = target_audience.tools[1].function(summary_result["summary"], audience_result["audience_analysis"])
                            
                            results["audience"] = audience_result
                            results["channels"] = channels_result
                            
                        elif agent_mode == "Nur Marketing-Strategie":
                            # Nur Marketing
                            summary_result = manuscript_analyzer.tools[1].function(text_content)
                            audience_result = target_audience.tools[0].function(summary_result["summary"])
                            strategy_result = marketing_strategy.tools[0].function(summary_result["summary"], audience_result["audience_analysis"])
                            
                            results["strategy"] = strategy_result
                        
                        # Ergebnisse im Session State speichern
                        st.session_state.manuscript_agent_results = results
                        st.session_state.manuscript_agent_button_clicked = True
                        
                        st.success("✅ Agent-Analyse abgeschlossen!")
                        
                    except Exception as e:
                        st.error(f"❌ Fehler bei der Agent-Analyse: {str(e)}")
                        logging.error(f"Manuscript Agent error: {e}")
        else:
            st.error("❌ Konnte Text aus dem Dokument nicht extrahieren")
    
    # Ergebnisse anzeigen
    if st.session_state.get("manuscript_agent_results"):
        st.divider()
        st.subheader("🤖 Agent-Ergebnisse")
        
        results = st.session_state.manuscript_agent_results
        
        # Tab-basierte Anzeige der Ergebnisse
        if "workflow" in results:
            # Kompletter Workflow
            st.success("🎉 Kompletter Workflow abgeschlossen!")
            st.json(results["workflow"])
            
        else:
            # Einzelne Ergebnisse
            tab1, tab2, tab3, tab4 = st.tabs(["📊 Analyse", "🎯 Zielgruppe", "📈 Marketing", "📋 Zusammenfassung"])
            
            with tab1:
                if "analysis" in results:
                    st.subheader("📊 Manuskript-Analyse")
                    st.text_area("Analyse", value=results["analysis"]["analysis"], height=300, disabled=True)
                
                if "evaluation" in results:
                    st.subheader("⭐ Bewertung")
                    st.text_area("Bewertung", value=results["evaluation"]["evaluation"], height=200, disabled=True)
            
            with tab2:
                if "audience" in results:
                    st.subheader("🎯 Zielgruppen-Analyse")
                    st.text_area("Zielgruppe", value=results["audience"]["audience_analysis"], height=300, disabled=True)
                
                if "channels" in results:
                    st.subheader("📢 Marketing-Kanäle")
                    st.text_area("Kanäle", value=results["channels"]["marketing_channels"], height=200, disabled=True)
            
            with tab3:
                if "strategy" in results:
                    st.subheader("📈 Marketing-Strategie")
                    st.text_area("Strategie", value=results["strategy"]["optimized_strategy"], height=300, disabled=True)
            
            with tab4:
                if "summary" in results:
                    st.subheader("📋 Zusammenfassung")
                    st.text_area("Zusammenfassung", value=results["summary"]["summary"], height=200, disabled=True)
                
                # Download-Button für Ergebnisse
                if st.button("💾 Ergebnisse herunterladen"):
                    results_json = json.dumps(results, indent=2, ensure_ascii=False)
                    st.download_button(
                        label="📥 Agent-Ergebnisse herunterladen (.json)",
                        data=results_json.encode('utf-8'),
                        file_name=f"manuscript_agent_results_{int(time.time())}.json",
                        mime="application/json"
                    )

# --- SICHERHEITSKONFIGURATION FÜR TTS ---
MAX_TTS_COST_USD = 10.0  # Maximal 10 USD pro TTS-Job (erhöht von 5.0)
MAX_TTS_RUNTIME_MINUTES = 30  # Maximal 30 Minuten Laufzeit
TTS_STATUS_CHECK_INTERVAL = 2  # Status alle 2 Sekunden prüfen
MAX_TTS_RETRIES = 3  # Maximal 3 Wiederholungen bei Fehlern

# Berechnung der maximalen Seitenanzahl
# Annahme: 250 Wörter/Seite × 5 Zeichen/Wort = 1250 Zeichen/Seite
# SSML-Expansion: +25% = 1562.5 Zeichen/Seite
# $10 ÷ $0.18 × 1000 Zeichen = 55.556 Zeichen
# 55.556 ÷ 1562.5 = ~35.5 Seiten
MAX_PAGES_FOR_TTS = 35  # Maximale Seitenanzahl für TTS

def calculate_tts_cost(text_length_chars):
    """Berechnet die Kosten für Google TTS basierend auf Textlänge."""
    return (text_length_chars / 1000000) * GOOGLE_TTS_PRICE_PER_1M_CHARS

def estimate_total_tts_cost(text_content):
    """Schätzt die Gesamtkosten für einen TTS-Job."""
    if not text_content:
        return 0.0
    
    # Schätze SSML-Expansion (SSML ist meist 20-30% länger als Originaltext)
    estimated_ssml_length = len(text_content) * 1.25
    return calculate_tts_cost(estimated_ssml_length)

def estimate_page_count(text_content):
    """Schätzt die Seitenanzahl basierend auf Textlänge."""
    if not text_content:
        return 0
    
    # Annahme: 250 Wörter/Seite × 5 Zeichen/Wort = 1250 Zeichen/Seite
    chars_per_page = 1250
    return max(1, len(text_content) // chars_per_page)

def check_tts_safety(start_time, current_cost=0.0, chunks_processed=0, total_chunks=0):
    """
    Prüft alle Sicherheitsbedingungen für den TTS-Job.
    Gibt True zurück wenn Job sicher weiterlaufen kann, False wenn gestoppt werden muss.
    """
    try:
        # 1. Zeit-Limit prüfen
        runtime_minutes = (datetime.datetime.utcnow() - start_time).total_seconds() / 60
        if runtime_minutes > MAX_TTS_RUNTIME_MINUTES:
            st.error(f"🚨 SICHERHEIT: TTS-Job läuft seit {runtime_minutes:.1f} Minuten. Maximal {MAX_TTS_RUNTIME_MINUTES} Minuten erlaubt.")
            return False
        
        # 2. Kosten-Limit prüfen
        if current_cost > MAX_TTS_COST_USD:
            st.error(f" SICHERHEIT: Kosten von ${current_cost:.2f} überschreiten Limit von ${MAX_TTS_COST_USD}")
            return False
        
        # 3. Kill Switch prüfen (aus Session State)
        if st.session_state.get("tts_kill_switch", False):
            st.error(" KILL SWITCH: TTS-Job wurde manuell gestoppt")
            return False
        
        return True
        
    except Exception as e:
        st.error(f"⚠️ Fehler bei TTS-Sicherheitsprüfung: {e}")
        return False



@log_exceptions
def get_voice_recommendations(_summary: str, _voices_info: str = None, gemini_api_key: str = None) -> Tuple[str, list]:
    """Erstellt eine Regieleitlinie und extrahiert die Top 3 Stimmen für Google TTS."""
    try:
        if gemini_api_key:
            genai.configure(api_key=gemini_api_key)
            
        # Hole Google TTS Stimmen
        if not _voices_info or not _voices_info.strip():
            try:
                available_voices = get_google_tts_voices()
                if available_voices:
                    _voices_info = "\n".join([f"{name}" for name in available_voices.keys()])
                else:
                    _voices_info = "en-US-Wavenet-D, en-US-Wavenet-F, en-US-Standard-D, en-US-Standard-F"
            except:
                _voices_info = "en-US-Wavenet-D, en-US-Wavenet-F, en-US-Standard-D, en-US-Standard-F"

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
