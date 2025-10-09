import base64, json, os, io, datetime, time, random
from google.cloud import firestore, storage, aiplatform
import vertexai
from vertexai.generative_models import GenerativeModel, Part
from vertexai import caching
from docx import Document
from docx.shared import Inches

# --- SICHERHEITSKONFIGURATION ---
MAX_COST_PER_JOB_USD = 10.0  # Maximal 10 Euro pro Job
MAX_RUNTIME_MINUTES = 120    # Maximal 120 Minuten Laufzeit
STATUS_CHECK_INTERVAL = 5    # Status alle 5 Sekunden prüfen
MAX_RETRIES = 3              # Maximal 3 Wiederholungen bei Fehlern

# --- Hilfsfunktionen für Fallback ---
def get_manuscript_file(gcs_path):
    """Lädt eine Datei als Bytes aus GCS herunter."""
    print(f"Lade Datei herunter von: {gcs_path}")
    storage_client = storage.Client(project=PROJECT_ID)
    bucket_name, blob_name = gcs_path.replace("gs://", "").split("/", 1)
    return storage_client.bucket(bucket_name).blob(blob_name).download_as_bytes()

def read_text_from_docx(docx_bytes):
    """Extrahiert Text aus einer DOCX-Datei."""
    try:
        doc = Document(io.BytesIO(docx_bytes))
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

# --- Konfiguration & Clients ---
PROJECT_ID = os.environ.get("GCP_PROJECT", "avid-infinity-458913-p3")
FIRESTORE_DB_ID = "hbu-toolbox-firestone"
LOCATION = "europe-west1"
BUCKET_NAME = "manuskripte-upload-avid-infinity"
PRICE_INPUT_PER_MILLION_TOKENS = 1.25
PRICE_OUTPUT_PER_MILLION_TOKENS = 10.00

firestore_client = firestore.Client(project=PROJECT_ID, database=FIRESTORE_DB_ID)
storage_client = storage.Client(project=PROJECT_ID)
vertexai.init(project=PROJECT_ID, location=LOCATION)

def check_job_safety(job_ref, start_time, current_cost=0.0):
    """
    Prüft alle Sicherheitsbedingungen für den Job.
    Gibt True zurück wenn Job sicher weiterlaufen kann, False wenn gestoppt werden muss.
    """
    try:
        # 1. Zeit-Limit prüfen
        runtime_minutes = (datetime.datetime.utcnow() - start_time).total_seconds() / 60
        if runtime_minutes > MAX_RUNTIME_MINUTES:
            print(f" SICHERHEIT: Job läuft seit {runtime_minutes:.1f} Minuten. Maximal {MAX_RUNTIME_MINUTES} Minuten erlaubt.")
            return False
        
        # 2. Kosten-Limit prüfen
        if current_cost > MAX_COST_PER_JOB_USD:
            print(f" SICHERHEIT: Kosten von ${current_cost:.2f} überschreiten Limit von ${MAX_COST_PER_JOB_USD}")
            return False
        
        # 3. Status in Firestore prüfen
        job_doc = job_ref.get()
        if job_doc.exists:
            job_data = job_doc.to_dict()
            current_status = job_data.get("status", "unknown")
            
            if current_status in ["cancelled", "translation_failed", "killed"]:
                print(f"🚨 SICHERHEIT: Job wurde gestoppt (Status: {current_status})")
                return False
            
            # 4. Kill Switch prüfen
            if job_data.get("kill_switch", False):
                print(f"🚨 KILL SWITCH: Job wurde manuell gestoppt")
                return False
        
        return True
        
    except Exception as e:
        print(f"⚠️ Fehler bei Sicherheitsprüfung: {e}")
        return False  # Bei Fehlern lieber stoppen

def monitor_translation_progress(job_ref, chunks, translated_chunks, failed_chunks):
    """
    Überwacht den Übersetzungsfortschritt und erkennt Probleme frühzeitig.
    """
    try:
        job_doc = job_ref.get()
        if not job_doc.exists:
            return True
        
        job_data = job_doc.to_dict()
        progress = job_data.get("translation_progress", {})
        
        chunks_completed = progress.get("chunks_completed", 0)
        total_chunks = progress.get("total_chunks", len(chunks))
        last_chunk_time = progress.get("last_chunk_completed_at")
        
        # Prüfe auf hängende Übersetzung
        if last_chunk_time:
            if hasattr(last_chunk_time, 'replace'):
                last_chunk_time = last_chunk_time.replace(tzinfo=None)
            
            time_since_last_chunk = datetime.datetime.utcnow() - last_chunk_time
            if time_since_last_chunk.total_seconds() > 300:  # 5 Minuten ohne Fortschritt
                print(f"⚠️ WARNUNG: Kein Fortschritt seit {time_since_last_chunk.total_seconds()/60:.1f} Minuten")
                print(f"   - Letzter Chunk: {chunks_completed}/{total_chunks}")
                print(f"   - Fehlgeschlagene Chunks: {len(failed_chunks)}")
                
                # Aktualisiere Job mit Warnung
                job_ref.update({
                    "translation_warnings": {
                        "stalled_detected": True,
                        "stall_duration_minutes": time_since_last_chunk.total_seconds() / 60,
                        "last_chunk_time": last_chunk_time.isoformat(),
                        "chunks_completed": chunks_completed,
                        "failed_chunks_count": len(failed_chunks)
                    }
                })
        
        # Prüfe auf zu viele fehlgeschlagene Chunks
        failure_rate = len(failed_chunks) / len(chunks) if chunks else 0
        if failure_rate > 0.3:  # Mehr als 30% Fehlerrate
            print(f"⚠️ WARNUNG: Hohe Fehlerrate: {failure_rate*100:.1f}% ({len(failed_chunks)}/{len(chunks)})")
            
            job_ref.update({
                "translation_warnings": {
                    "high_failure_rate": True,
                    "failure_rate": failure_rate,
                    "failed_chunks_count": len(failed_chunks),
                    "failed_chunk_indices": [fc["chunk_index"] for fc in failed_chunks]
                }
            })
        
        return True
        
    except Exception as e:
        print(f"⚠️ Fehler bei Progress-Monitoring: {e}")
        return True  # Monitoring-Fehler stoppen nicht den Job

