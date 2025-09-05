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
def chunk_text(text: str, chunk_size: int = 8000) -> list[str]:
    """
    Teilt einen langen Text rekursiv in Chunks auf, die die chunk_size
    garantiert nicht überschreiten.
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
def chunk_text_by_paragraphs(text: str, max_chunk_size: int = 8000) -> list[str]:
    """
    Teilt Text intelligent nach Absätzen auf, ideal für Gemini-Verarbeitung.
    Versucht Absätze zusammenzuhalten, solange sie unter der max_chunk_size bleiben.
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
def chunk_ssml_for_elevenlabs(ssml_text: str, max_chunk_size: int = 40000) -> list[str]:
    """
    Teilt SSML-Text für ElevenLabs API auf (40000 Zeichen Limit).
    Versucht SSML-Tags intakt zu halten.
    """
    if not isinstance(ssml_text, str):
        return []
    
    if len(ssml_text) <= max_chunk_size:
        return [ssml_text]
    
    chunks = []
    current_chunk = ""
    
    # Teile SSML in Sätze auf (nach </speak> oder </s> Tags)
    sentences = []
    remaining_text = ssml_text
    
    while remaining_text:
        # Suche nach </speak> oder </s> Tags
        speak_end = remaining_text.find('</speak>')
        s_end = remaining_text.find('</s>')
        
        if speak_end == -1 and s_end == -1:
            # Keine Tags mehr gefunden, füge Rest hinzu
            if remaining_text.strip():
                sentences.append(remaining_text.strip())
            break
        
        # Finde das nächste Ende-Tag
        if speak_end == -1:
            next_end = s_end + 4  # </s> ist 4 Zeichen lang
        elif s_end == -1:
            next_end = speak_end + 8  # </speak> ist 8 Zeichen lang
        else:
            next_end = min(speak_end + 8, s_end + 4)
        
        # Füge Satz hinzu
        sentence = remaining_text[:next_end].strip()
        if sentence:
            sentences.append(sentence)
        
        remaining_text = remaining_text[next_end:]
    
    # Gruppiere Sätze zu Chunks
    for sentence in sentences:
        if current_chunk and len(current_chunk) + len(sentence) + 1 > max_chunk_size:
            chunks.append(current_chunk.strip())
            current_chunk = sentence
        else:
            if current_chunk:
                current_chunk += sentence
            else:
                current_chunk = sentence
    
    # Füge den letzten Chunk hinzu
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    
    return chunks