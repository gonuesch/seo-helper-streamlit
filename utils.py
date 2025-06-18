# utils.py

from PIL import Image
from io import BytesIO
import docx

def convert_tiff_to_png_bytes(tiff_bytes: bytes) -> bytes:
    """Konvertiert eine TIFF-Datei (als Bytes) in PNG-Bytes."""
    pil_image = Image.open(BytesIO(tiff_bytes))
    if getattr(pil_image, "n_frames", 1) > 1:
        pil_image.seek(0)
    if pil_image.mode not in ('RGB', 'RGBA', 'L'):
        pil_image = pil_image.convert('RGB')
    
    output_buffer = BytesIO()
    pil_image.save(output_buffer, format="PNG")
    return output_buffer.getvalue()

def read_text_from_docx(file_object: BytesIO) -> str:
    """Liest den gesamten Text aus einem DOCX-Dokument."""
    doc = docx.Document(file_object)
    full_text = [para.text for para in doc.paragraphs]
    return '\n'.join(full_text)

def chunk_text(text: str, chunk_size: int = 9500) -> list[str]:
    """
    Teilt einen langen Text in kleinere Chunks auf, ohne Sätze zu zerschneiden.
    """
    chunks = []
    current_chunk = ""
    # Teile den Text zuerst in Absätze auf
    paragraphs = text.split('\n')
    
    for paragraph in paragraphs:
        # Wenn der Absatz selbst schon zu groß ist, müssen wir ihn aufteilen
        if len(paragraph) > chunk_size:
            sentences = paragraph.split('.')
            temp_para_chunk = ""
            for sentence in sentences:
                if not sentence: continue
                sentence += "."
                if len(temp_para_chunk) + len(sentence) <= chunk_size:
                    temp_para_chunk += sentence
                else:
                    chunks.append(temp_para_chunk)
                    temp_para_chunk = sentence
            if temp_para_chunk:
                chunks.append(temp_para_chunk)
        else:
            # Füge Absätze zum aktuellen Chunk hinzu, bis er voll ist
            if len(current_chunk) + len(paragraph) + 1 <= chunk_size:
                current_chunk += paragraph + '\n'
            else:
                chunks.append(current_chunk)
                current_chunk = paragraph + '\n'
    
    # Füge den letzten verbleibenden Chunk hinzu
    if current_chunk:
        chunks.append(current_chunk)
        
    return [chunk for chunk in chunks if chunk.strip()]