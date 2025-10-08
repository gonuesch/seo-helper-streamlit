import base64
import json
import os
import io
import datetime
from google.cloud import firestore, storage, aiplatform
import vertexai
from vertexai.generative_models import GenerativeModel, Part, GenerationConfig
from vertexai import caching
import docx

# --- Konfiguration ---
PROJECT_ID = os.environ.get("GCP_PROJECT", "avid-infinity-458913-p3")
FIRESTORE_DB_ID = "hbu-toolbox-firestone"
LOCATION = "europe-west1"
BUCKET_NAME = "manuskripte-upload-avid-infinity"

# --- Preis-Konfiguration für Gemini 2.5 Pro ---
PRICE_INPUT_PER_MILLION_TOKENS = 1.25  # USD
PRICE_OUTPUT_PER_MILLION_TOKENS = 10.00 # USD

def get_manuscript_file(gcs_path):
    """Lädt eine Datei als Bytes aus GCS herunter."""
    print(f"Lade Datei herunter von: {gcs_path}")
    storage_client = storage.Client(project=PROJECT_ID)
    bucket_name, blob_name = gcs_path.replace("gs://", "").split("/", 1)
    return storage_client.bucket(bucket_name).blob(blob_name).download_as_bytes()

def read_text_from_docx(docx_bytes):
    """Extrahiert Text aus einer DOCX-Datei."""
    try:
        doc = docx.Document(io.BytesIO(docx_bytes))
        text = []
        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                text.append(paragraph.text.strip())
        return '\n'.join(text)
    except Exception as e:
        print(f"Fehler beim Lesen der DOCX-Datei: {e}")
        raise

def read_text_from_pdf(pdf_bytes):
    """Extrahiert Text aus einer PDF-Datei."""
    try:
        import PyPDF2
        pdf_reader = PyPDF2.PdfReader(io.BytesIO(pdf_bytes))
        text = []
        for page in pdf_reader.pages:
            text.append(page.extract_text())
        return '\n'.join(text)
    except Exception as e:
        print(f"Fehler beim Lesen der PDF-Datei: {e}")
        raise

