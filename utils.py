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
def convert_tiff_to_png_bytes(tiff_bytes: bytes) -> bytes:
    pil_image = Image.open(BytesIO(tiff_bytes))
    if getattr(pil_image, "n_frames", 1) > 1:
        pil_image.seek(0)
    if pil_image.mode not in ('RGB', 'RGBA', 'L'):
        pil_image = pil_image.convert('RGB')
    output_buffer = BytesIO()
    pil_image.save(output_buffer, format="PNG")
    return output_buffer.getvalue()

def read_text_from_docx(file_object: BytesIO) -> str:
    doc = docx.Document(file_object)
    full_text = [para.text for para in doc.paragraphs]
    return '\n'.join(full_text)

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
        log_usage("error", "pdf_reading", "exception", {"error_message": str(e)})
        return "" # Im Fehlerfall leeren String zurückgeben


# +++ NEUE, ROBUSTERE CHUNKING-FUNKTION +++
def chunk_text(text: str, chunk_size: int = 9500) -> list[str]:
    """
    Teilt einen langen Text in Chunks auf, die die chunk_size garantiert nicht überschreiten.
    Sucht rückwärts nach dem besten Trennpunkt (Absatz, Satz, Leerzeichen).
    """
    chunks = []
    text_remaining = text
    
    while len(text_remaining) > 0:
        if len(text_remaining) <= chunk_size:
            chunks.append(text_remaining)
            break
            
        # Finde den letzten möglichen Trennpunkt innerhalb des Chunks
        # Wir suchen von hinten nach vorne, um so viel wie möglich in einen Chunk zu bekommen
        chunk_end = text_remaining.rfind('\n', 0, chunk_size)
        if chunk_end == -1:
            chunk_end = text_remaining.rfind('.', 0, chunk_size)
        if chunk_end == -1:
            chunk_end = text_remaining.rfind(' ', 0, chunk_size)
            
        # Wenn gar kein Trennzeichen gefunden wird, machen wir einen harten Schnitt
        # um einen unendlichen Loop zu vermeiden
        if chunk_end == -1:
            chunk_end = chunk_size
            
        # Erstelle den Chunk und aktualisiere den verbleibenden Text
        # Wir nehmen chunk_end + 1, um das Trennzeichen (Punkt, Leerzeichen) mitzunehmen
        chunks.append(text_remaining[:chunk_end + 1])
        text_remaining = text_remaining[chunk_end + 1:]
        
    return [c for c in chunks if c.strip()]