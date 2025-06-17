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