def analyze_manuscript_single_call(cloudevent):
    """
    Nimmt einen Job an und analysiert das gesamte Manuskript in einem einzigen KI-Aufruf.
    Diese Funktion wird durch das Pub/Sub-Thema 'start-translation' getriggert.
    """
    job_ref = None
    job_id = "unknown-job"
    try:
        # --- Clients "Lazy" initialisieren ---
        firestore_client = firestore.Client(project=PROJECT_ID, database=FIRESTORE_DB_ID)
        vertexai.init(project=PROJECT_ID, location=LOCATION)
        model = GenerativeModel("gemini-2.5-flash")

        # 1. Job-ID aus der Pub/Sub-Nachricht holen
        pubsub_message = json.loads(cloudevent.data.decode('utf-8'))
        message_data_b64 = pubsub_message["message"]["data"]
        job_id = json.loads(base64.b64decode(message_data_b64).decode('utf-8'))["job_id"]
        print(f"Starte SINGLE-CALL-Analyse für Job-ID: {job_id}")

        # 2. Job-Details aus Firestore laden & Status aktualisieren
        job_ref = firestore_client.collection("translation_jobs").document(job_id)
        job_data = job_ref.get().to_dict()
        gcs_path = job_data["source_gcs_path"]
        file_name = job_data["file_name"]
        job_ref.update({"status": "analyzing"})

        # 3. Gesamtes Manuskript als Bytes-Objekt laden
        manuscript_bytes = get_manuscript_file(gcs_path)
        
        # 4. DOCX/PDF in Text konvertieren (WICHTIG für Gemini!)
        try:
            if file_name.lower().endswith('.docx'):
                manuscript_text = read_text_from_docx(manuscript_bytes)
            elif file_name.lower().endswith('.pdf'):
                manuscript_text = read_text_from_pdf(manuscript_bytes)
            else:
                # Fallback: versuche als UTF-8 Text zu lesen
                manuscript_text = manuscript_bytes.decode('utf-8', errors='ignore')
        except Exception as e:
            raise ValueError(f"Konnte Text aus Datei {file_name} nicht extrahieren: {e}")
        
        if not manuscript_text or manuscript_text.strip() == "":
            raise ValueError("Das Manuskript enthält keinen lesbaren Text")
        
        print(f"Text erfolgreich extrahiert: {len(manuscript_text)} Zeichen")
        
        # 5. Vertex AI Cache erstellen für spätere Übersetzung (mit Fallback)
        print(f"🔄 Erstelle Vertex AI Cache für Job {job_id}...")
        manuscript_part = Part.from_data(data=manuscript_text.encode('utf-8'), mime_type="text/plain")
        
        cache = None
        try:
            cache = caching.CachedContent.create(
                model_name="gemini-2.5-flash",
                system_instruction="Du bist ein Experte für Literaturanalyse und Übersetzung.",
                contents=[manuscript_part]
            )
            print(f"✅ Cache erstellt: {cache.name}")
        except Exception as cache_error:
            print(f"⚠️ Cache-Erstellung fehlgeschlagen: {cache_error}")
            print("🔄 Übersetzung läuft ohne Cache weiter...")
            cache = None
        
        # 6. Gemini zur Analyse des GESAMTEN Manuskripts aufrufen
        prompt = f"""
        Analysiere dieses Manuskript und erstelle ein JSON-Objekt.

        Format:
        {{
          "style_guide": {{
            "genre_audience": "Beschreibe Genre und Zielgruppe",
            "tone_mood": "Beschreibe Ton und Stimmung", 
            "narrative_perspective": "Beschreibe die Erzählperspektive",
            "character_names": "Liste die Hauptcharaktere auf",
            "key_concepts": "Liste zentrale Begriffe der Geschichte auf",
            "stylistic_features": "Beschreibe sprachliche Stilmittel"
          }},
          "key_terms": {{
            "Deutscher Begriff": "Englische Übersetzung"
          }}
        }}

        WICHTIG für key_terms:
        - Identifiziere mindestens 5-10 wichtige Schlüsselbegriffe aus dem Text
        - Das können Namen, Orte, spezifische Begriffe oder Konzepte sein
        - Gib für jeden Begriff die deutsche Bezeichnung und die englische Übersetzung an
        - Fülle die key_terms mit echten Begriffen aus dem Manuskript aus

        Manuskript: {manuscript_text[:1000]}...
        """
        
        # Cache-Name für spätere Verwendung speichern (falls verfügbar)
        cache_name = cache.name if cache else None
        if cache_name:
            print(f"📝 Cache-Name für Übersetzung: {cache_name}")
        else:
            print("📝 Übersetzung läuft ohne Cache")
        
        # Response Schema für JSON-Format
        response_schema = {
            "type": "object",
            "properties": {
                "style_guide": {
                    "type": "object",
                    "properties": {
                        "genre_audience": {"type": "string"},
                        "tone_mood": {"type": "string"},
                        "narrative_perspective": {"type": "string"},
                        "character_names": {"type": "string"},
                        "key_concepts": {"type": "string"},
                        "stylistic_features": {"type": "string"}
                    }
                },
                "key_terms": {
                    "type": "object",
                    "properties": {}
                }
            }
        }
        
        # Generation-Config mit GenerationConfig Klasse
        generation_config = GenerationConfig(
            temperature=0.1,  # Niedrige Temperatur für konsistente Ausgabe
            top_p=0.8,
            top_k=40,
            max_output_tokens=2048,
            response_mime_type="application/json",
            response_schema=response_schema
        )
        
        response = model.generate_content(
            [prompt, manuscript_part],
            generation_config=generation_config
        )
        
        # 6. Kosten-Tracking
        input_tokens = response.usage_metadata.prompt_token_count
        output_tokens = response.usage_metadata.candidates_token_count
        cost = ((input_tokens / 1000000) * PRICE_INPUT_PER_MILLION_TOKENS) + ((output_tokens / 1000000) * PRICE_OUTPUT_PER_MILLION_TOKENS)
        print(f"Job {job_id} - Analyse-Kosten berechnet: ${cost:.4f}")
        
        # 7. Style-Guide validieren und in Cloud Storage speichern
        style_guide_json_str = response.text.strip()
        
        # Prüfe ob die Antwort leer ist
        if not style_guide_json_str or len(style_guide_json_str.strip()) == 0:
            raise ValueError("Gemini hat eine leere Antwort zurückgegeben")
        
        # Intelligente Bereinigung der Gemini-Antwort
        print(f"🔍 Rohe Gemini-Antwort: {style_guide_json_str[:200]}...")
        
        # Entferne Markdown-Codeblöcke (```json, ```, etc.)
        if "```json" in style_guide_json_str:
            style_guide_json_str = style_guide_json_str.split("```json")[1]
            print("✅ Markdown-Codeblock ```json entfernt")
        
        if "```" in style_guide_json_str:
            style_guide_json_str = style_guide_json_str.split("```")[0]
            print("✅ Markdown-Codeblock ``` entfernt")
        
        # Entferne führende/abschließende Leerzeichen und Zeilenumbrüche
        style_guide_json_str = style_guide_json_str.strip()
        
        # Suche nach dem ersten { und dem letzten }
        start_idx = style_guide_json_str.find('{')
        end_idx = style_guide_json_str.rfind('}')
        
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            style_guide_json_str = style_guide_json_str[start_idx:end_idx + 1]
            print("✅ JSON-Inhalt extrahiert (von { bis })")
        else:
            print("⚠️ Keine geschweiften Klammern gefunden")
        
        print(f"🔍 Bereinigte Antwort: {style_guide_json_str[:200]}...")
        
        # Prüfe ob es gültiges JSON ist
        try:
            style_guide_data = json.loads(style_guide_json_str)
            print("✅ JSON erfolgreich geparst!")
        except json.JSONDecodeError as json_error:
            print(f"❌ Ungültiges JSON nach Bereinigung: {json_error}")
            print(f"Bereinigte Antwort: {style_guide_json_str}")
            
            # Fallback: Erstelle einen Standard-Style-Guide
            print("🔄 Erstelle Fallback-Style-Guide...")
            style_guide_data = {
                "style_guide": {
                    "genre_audience": "Allgemeine Literatur",
                    "tone_mood": "Neutral",
                    "narrative_perspective": "Nicht spezifiziert",
                    "character_names": "Charaktere aus dem Manuskript",
                    "key_concepts": "Zentrale Themen der Geschichte",
                    "stylistic_features": "Standardsprache"
                },
                "key_terms": {}
            }
            
            print("✅ Fallback-Style-Guide erstellt")
        
        # Prüfe ob die JSON-Struktur korrekt ist
        if not isinstance(style_guide_data, dict):
            raise ValueError("Gemini-Antwort ist kein JSON-Objekt")
        
        if 'style_guide' not in style_guide_data:
            raise ValueError("Gemini-Antwort enthält keinen 'style_guide' Schlüssel")
        
        if 'key_terms' not in style_guide_data:
            raise ValueError("Gemini-Antwort enthält keinen 'key_terms' Schlüssel")
        
        # Prüfe ob style_guide die erwarteten Felder hat
        required_fields = ['genre_audience', 'tone_mood', 'narrative_perspective', 'character_names', 'key_concepts', 'stylistic_features']
        missing_fields = [field for field in required_fields if field not in style_guide_data['style_guide']]
        if missing_fields:
            print(f"⚠️ Fehlende Felder im style_guide: {missing_fields}")
            # Fehlende Felder mit Standardwerten füllen
            for field in missing_fields:
                style_guide_data['style_guide'][field] = "Nicht spezifiziert"
        
        # Prüfe ob key_terms ein Dictionary ist
        if not isinstance(style_guide_data['key_terms'], dict):
            print("⚠️ key_terms ist kein Dictionary, setze auf leeres Dictionary")
            style_guide_data['key_terms'] = {}
        
        # JSON neu formatieren (sauber und valide)
        validated_json_str = json.dumps(style_guide_data, indent=2, ensure_ascii=False)
        
        print(f"✅ Style-Guide validiert: {len(validated_json_str)} Zeichen")
        print(f"📊 Style-Guide Struktur: {list(style_guide_data['style_guide'].keys())}")
        print(f"📚 Key Terms: {len(style_guide_data['key_terms'])} Einträge")
        
        # 8. Validierten Style-Guide in Cloud Storage speichern
        storage_client = storage.Client(project=PROJECT_ID)
        bucket = storage_client.bucket(BUCKET_NAME)
        style_guide_blob = bucket.blob(f"{job_id}/style_guide.json")
        style_guide_blob.upload_from_string(validated_json_str, content_type="application/json")
        
        print(f"✅ Style-Guide erfolgreich in Cloud Storage gespeichert")
        
        # 9. Job-Status in Firestore aktualisieren (inkl. Kosten und Cache-Name)
        job_ref.update({
            "status": "analyzed",
            "style_guide_gcs_path": f"gs://{BUCKET_NAME}/{style_guide_blob.name}",
            "cached_content_name": cache.name,  # ✅ Cache-Name wird gespeichert!
            "analysis_cost_usd": cost,
            "analysis_input_tokens": input_tokens,
            "analysis_output_tokens": output_tokens,
            "analyzed_at": datetime.datetime.utcnow()
        })

        print(f"✅ Analyse für Job {job_id} erfolgreich abgeschlossen.")
        return ("OK", 200)

    except Exception as e:
        error_message = f"Fehler in der Analyse-Funktion: {e}"
        print(f"❌ {error_message}")
        
        if job_ref:
            try:
                job_ref.update({
                    "status": "analysis_failed", 
                    "error_message": str(e),
                    "analysis_failed_at": datetime.datetime.utcnow()
                })
                print(f"✅ Fehler-Status in Firestore gespeichert")
            except Exception as firestore_error:
                print(f"⚠️ Konnte Fehler-Status nicht speichern: {firestore_error}")
        
        return (f"Error: {e}", 500) 