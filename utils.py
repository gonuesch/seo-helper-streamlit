# utils.py

from PIL import Image
from io import BytesIO
import docx
import fitz
import json
import csv
from datetime import datetime
import os
import threading
import logging
import functools
from google.cloud import storage

def log_exceptions(func):
    """
    Ein Decorator, der automatisch alle Ausnahmen innerhalb einer Funktion
    abfängt, sie loggt und dann weiter auslöst.
    """
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            # Loggt die Ausnahme mit vollständigem Traceback
            logging.exception("In Funktion '%s' ist ein Fehler aufgetreten", func.__name__)
            # Löst die Ausnahme erneut aus, damit die aufrufende Funktion
            # sie optional behandeln kann (z.B. mit st.error).
            raise
    return wrapper

# --- GCS Helper Functions ---

@log_exceptions
def upload_to_gcs(bucket_name: str, source_file_name: str, destination_blob_name: str):
    """Uploads a file to the bucket."""
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(destination_blob_name)

    blob.upload_from_filename(source_file_name)

    logging.info(f"File {source_file_name} uploaded to {destination_blob_name}.")
    return f"gs://{bucket_name}/{destination_blob_name}"

@log_exceptions
def download_from_gcs(bucket_name: str, source_blob_name: str) -> bytes:
    """Downloads a file from the bucket and returns its content as bytes."""
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(source_blob_name)
    
    return blob.download_as_bytes()


# --- LOGGING FUNKTION (unverändert) ---
log_lock = threading.Lock()
LOG_FILE = "usage_log.csv"

