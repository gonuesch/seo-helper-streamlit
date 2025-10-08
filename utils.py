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
    Teilt einen langen Text in Chunks auf.
    Einfache Implementierung für Gemini 2.5 Flash.
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
            p = sub_text.rfind(delimiter, 0, chunk_size)
            if p != -1:
                break_point = p + len(delimiter)
                break
        
        if break_point == -1:
            break_point = chunk_size
            
        chunks.append(sub_text[:break_point])
        chunk_recursively(sub_text[break_point:])

    chunk_recursively(text)
    return [c for c in chunks if c.strip()]

# Einfache Chunking-Funktion für Gemini 2.5 Flash
# Alle komplexen Funktionen entfernt - zurück zu den Basics