def calculate_optimal_chunk_size(manuscript_length):
    """
    Berechnet die optimale Chunk-Größe basierend auf der Manuskript-Länge.
    Kleinere Manuskripte werden in einem Chunk verarbeitet, größere werden aufgeteilt.
    """
    if manuscript_length < 50000:  # < 50 Seiten
        return manuscript_length  # Ein Chunk
    elif manuscript_length < 150000:  # 50-150 Seiten
        return 50000  # 50 Seiten pro Chunk
    else:  # > 150 Seiten
        return 30000  # 30 Seiten pro Chunk

def split_text_into_chunks(text, chunk_size):
    """
    Teilt Text in Chunks auf, wobei Satzgrenzen respektiert werden.
    Verbesserte Version mit mehreren Satzenden und besserer Strukturerhaltung.
    """
    if len(text) <= chunk_size:
        return [text]
    
    chunks = []
    current_chunk = ""
    
    # Verbesserte Satzaufteilung mit mehreren Satzenden
    import re
    # Teile Text in Sätze auf (berücksichtigt . ! ? ; und Zeilenumbrüche)
    sentences = re.split(r'([.!?;]+\s*)', text)
    
    # Rekonstruiere Sätze mit ihren Satzenden
    reconstructed_sentences = []
    for i in range(0, len(sentences), 2):
        if i + 1 < len(sentences):
            sentence = sentences[i] + sentences[i + 1]
        else:
            sentence = sentences[i]
        if sentence.strip():
            reconstructed_sentences.append(sentence)
    
    for sentence in reconstructed_sentences:
        # Wenn der aktuelle Chunk + neuer Satz zu lang wird
        if len(current_chunk) + len(sentence) > chunk_size and current_chunk:
            chunks.append(current_chunk.strip())
            current_chunk = sentence
        else:
            current_chunk += sentence
    
    # Füge den letzten Chunk hinzu
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    
    print(f"📊 Chunk-Aufteilung: {len(chunks)} Chunks erstellt")
    for i, chunk in enumerate(chunks):
        print(f"   Chunk {i+1}: {len(chunk)} Zeichen")
    
    return chunks

def validate_translation_completeness(original_chunks, translated_chunks):
    """
    Validiert, ob alle Chunks vollständig übersetzt wurden.
    """
    print(f"🔍 Validiere Übersetzungs-Vollständigkeit...")
    
    # 1. Chunk-Anzahl prüfen
    if len(original_chunks) != len(translated_chunks):
        error_msg = f"KRITISCHER FEHLER: Chunk-Anzahl stimmt nicht überein - Original: {len(original_chunks)}, Übersetzt: {len(translated_chunks)}"
        print(f"❌ {error_msg}")
        raise ValueError(error_msg)
    
    print(f"✅ Chunk-Anzahl stimmt überein: {len(original_chunks)} Chunks")
    
    # 2. Jeden Chunk einzeln prüfen
    issues_found = []
    for i, (orig_chunk, trans_chunk) in enumerate(zip(original_chunks, translated_chunks)):
        chunk_num = i + 1
        
        # Leere oder fehlende Übersetzung
        if not trans_chunk or len(trans_chunk.strip()) == 0:
            error_msg = f"Chunk {chunk_num} ist leer oder nicht übersetzt"
            print(f"❌ {error_msg}")
            issues_found.append(error_msg)
            continue
        
        # Ungewöhnlich kurze Übersetzung (weniger als 30% der Original-Länge)
        if len(trans_chunk) < len(orig_chunk) * 0.3:
            warning_msg = f"Chunk {chunk_num} ist ungewöhnlich kurz: {len(trans_chunk)} vs {len(orig_chunk)} Zeichen ({(len(trans_chunk)/len(orig_chunk)*100):.1f}%)"
            print(f"⚠️ {warning_msg}")
            issues_found.append(warning_msg)
        
        # Ungewöhnlich lange Übersetzung (mehr als 300% der Original-Länge)
        elif len(trans_chunk) > len(orig_chunk) * 3.0:
            warning_msg = f"Chunk {chunk_num} ist ungewöhnlich lang: {len(trans_chunk)} vs {len(orig_chunk)} Zeichen ({(len(trans_chunk)/len(orig_chunk)*100):.1f}%)"
            print(f"⚠️ {warning_msg}")
            issues_found.append(warning_msg)
        
        # Erfolgreiche Validierung
        else:
            print(f"✅ Chunk {chunk_num}: {len(trans_chunk)} Zeichen ({(len(trans_chunk)/len(orig_chunk)*100):.1f}% der Original-Länge)")
    
    # 3. Zusammenfassung
    if issues_found:
        print(f"⚠️ {len(issues_found)} Probleme bei der Übersetzungs-Validierung gefunden:")
        for issue in issues_found:
            print(f"   - {issue}")
        
        # Bei kritischen Fehlern (leere Chunks) Exception werfen
        critical_issues = [issue for issue in issues_found if "ist leer oder nicht übersetzt" in issue]
        if critical_issues:
            raise ValueError(f"Kritische Übersetzungsfehler gefunden: {len(critical_issues)} leere Chunks")
    else:
        print(f"🎉 Alle {len(original_chunks)} Chunks erfolgreich validiert!")
    
    return True

