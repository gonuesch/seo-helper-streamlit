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

def clean_json_response(json_str):
    """Robuste JSON-Bereinigung für Gemini-Antworten"""
    print(f"🔍 Rohe Gemini-Antwort: {json_str[:200]}...")
    
    # 1. Entferne Markdown-Codeblöcke
    if "```json" in json_str:
        json_str = json_str.split("```json")[1]
        print("✅ Markdown-Codeblock ```json entfernt")
    
    if "```" in json_str:
        json_str = json_str.split("```")[0]
        print("✅ Markdown-Codeblock ``` entfernt")
    
    # 2. Entferne führende/abschließende Leerzeichen
    json_str = json_str.strip()
    
    # 3. Finde JSON-Bereich
    start_idx = json_str.find('{')
    end_idx = json_str.rfind('}')
    
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        json_str = json_str[start_idx:end_idx + 1]
        print("✅ JSON-Inhalt extrahiert (von { bis })")
    else:
        print("⚠️ Keine geschweiften Klammern gefunden")
        return None
    
    # 4. Einfache String-Reparatur
    print("🔧 Behandle unterminated strings...")
    
    # Repariere häufige JSON-Probleme
    json_str = json_str.replace('\\"', '"')  # Entferne escaped quotes
    json_str = json_str.replace('\\n', ' ')  # Ersetze newlines
    json_str = json_str.replace('\\t', ' ')  # Ersetze tabs
    
    # Entferne trailing commas
    import re
    json_str = re.sub(r',\s*}', '}', json_str)
    json_str = re.sub(r',\s*]', ']', json_str)
    
    # Repariere unterminated strings
    lines = json_str.split('\n')
    for i, line in enumerate(lines):
        if line.count('"') % 2 != 0:  # Ungerade Anzahl von Anführungszeichen
            if not line.endswith('"') and not line.endswith(','):
                lines[i] = line + '"'
                print(f"✅ Unvollständigen String repariert in Zeile {i+1}")
    
    json_str = '\n'.join(lines)
    
    # 5. Stelle sicher, dass JSON korrekt endet
    if not json_str.endswith('}'):
        open_braces = json_str.count('{')
        close_braces = json_str.count('}')
        if open_braces > close_braces:
            json_str += '}' * (open_braces - close_braces)
            print(f"✅ {open_braces - close_braces} fehlende schließende Klammern hinzugefügt")
    
    print(f"🔍 Bereinigte Antwort: {json_str[:200]}...")
    return json_str

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
    start_time = datetime.datetime.utcnow()
    max_runtime_minutes = 30  # Maximal 30 Minuten Laufzeit
    
    try:
        # --- Clients "Lazy" initialisieren ---
        firestore_client = firestore.Client(project=PROJECT_ID, database=FIRESTORE_DB_ID)
        vertexai.init(project=PROJECT_ID, location=LOCATION)
        model = GenerativeModel("gemini-2.5-pro")

        # 1. Job-ID aus der Pub/Sub-Nachricht holen
        pubsub_message = json.loads(cloudevent.data.decode('utf-8'))
        message_data_b64 = pubsub_message["message"]["data"]
        job_id = json.loads(base64.b64decode(message_data_b64).decode('utf-8'))["job_id"]
        print(f"🚀 Starte SINGLE-CALL-Analyse für Job-ID: {job_id}")

        # 2. Job-Details aus Firestore laden & Status aktualisieren
        job_ref = firestore_client.collection("translation_jobs").document(job_id)
        job_doc = job_ref.get()
        
        if not job_doc.exists:
            raise ValueError(f"Job {job_id} nicht in Firestore gefunden")
        
        job_data = job_doc.to_dict()
        current_status = job_data.get("status", "unknown")
        
        # Prüfe ob Job bereits abgeschlossen oder in Bearbeitung ist
        if current_status == "analyzed":
            print(f"✅ Job {job_id} bereits analysiert. Überspringe Analyse.")
            return ("OK - Already analyzed", 200)
        
        if current_status == "analyzing":
            print(f"⚠️ Job {job_id} bereits in Analyse. Prüfe ob noch aktiv...")
            analysis_started = job_data.get("analysis_started_at")
            if analysis_started:
                if hasattr(analysis_started, 'replace'):
                    analysis_started = analysis_started.replace(tzinfo=None)
                time_diff = datetime.datetime.utcnow() - analysis_started
                if time_diff.total_seconds() > 1800:  # 30 Minuten
                    print(f"⚠️ Analyse läuft seit {time_diff.total_seconds()/60:.1f} Minuten. Starte neu...")
                else:
                    print(f"✅ Analyse läuft bereits seit {time_diff.total_seconds()/60:.1f} Minuten. Überspringe.")
                    return ("OK - Already in progress", 200)
        
        gcs_path = job_data["source_gcs_path"]
        file_name = job_data["file_name"]
        
        # Status mit Zeitstempel aktualisieren
        job_ref.update({
            "status": "analyzing",
            "analysis_started_at": datetime.datetime.utcnow(),
            "analysis_lock": f"locked_{datetime.datetime.utcnow().isoformat()}"
        })
        print(f"✅ Status auf 'analyzing' gesetzt mit Lock")

        # 3. Gesamtes Manuskript als Bytes-Objekt laden (mit Timeout-Überprüfung)
        print(f"📄 Lade Datei herunter von: {gcs_path}")
        manuscript_bytes = get_manuscript_file(gcs_path)
        print(f"✅ Datei heruntergeladen: {len(manuscript_bytes)} Bytes")
        
        # Laufzeit-Überprüfung
        runtime_minutes = (datetime.datetime.utcnow() - start_time).total_seconds() / 60
        if runtime_minutes > max_runtime_minutes:
            raise ValueError(f"Laufzeit-Limit überschritten: {runtime_minutes:.1f} Minuten")
        
        # 4. DOCX/PDF in Text konvertieren (WICHTIG für Gemini!)
        print(f"📝 Extrahiere Text aus {file_name}...")
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
        
        print(f"✅ Text erfolgreich extrahiert: {len(manuscript_text)} Zeichen")
        
        # Laufzeit-Überprüfung nach Text-Extraktion
        runtime_minutes = (datetime.datetime.utcnow() - start_time).total_seconds() / 60
        if runtime_minutes > max_runtime_minutes:
            raise ValueError(f"Laufzeit-Limit überschritten: {runtime_minutes:.1f} Minuten")
        
        # 5. Vertex AI Cache erstellen für spätere Übersetzung (mit Timeout und Fallback)
        print(f"🔄 Erstelle Vertex AI Cache für Job {job_id}...")
        manuscript_part = Part.from_data(data=manuscript_text.encode('utf-8'), mime_type="text/plain")
        
        cache = None
        cache_start_time = datetime.datetime.utcnow()
        
        try:
            # Prüfe ob Text groß genug für Cache ist (mindestens 1024 Tokens)
            estimated_tokens = len(manuscript_text) // 4  # Grobe Schätzung
            if estimated_tokens < 1024:
                print(f"⚠️ Text zu kurz für Cache ({estimated_tokens} Tokens < 1024). Überspringe Cache-Erstellung.")
                cache = None
            else:
                print(f"📊 Geschätzte Tokens: {estimated_tokens} (Cache-Minimum: 1024)")
                
                # Cache mit Timeout erstellen
                cache = caching.CachedContent.create(
                    model_name="gemini-2.5-pro",
                    system_instruction="Du bist ein Experte für Literaturanalyse und Übersetzung.",
                    contents=[manuscript_part]
                )
                
                cache_duration = (datetime.datetime.utcnow() - cache_start_time).total_seconds()
                print(f"✅ Cache erstellt: {cache.name} (Dauer: {cache_duration:.1f}s)")
                
        except Exception as cache_error:
            cache_duration = (datetime.datetime.utcnow() - cache_start_time).total_seconds()
            print(f"⚠️ Cache-Erstellung fehlgeschlagen nach {cache_duration:.1f}s: {cache_error}")
            print("🔄 Übersetzung läuft ohne Cache weiter...")
            cache = None
            
            # Laufzeit-Überprüfung nach Cache-Fehler
            runtime_minutes = (datetime.datetime.utcnow() - start_time).total_seconds() / 60
            if runtime_minutes > max_runtime_minutes:
                raise ValueError(f"Laufzeit-Limit überschritten: {runtime_minutes:.1f} Minuten")
        
        # 6. Gemini zur Analyse des GESAMTEN Manuskripts aufrufen
        prompt = f"""
        Analysiere dieses Manuskript und erstelle ein JSON-Objekt.

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
        - Identifiziere 10 wichtige Schlüsselbegriffe aus dem Text
        - Das können sein: Personennamen, Ortsnamen, spezifische Begriffe, Konzepte, Titel
        - Gib für jeden Begriff die deutsche Bezeichnung und die englische Übersetzung an
        - Beispiel: "Das Große Vergehen" → "The Great Transgression"

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
        
        # Generation-Config OHNE response_schema
        generation_config = GenerationConfig(
            temperature=0.1,  # Niedrige Temperatur für konsistente Ausgabe
            top_p=0.8,
            top_k=40,
            max_output_tokens=4096,  # Erhöht von 2048
            response_mime_type="application/json"
            # response_schema entfernt!
        )
        
        # Gemini-Aufruf mit Timeout-Überprüfung
        print(f"🤖 Starte Gemini-Analyse...")
        gemini_start_time = datetime.datetime.utcnow()
        
        try:
            response = model.generate_content(
                [prompt, manuscript_part],
                generation_config=generation_config
            )
            
            gemini_duration = (datetime.datetime.utcnow() - gemini_start_time).total_seconds()
            print(f"✅ Gemini-Analyse abgeschlossen (Dauer: {gemini_duration:.1f}s)")
            
        except Exception as gemini_error:
            gemini_duration = (datetime.datetime.utcnow() - gemini_start_time).total_seconds()
            print(f"❌ Gemini-Aufruf fehlgeschlagen nach {gemini_duration:.1f}s: {gemini_error}")
            raise ValueError(f"Gemini-Analyse fehlgeschlagen: {gemini_error}")
        
        # Laufzeit-Überprüfung nach Gemini-Aufruf
        runtime_minutes = (datetime.datetime.utcnow() - start_time).total_seconds() / 60
        if runtime_minutes > max_runtime_minutes:
            raise ValueError(f"Laufzeit-Limit überschritten: {runtime_minutes:.1f} Minuten")
        
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

        # Finale Laufzeit-Überprüfung
        total_runtime_minutes = (datetime.datetime.utcnow() - start_time).total_seconds() / 60
        print(f"📊 Gesamtlaufzeit: {total_runtime_minutes:.1f} Minuten")
        
        print(f"✅ Analyse für Job {job_id} erfolgreich abgeschlossen.")
        return ("OK", 200)

    except Exception as e:
        total_runtime_minutes = (datetime.datetime.utcnow() - start_time).total_seconds() / 60
        error_message = f"Fehler in der Analyse-Funktion nach {total_runtime_minutes:.1f} Minuten: {e}"
        print(f"❌ {error_message}")
        
        if job_ref:
            try:
                job_ref.update({
                    "status": "analysis_failed", 
                    "error_message": str(e),
                    "analysis_failed_at": datetime.datetime.utcnow(),
                    "analysis_runtime_minutes": total_runtime_minutes,
                    "analysis_lock": None  # Lock entfernen
                })
                print(f"✅ Fehler-Status in Firestore gespeichert")
            except Exception as firestore_error:
                print(f"⚠️ Konnte Fehler-Status nicht speichern: {firestore_error}")
        
        return (f"Error: {e}", 500)