def log_usage(user_email: str, feature: str, action: str, details: dict = None):
    timestamp = datetime.now().isoformat()
    details_str = json.dumps(details) if details else ""
    log_entry = [timestamp, user_email, feature, action, details_str]
    with log_lock:
        file_exists = os.path.isfile(LOG_FILE)
        with open(LOG_FILE, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(["timestamp", "user_email", "feature", "action", "details"])
            writer.writerow(log_entry)


# --- BILD- & DOKUMENTEN-FUNKTIONEN (unverändert) ---
@log_exceptions
def convert_tiff_to_png_bytes(tiff_bytes: bytes) -> bytes:
    pil_image = Image.open(BytesIO(tiff_bytes))
    if getattr(pil_image, "n_frames", 1) > 1:
        pil_image.seek(0)
    if pil_image.mode not in ('RGB', 'RGBA', 'L'):
        pil_image = pil_image.convert('RGB')
    output_buffer = BytesIO()
    pil_image.save(output_buffer, format="PNG")
    return output_buffer.getvalue()

@log_exceptions
def read_text_from_docx(file_object: BytesIO) -> str:
    doc = docx.Document(file_object)
    full_text = [para.text for para in doc.paragraphs]
    return '\n'.join(full_text)

@log_exceptions
def read_text_from_pdf(file_object: BytesIO) -> str:
    try:
        pdf_document = fitz.open(stream=file_object.read(), filetype="pdf")
        full_text = ""
        for page_num in range(len(pdf_document)):
            page = pdf_document.load_page(page_num)
            full_text += page.get_text()
        if not full_text.strip():
            return "NO_TEXT_IN_PDF"
        return full_text
    except Exception as e:
        logging.error("Fehler beim Lesen der PDF-Datei: %s", str(e))
        return ""

@log_exceptions
def chunk_text(text: str, chunk_size: int = 40000) -> list[str]:
    """
    Teilt einen langen Text rekursiv in Chunks auf, die die chunk_size
    garantiert nicht überschreiten.
    
    Optimiert für Gemini 2.5 Flash:
    - Input: 1M Tokens (~800K Zeichen)
    - Output: 65K Tokens (~50K Zeichen)
    - Sicherer Chunk: 40K Zeichen Input → ~44K Zeichen Output
    """
    if not isinstance(text, str):
        return []
        
    chunks = []
    
    def chunk_recursively(sub_text):
        if len(sub_text) <= chunk_size:
            if sub_text.strip():
                chunks.append(sub_text)
            return

        # Finde den besten möglichen Trennpunkt von hinten
        break_point = -1
        for delimiter in ['\n\n', '.', ' ']:
            # rfind gibt den letzten Index des Delimiters vor dem Ende zurück
            p = sub_text.rfind(delimiter, 0, chunk_size)
            if p != -1:
                break_point = p + len(delimiter)
                break
        
        # Wenn gar kein Trennzeichen gefunden wird, mache einen harten Schnitt
        if break_point == -1:
            break_point = chunk_size
            
        # Füge den Chunk hinzu und verarbeite den Rest rekursiv
        chunks.append(sub_text[:break_point])
        chunk_recursively(sub_text[break_point:])

    chunk_recursively(text)
    return [c for c in chunks if c.strip()]

@log_exceptions
def chunk_text_by_paragraphs(text: str, max_chunk_size: int = 40000) -> list[str]:
    """
    Teilt Text intelligent nach Absätzen auf, optimiert für Gemini 2.5 Flash.
    - Input Limit: 1M Tokens (~800K Zeichen)
    - Output Limit: 65K Tokens (~50K Zeichen)
    - Sicherer Chunk: 40K Zeichen Input → ~44K Zeichen Output
    """
    if not isinstance(text, str):
        return []
    
    # Teile Text in Absätze auf
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    
    if not paragraphs:
        return []
    
    chunks = []
    current_chunk = ""
    
    for paragraph in paragraphs:
        # Wenn der aktuelle Chunk + neuer Absatz zu groß wäre
        if current_chunk and len(current_chunk) + len(paragraph) + 2 > max_chunk_size:
            # Speichere den aktuellen Chunk
            chunks.append(current_chunk.strip())
            current_chunk = paragraph
        else:
            # Füge Absatz zum aktuellen Chunk hinzu
            if current_chunk:
                current_chunk += "\n\n" + paragraph
            else:
                current_chunk = paragraph
    
    # Füge den letzten Chunk hinzu
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    
    return chunks

@log_exceptions
def estimate_translation_output_size(german_text: str) -> int:
    """
    Schätzt die Größe der englischen Übersetzung basierend auf dem deutschen Text.
    Deutsche Texte sind typischerweise 10-15% kürzer als englische Übersetzungen.
    """
    if not isinstance(german_text, str):
        return 0
    
    # Deutsche Texte sind ~10-15% kürzer als englische Übersetzungen
    estimated_output_size = int(len(german_text) * 1.12)  # 12% länger
    return estimated_output_size

@log_exceptions
def is_safe_for_gemini_flash_output(german_text: str) -> bool:
    """
    Prüft, ob der deutsche Text sicher für Gemini 2.5 Flash übersetzt werden kann.
    Output-Limit: 65K Tokens (~50K Zeichen)
    """
    estimated_output = estimate_translation_output_size(german_text)
    max_safe_output = 45000  # 45K Zeichen (sicher unter 50K)
    
    return estimated_output <= max_safe_output

@log_exceptions
def chunk_text_for_gemini_flash(text: str) -> list[str]:
    """
    Intelligente Chunking-Strategie für Gemini 2.5 Flash.
    Berücksichtigt sowohl Input- als auch Output-Limits.
    """
    if not isinstance(text, str):
        return []
    
    # Maximaler sicherer Input für Gemini 2.5 Flash
    max_input_chars = 40000  # 40K Zeichen Input
    chunks = []
    
    def chunk_recursively(sub_text):
        if len(sub_text) <= max_input_chars:
            # Prüfe Output-Limit
            if is_safe_for_gemini_flash_output(sub_text):
                chunks.append(sub_text)
            else:
                # Text ist zu groß für Output-Limit, weiter aufteilen
                mid_point = len(sub_text) // 2
                # Finde besseren Trennpunkt
                for delimiter in ['\n\n', '.', ' ']:
                    break_point = sub_text.rfind(delimiter, 0, mid_point)
                    if break_point != -1:
                        chunk_recursively(sub_text[:break_point + len(delimiter)])
                        chunk_recursively(sub_text[break_point + len(delimiter):])
                        return
                # Fallback: harte Teilung
                chunk_recursively(sub_text[:mid_point])
                chunk_recursively(sub_text[mid_point:])
            return
        
        # Finde besten Trennpunkt
        break_point = -1
        for delimiter in ['\n\n', '.', ' ']:
            p = sub_text.rfind(delimiter, 0, max_input_chars)
            if p != -1:
                break_point = p + len(delimiter)
                break
        
        if break_point == -1:
            break_point = max_input_chars
            
        chunk_recursively(sub_text[:break_point])
        chunk_recursively(sub_text[break_point:])
    
    chunk_recursively(text)
    return [c for c in chunks if c.strip()]