def translate_chunk_with_retry(chunk, style_guide, key_terms, previous_chunk="", chunk_index=0, total_chunks=1, max_retries=3):
    """
    Übersetzt einen Chunk mit robuster Wiederholungslogik und Fallback-Strategien.
    """
    model = GenerativeModel("gemini-2.5-pro")
    
    # Rate Limiting: Pause zwischen Chunks
    if chunk_index > 0:
        sleep_time = 3 + random.uniform(0, 2)  # 3-5 Sekunden Pause
        print(f"⏳ Rate Limiting: Warte {sleep_time:.1f}s...")
        time.sleep(sleep_time)
    
    # Erstelle den Prompt mit allen notwendigen Informationen
    prompt = f"""
Übersetze diesen Text-Abschnitt ins Englische. Das ist Chunk {chunk_index + 1} von {total_chunks}.

**WICHTIGE REGELN:**
1. Übersetze den Text wortgetreu, aber idiomatisch korrekt
2. Halte dich STRIKT an das vorgegebene Glossar (key_terms) - verwende NUR die dort angegebenen Übersetzungen
3. Bewahre den ursprünglichen Ton und Stil basierend auf dem Style-Guide
4. Stelle sicher, dass der Text flüssig mit dem vorherigen Chunk übergeht

**STYLE-GUIDE (strikt befolgen):**
Genre & Zielgruppe: {style_guide.get('genre_audience', 'Nicht spezifiziert')}
Ton & Stimmung: {style_guide.get('tone_mood', 'Nicht spezifiziert')}
Erzählperspektive: {style_guide.get('narrative_perspective', 'Nicht spezifiziert')}
Charakternamen: {style_guide.get('character_names', 'Nicht spezifiziert')}
Schlüsselkonzepte: {style_guide.get('key_concepts', 'Nicht spezifiziert')}
Stilistische Merkmale: {style_guide.get('stylistic_features', 'Nicht spezifiziert')}

**GLOSSAR (key_terms) - VERWENDE NUR DIESE ÜBERSETZUNGEN:**
{chr(10).join([f"'{deutsch}' → '{englisch}'" for deutsch, englisch in key_terms.items()])}

**VORHERIGER CHUNK (für Kontext und Übergang):**
{previous_chunk if previous_chunk else "Dies ist der erste Chunk."}

**AKTUELLER CHUNK ZUM ÜBERSETZEN:**
{chunk}

**Antworte AUSSCHLIESSLICH mit der englischen Übersetzung, ohne Kommentare oder Erklärungen.**
"""
    
    # Robuste Retry-Logik mit verschiedenen Strategien
    for attempt in range(max_retries):
        try:
            print(f"🔄 Übersetze Chunk {chunk_index + 1} (Versuch {attempt + 1}/{max_retries})...")
            response = model.generate_content(prompt)
            translated_text = response.text.strip()
            
            # Validierung der Übersetzung
            if not translated_text:
                raise ValueError("Leere Übersetzung erhalten")
            
            if len(translated_text) < len(chunk) * 0.1:  # Zu kurz
                raise ValueError(f"Übersetzung zu kurz: {len(translated_text)} vs {len(chunk)} Zeichen")
            
            print(f"✅ Chunk {chunk_index + 1} erfolgreich übersetzt: {len(translated_text)} Zeichen")
            return translated_text
            
        except Exception as e:
            error_str = str(e)
            print(f"⚠️ Fehler bei Chunk {chunk_index + 1}, Versuch {attempt + 1}/{max_retries}: {error_str}")
            
            if attempt < max_retries - 1:
                # Verschiedene Wartezeiten je nach Fehlertyp
                if "429" in error_str or "rate limit" in error_str.lower():
                    wait_time = (2 ** attempt) + random.uniform(0, 5)  # Exponential backoff
                    print(f"⏳ Rate limit - warte {wait_time:.1f}s...")
                elif "quota" in error_str.lower():
                    wait_time = 30 + random.uniform(0, 10)  # Längere Wartezeit bei Quota
                    print(f"⏳ Quota-Fehler - warte {wait_time:.1f}s...")
                else:
                    wait_time = 5 + random.uniform(0, 3)  # Standard-Wartezeit
                    print(f"⏳ Standard-Fehler - warte {wait_time:.1f}s...")
                
                time.sleep(wait_time)
            else:
                # Letzter Versuch fehlgeschlagen - Fallback-Strategie
                print(f"❌ Alle Versuche für Chunk {chunk_index + 1} fehlgeschlagen. Erstelle Fallback...")
                
                # Fallback: Vereinfachter Prompt
                try:
                    simple_prompt = f"Übersetze diesen Text ins Englische:\n\n{chunk}"
                    response = model.generate_content(simple_prompt)
                    fallback_text = response.text.strip()
                    
                    if fallback_text and len(fallback_text) > len(chunk) * 0.1:
                        print(f"✅ Fallback-Übersetzung für Chunk {chunk_index + 1} erfolgreich")
                        return fallback_text
                    else:
                        raise ValueError("Fallback-Übersetzung fehlgeschlagen")
                        
                except Exception as fallback_error:
                    print(f"❌ Auch Fallback für Chunk {chunk_index + 1} fehlgeschlagen: {fallback_error}")
                    # Letzter Ausweg: Fehler-Chunk mit Informationen
                    error_chunk = f"[ÜBERSETZUNGSFEHLER - Chunk {chunk_index + 1}: {str(e)[:100]}...]\n\n[ORIGINAL TEXT: {chunk[:200]}...]"
                    print(f"⚠️ Verwende Fehler-Chunk für Chunk {chunk_index + 1}")
                    return error_chunk

def translate_chunk_with_context(chunk, style_guide, key_terms, previous_chunk="", chunk_index=0, total_chunks=1):
    """
    Wrapper-Funktion für Rückwärtskompatibilität.
    """
    return translate_chunk_with_retry(chunk, style_guide, key_terms, previous_chunk, chunk_index, total_chunks)

def run_translation_with_cache(cloudevent):
    """Übersetzt ein Manuskript mit adaptivem Chunking und behält die Formatierung bei."""
    job_ref = None
    start_time = datetime.datetime.utcnow()
    total_cost = 0.0
    
    try:
        # 1. Job-ID holen
        pubsub_message = json.loads(cloudevent.data.decode('utf-8'))
        message_data_b64 = pubsub_message["message"]["data"]
        job_id = json.loads(base64.b64decode(message_data_b64).decode('utf-8'))["job_id"]
        print(f" Starte Übersetzung mit adaptivem Chunking für Job-ID: {job_id}")

        # 2. Job-Details aus Firestore laden & Status prüfen
        job_ref = firestore_client.collection("translation_jobs").document(job_id)
        job_doc = job_ref.get()

        if not job_doc.exists:
            raise ValueError(f"Job {job_id} nicht in Firestore gefunden")

        job_data = job_doc.to_dict()
        current_status = job_data.get("status", "unknown")
        
        # IDEMPOTENZ: Prüfe ob Job bereits abgeschlossen oder in Bearbeitung ist
        if current_status == "completed":
            print(f"✅ Job {job_id} bereits abgeschlossen. Überspringe Übersetzung.")
            return ("OK - Already completed", 200)
        
        if current_status == "translating":
            print(f"⚠️ Job {job_id} bereits in Übersetzung. Prüfe ob noch aktiv...")
            translation_started = job_data.get("translation_started_at")
            if translation_started:
                # Prüfe ob die Übersetzung vor mehr als 30 Minuten gestartet wurde
                # Behandle timezone-aware und timezone-naive datetime Objekte
                if hasattr(translation_started, 'replace'):
                    # Firestore datetime ist timezone-aware, mache es timezone-naive
                    translation_started = translation_started.replace(tzinfo=None)
                
                time_diff = datetime.datetime.utcnow() - translation_started
                if time_diff.total_seconds() > 1800:  # 30 Minuten
                    print(f"⚠️ Übersetzung läuft seit {time_diff.total_seconds()/60:.1f} Minuten. Starte neu...")
                else:
                    print(f"✅ Übersetzung läuft bereits seit {time_diff.total_seconds()/60:.1f} Minuten. Überspringe.")
                    return ("OK - Already in progress", 200)
        
        file_name = job_data["file_name"]
        gcs_path = job_data["source_gcs_path"]
        style_guide_gcs_path = job_data["style_guide_gcs_path"]
        cached_content_name = job_data.get("cached_content_name")

        if not cached_content_name:
            raise ValueError(f"Kein cached_content_name für Job {job_id} gefunden")

        print(f"📋 Job-Details geladen: {file_name}")

        # Status auf 'translating' aktualisieren mit Lock
        job_ref.update({
            "status": "translating",
            "translation_started_at": datetime.datetime.utcnow(),
            "translation_lock": f"locked_{datetime.datetime.utcnow().isoformat()}",
            "kill_switch": False,  # Kill Switch initialisieren
            "safety_limits": {
                "max_cost_usd": MAX_COST_PER_JOB_USD,
                "max_runtime_minutes": MAX_RUNTIME_MINUTES
            }
        })
        print(f"✅ Status auf 'translating' gesetzt mit Lock und Sicherheitslimits")

        # 3. Style-Guide laden
        print(f"📚 Lade Style-Guide von: {style_guide_gcs_path}")
        style_guide_blob = storage_client.bucket(BUCKET_NAME).blob(style_guide_gcs_path.split(f"gs://{BUCKET_NAME}/")[1])
        style_guide_json_str = style_guide_blob.download_as_text()
        style_guide_data = json.loads(style_guide_json_str)
        print(f"✅ Style-Guide geladen: {len(style_guide_json_str)} Zeichen")

        # Style-Guide und Glossar extrahieren
        style_guide = style_guide_data.get("style_guide", {})
        key_terms = style_guide_data.get("key_terms", {})

        # 4. Cache wiederherstellen und Text extrahieren (mit verbesserter Validierung)
        print(f"🔄 Stelle Cache wieder her: {cached_content_name}")
        
        full_text = None
        cache_success = False
        
        try:
            cached_content = caching.CachedContent.get(cached_content_name)
            model_with_cache = GenerativeModel.from_cached_content(cached_content=cached_content)
            
            # Extrahiere den Text aus dem Cache mit verbesserter Validierung
            cache_response = model_with_cache.generate_content("Gib mir den kompletten Text des Manuskripts zurück, ohne Änderungen.")
            extracted_text = cache_response.text.strip()
            
            # Validierung der Cache-Extraktion
            if extracted_text and len(extracted_text) > 100:  # Mindestens 100 Zeichen
                full_text = extracted_text
                cache_success = True
                print(f"✅ Text aus Cache extrahiert: {len(full_text)} Zeichen")
            else:
                print(f"⚠️ Cache-Extraktion unvollständig: {len(extracted_text) if extracted_text else 0} Zeichen")
                raise ValueError("Cache-Extraktion unvollständig")
            
        except Exception as cache_error:
            print(f"⚠️ Cache-Wiederherstellung fehlgeschlagen: {cache_error}")
            print("🔄 Versuche Text direkt aus der Datei zu extrahieren...")
            
            # Fallback: Text direkt aus der Datei extrahieren
            try:
                file_bytes = get_manuscript_file(gcs_path)
                print(f"📄 Datei heruntergeladen: {len(file_bytes)} Bytes")
                
                if file_name.lower().endswith('.docx'):
                    full_text = read_text_from_docx(file_bytes)
                elif file_name.lower().endswith('.pdf'):
                    full_text = read_text_from_pdf(file_bytes)
                else:
                    full_text = file_bytes.decode('utf-8', errors='ignore')
                
                # Validierung der Datei-Extraktion
                if full_text and len(full_text.strip()) > 100:
                    print(f"✅ Text direkt aus Datei extrahiert: {len(full_text)} Zeichen")
                else:
                    raise ValueError(f"Datei-Extraktion unvollständig: {len(full_text) if full_text else 0} Zeichen")
                
            except Exception as file_error:
                print(f"❌ Fehler beim direkten Datei-Zugriff: {file_error}")
                raise ValueError(f"Konnte weder Cache noch Datei verwenden: {file_error}")
        
        # Finale Validierung
        if not full_text or len(full_text.strip()) == 0:
            raise ValueError("Konnte keinen Text aus Cache oder Datei extrahieren")
        
        # Zusätzliche Validierung der Textqualität
        if len(full_text) < 50:
            raise ValueError(f"Extrahierter Text zu kurz: {len(full_text)} Zeichen")
        
        print(f"📊 Text-Extraktion erfolgreich:")
        print(f"   - Methode: {'Cache' if cache_success else 'Datei'}")
        print(f"   - Länge: {len(full_text)} Zeichen")
        print(f"   - Wörter: {len(full_text.split())} Wörter")

        # 5. Optimale Chunk-Größe berechnen
        optimal_chunk_size = calculate_optimal_chunk_size(len(full_text))
        print(f" Optimale Chunk-Größe: {optimal_chunk_size} Zeichen")

        # 6. Text in Chunks aufteilen
        chunks = split_text_into_chunks(full_text, optimal_chunk_size)
        print(f"✂️ Text in {len(chunks)} Chunks aufgeteilt")

        # 7. Chunks übersetzen mit erweitertem Tracking und Debugging
        print(f"🚀 Starte Übersetzung der {len(chunks)} Chunks...")
        print(f"📊 Chunk-Statistiken:")
        print(f"   - Gesamt-Chunks: {len(chunks)}")
        print(f"   - Durchschnittliche Chunk-Größe: {sum(len(c) for c in chunks) // len(chunks)} Zeichen")
        print(f"   - Größter Chunk: {max(len(c) for c in chunks)} Zeichen")
        print(f"   - Kleinster Chunk: {min(len(c) for c in chunks)} Zeichen")
        
        translated_chunks = []
        total_input_tokens = 0
        total_output_tokens = 0
        previous_chunk = ""
        failed_chunks = []
        chunk_start_times = []

        for i, chunk in enumerate(chunks):
            chunk_start_time = datetime.datetime.utcnow()
            chunk_start_times.append(chunk_start_time)
            
            print(f"\n{'='*60}")
            print(f"🔄 VERARBEITE CHUNK {i+1}/{len(chunks)}")
            print(f"   - Chunk-Größe: {len(chunk)} Zeichen")
            print(f"   - Erste 100 Zeichen: {chunk[:100]}...")
            print(f"   - Letzte 100 Zeichen: ...{chunk[-100:]}")
            print(f"{'='*60}")
            
            # SICHERHEITSPRÜFUNG vor jedem Chunk
            if not check_job_safety(job_ref, start_time, total_cost):
                print(f"🚨 SICHERHEIT: Job wird gestoppt nach {i} Chunks")
                job_ref.update({
                    "status": "killed",
                    "killed_at": datetime.datetime.utcnow(),
                    "killed_reason": "Safety limits exceeded",
                    "chunks_completed": i,
                    "total_chunks": len(chunks),
                    "final_cost_usd": total_cost,
                    "failed_chunks": failed_chunks,
                    "chunk_processing_times": [(t.isoformat() for t in chunk_start_times)]
                })
                return ("Job killed for safety", 200)
            
            try:
                print(f"⏳ Übersetze Chunk {i+1}...")
                translated_chunk = translate_chunk_with_context(
                    chunk, 
                    style_guide, 
                    key_terms, 
                    previous_chunk, 
                    i, 
                    len(chunks)
                )
                
                # Erweiterte Validierung der Übersetzung
                if not translated_chunk or len(translated_chunk.strip()) == 0:
                    raise ValueError(f"Chunk {i+1} ergab leere Übersetzung")
                
                if len(translated_chunk) < len(chunk) * 0.1:  # Zu kurz
                    print(f"⚠️ WARNUNG: Chunk {i+1} ist ungewöhnlich kurz: {len(translated_chunk)} vs {len(chunk)} Zeichen")
                
                translated_chunks.append(translated_chunk)
                previous_chunk = translated_chunk
                
                # Token-Zählung (Schätzung basierend auf Zeichen)
                estimated_input_tokens = len(chunk) // 4  # Grobe Schätzung
                estimated_output_tokens = len(translated_chunk) // 4
                total_input_tokens += estimated_input_tokens
                total_output_tokens += estimated_output_tokens
                
                # Kosten aktualisieren
                chunk_cost = ((estimated_input_tokens / 1000000) * PRICE_INPUT_PER_MILLION_TOKENS) + ((estimated_output_tokens / 1000000) * PRICE_OUTPUT_PER_MILLION_TOKENS)
                total_cost += chunk_cost
                
                chunk_duration = (datetime.datetime.utcnow() - chunk_start_time).total_seconds()
                print(f"✅ Chunk {i+1} erfolgreich übersetzt:")
                print(f"   - Dauer: {chunk_duration:.1f}s")
                print(f"   - Übersetzungs-Länge: {len(translated_chunk)} Zeichen")
                print(f"   - Kosten: ${chunk_cost:.4f}, Gesamt: ${total_cost:.4f}")
                print(f"   - Erste 100 Zeichen der Übersetzung: {translated_chunk[:100]}...")
                
                # Detaillierte Fortschritts-Aktualisierung in Firestore
                progress_data = {
                    "translation_progress": {
                        "chunks_completed": i + 1,
                        "total_chunks": len(chunks),
                        "last_chunk_completed_at": datetime.datetime.utcnow(),
                        "current_cost_usd": total_cost,
                        "chunk_processing_times": [t.isoformat() for t in chunk_start_times],
                        "current_chunk_duration_seconds": chunk_duration,
                        "translation_quality_metrics": {
                            "avg_chunk_size": sum(len(c) for c in chunks[:i+1]) / (i+1),
                            "avg_translation_size": sum(len(t) for t in translated_chunks) / len(translated_chunks),
                            "compression_ratio": sum(len(t) for t in translated_chunks) / sum(len(c) for c in chunks[:i+1]) if sum(len(c) for c in chunks[:i+1]) > 0 else 0
                        }
                    }
                }
                
                # Zusätzliche Debugging-Informationen
                if i % 5 == 0 or i == len(chunks) - 1:  # Alle 5 Chunks oder beim letzten
                    progress_data["translation_progress"]["debug_info"] = {
                        "chunks_processed": i + 1,
                        "total_original_chars": sum(len(c) for c in chunks[:i+1]),
                        "total_translated_chars": sum(len(t) for t in translated_chunks),
                        "failed_chunks_count": len(failed_chunks),
                        "runtime_minutes": (datetime.datetime.utcnow() - start_time).total_seconds() / 60
                    }
                
                job_ref.update(progress_data)
                
                # Progress-Monitoring
                monitor_translation_progress(job_ref, chunks, translated_chunks, failed_chunks)
                
                # Längere Pause für Status-Updates und Rate Limiting
                time.sleep(2)
                
            except Exception as e:
                error_msg = f"Fehler bei Chunk {i+1}: {str(e)}"
                print(f"❌ {error_msg}")
                failed_chunks.append({
                    "chunk_index": i,
                    "chunk_size": len(chunk),
                    "error": str(e),
                    "timestamp": datetime.datetime.utcnow().isoformat()
                })
                
                # Versuche den Chunk trotzdem zu übersetzen mit Fallback
                try:
                    print(f"🔄 Versuche Fallback-Übersetzung für Chunk {i+1}...")
                    fallback_chunk = f"[ÜBERSETZUNGSFEHLER - Chunk {i+1}: {str(e)[:100]}...]\n\n[ORIGINAL: {chunk[:200]}...]"
                    translated_chunks.append(fallback_chunk)
                    previous_chunk = fallback_chunk
                    print(f"⚠️ Fallback-Chunk für {i+1} erstellt")
                except Exception as fallback_error:
                    print(f"❌ Auch Fallback für Chunk {i+1} fehlgeschlagen: {fallback_error}")
                    # Leeren Chunk hinzufügen um Index zu erhalten
                    translated_chunks.append("")
                    previous_chunk = ""
                
                # Aktualisiere Firestore mit Fehler-Informationen
                job_ref.update({
                    "translation_progress": {
                        "chunks_completed": i + 1,
                        "total_chunks": len(chunks),
                        "last_chunk_completed_at": datetime.datetime.utcnow(),
                        "current_cost_usd": total_cost,
                        "failed_chunks": failed_chunks,
                        "last_error": str(e)
                    }
                })
                
                # Kurze Pause nach Fehlern
                time.sleep(3)

        # 8. Erweiterte Vollständigkeits-Validierung mit Recovery-Option
        print(f"🔍 Validiere Übersetzungs-Vollständigkeit...")
        print(f"📊 Validierungs-Statistiken:")
        print(f"   - Original Chunks: {len(chunks)}")
        print(f"   - Übersetzte Chunks: {len(translated_chunks)}")
        print(f"   - Fehlgeschlagene Chunks: {len(failed_chunks)}")
        print(f"   - Erfolgsrate: {((len(translated_chunks) - len(failed_chunks)) / len(chunks) * 100):.1f}%")
        
        try:
            validate_translation_completeness(chunks, translated_chunks)
        except ValueError as validation_error:
            print(f"❌ Validierung fehlgeschlagen: {validation_error}")
            
            # Prüfe ob wir eine Recovery durchführen können
            if len(translated_chunks) > len(chunks) * 0.5:  # Mindestens 50% erfolgreich
                print(f"🔄 Versuche Recovery für fehlgeschlagene Chunks...")
                
                # Identifiziere fehlende Chunks
                missing_chunks = []
                for i, (orig, trans) in enumerate(zip(chunks, translated_chunks)):
                    if not trans or len(trans.strip()) == 0:
                        missing_chunks.append(i)
                
                print(f"📋 {len(missing_chunks)} Chunks müssen neu übersetzt werden: {missing_chunks}")
                
                # Versuche fehlende Chunks zu übersetzen
                recovery_success = 0
                for missing_idx in missing_chunks:
                    try:
                        print(f"🔄 Recovery: Übersetze Chunk {missing_idx + 1}...")
                        recovered_chunk = translate_chunk_with_context(
                            chunks[missing_idx], 
                            style_guide, 
                            key_terms, 
                            translated_chunks[missing_idx - 1] if missing_idx > 0 else "", 
                            missing_idx, 
                            len(chunks)
                        )
                        translated_chunks[missing_idx] = recovered_chunk
                        recovery_success += 1
                        print(f"✅ Recovery erfolgreich für Chunk {missing_idx + 1}")
                        time.sleep(2)  # Pause zwischen Recovery-Versuchen
                    except Exception as recovery_error:
                        print(f"❌ Recovery fehlgeschlagen für Chunk {missing_idx + 1}: {recovery_error}")
                        # Erstelle Fehler-Chunk
                        translated_chunks[missing_idx] = f"[RECOVERY-FEHLER - Chunk {missing_idx + 1}: {str(recovery_error)[:100]}...]"
                
                print(f"🔄 Recovery abgeschlossen: {recovery_success}/{len(missing_chunks)} Chunks wiederhergestellt")
                
                # Erneute Validierung nach Recovery
                try:
                    validate_translation_completeness(chunks, translated_chunks)
                    print(f"✅ Validierung nach Recovery erfolgreich!")
                except ValueError as recovery_validation_error:
                    print(f"❌ Validierung nach Recovery fehlgeschlagen: {recovery_validation_error}")
                    # Aktualisiere Job-Status mit Recovery-Fehlern
                    job_ref.update({
                        "status": "translation_failed",
                        "error_message": f"Recovery fehlgeschlagen: {recovery_validation_error}",
                        "translation_failed_at": datetime.datetime.utcnow(),
                        "translation_success": False,
                        "validation_failed": True,
                        "recovery_attempted": True,
                        "recovery_success_rate": recovery_success / len(missing_chunks) if missing_chunks else 0,
                        "chunks_original": len(chunks),
                        "chunks_translated": len(translated_chunks),
                        "failed_chunks": failed_chunks
                    })
                    return (f"Recovery Validation Error: {recovery_validation_error}", 500)
            else:
                # Zu wenige erfolgreiche Chunks für Recovery
                print(f"❌ Zu wenige erfolgreiche Chunks ({len(translated_chunks)}/{len(chunks)}) für Recovery")
                job_ref.update({
                    "status": "translation_failed",
                    "error_message": f"Validierung fehlgeschlagen: {validation_error}",
                    "translation_failed_at": datetime.datetime.utcnow(),
                    "translation_success": False,
                    "validation_failed": True,
                    "recovery_attempted": False,
                    "chunks_original": len(chunks),
                    "chunks_translated": len(translated_chunks),
                    "failed_chunks": failed_chunks
                })
                return (f"Validation Error: {validation_error}", 500)

        # 9. Alle übersetzten Chunks zusammenfügen
        final_translated_text = '\n\n'.join(translated_chunks)
        print(f"✅ Alle {len(chunks)} Chunks erfolgreich zusammengefügt")

        # 9. Kosten-Tracking (Schätzung)
        estimated_cost = ((total_input_tokens / 1000000) * PRICE_INPUT_PER_MILLION_TOKENS) + ((total_output_tokens / 1000000) * PRICE_OUTPUT_PER_MILLION_TOKENS)
        print(f"💰 Geschätzte Übersetzungs-Kosten: ${estimated_cost:.4f}")

        # 10. Übersetzten Text in neues .docx-Dokument schreiben
        print(f"📄 Erstelle formatiertes DOCX-Dokument...")
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
        paragraphs = final_translated_text.split('\n')
        for paragraph_text in paragraphs:
            if paragraph_text.strip():
                doc.add_paragraph(paragraph_text)
            else:
                doc.add_paragraph()  # Fügt einen leeren Absatz für die Formatierung hinzu

        print(f"✅ {len(paragraphs)} Absätze verarbeitet")

        # Dokument im Speicher speichern
        doc_stream = io.BytesIO()
        doc.save(doc_stream)
        doc_stream.seek(0)

        # 11. Finales .docx in Cloud Storage hochladen
        print(f"☁️ Lade übersetztes Dokument in Cloud Storage hoch...")
        bucket = storage_client.bucket(BUCKET_NAME)
        
        # Ensure the filename always ends with .docx
        base_name = file_name.rsplit('.', 1)[0] if '.' in file_name else file_name
        docx_filename = f"{base_name}_translated.docx"
        final_blob_name = f"{job_id}/final_translation_{docx_filename}"
        final_blob = bucket.blob(final_blob_name)
        final_blob.upload_from_file(doc_stream, content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

        final_gcs_path = f"gs://{BUCKET_NAME}/{final_blob.name}"
        print(f"✅ Dokument gespeichert: {final_gcs_path}")

        # 12. Job in Firestore als abgeschlossen markieren
        print(f"🎉 Markiere Job als abgeschlossen...")
        
        # Berechne finale Statistiken
        final_stats = {
            "status": "completed",
            "final_gcs_path": final_gcs_path,
            "translation_cost_usd": estimated_cost,
            "translation_completed_at": datetime.datetime.utcnow(),
            "input_tokens_translation": total_input_tokens,
            "output_tokens_translation": total_output_tokens,
            "chunks_processed": len(chunks),
            "chunk_size_used": optimal_chunk_size,
            "translation_success": True,
            "translation_lock": None,  # Lock entfernen
            "kill_switch": False,
            # Zusätzliche Validierungs-Statistiken
            "validation_passed": True,
            "original_text_length": len(full_text),
            "translated_text_length": len(final_translated_text),
            "text_compression_ratio": len(final_translated_text) / len(full_text) if len(full_text) > 0 else 0,
            "chunks_original": len(chunks),
            "chunks_translated": len(translated_chunks),
            "translation_quality_score": "high" if len(final_translated_text) > len(full_text) * 0.5 else "medium"
        }
        
        job_ref.update(final_stats)
        
        print(f"📊 Finale Statistiken:")
        print(f"   - Original: {len(full_text)} Zeichen")
        print(f"   - Übersetzt: {len(final_translated_text)} Zeichen")
        print(f"   - Kompressionsverhältnis: {final_stats['text_compression_ratio']:.2f}")
        print(f"   - Chunks verarbeitet: {len(chunks)}")
        print(f"   - Geschätzte Kosten: ${estimated_cost:.4f}")

        print(f"🎯 Job {job_id} erfolgreich abgeschlossen! {len(chunks)} Chunks verarbeitet.")
        return ("OK", 200)

    except Exception as e:
        # Fehlerbehandlung
        error_message = f"Fehler in der Übersetzungs-Funktion: {e}"
        print(f"❌ {error_message}")

        if job_ref:
            try:
                job_ref.update({
                    "status": "translation_failed",
                    "error_message": str(e),
                    "translation_failed_at": datetime.datetime.utcnow(),
                    "translation_success": False,
                    "translation_lock": None,  # Lock entfernen
                    "kill_switch": False,
                    "final_cost_usd": total_cost
                })
                print(f"✅ Fehler-Status in Firestore gespeichert")
            except Exception as firestore_error:
                print(f"⚠️ Konnte Fehler-Status nicht speichern: {firestore_error}")

        return (f"Error: {e}", 500) 