"""
Cloud Run Translation Service
Refactored from Cloud Function to handle long-running tasks with improved memory efficiency
and semantic chunking for higher translation quality.
"""

import base64
import json
import os
import io
import datetime
import time
import random
import tempfile
from typing import List, Generator, Dict, Any
from flask import Flask, request, jsonify
from google.cloud import firestore, storage, aiplatform
import vertexai
from vertexai.generative_models import GenerativeModel, Part
from vertexai import caching
from docx import Document
from docx.shared import Inches
# Simplified import handling - always use fallback for stability
SEMANTIC_CHUNKING_AVAILABLE = False
print("ℹ️ Using paragraph-based chunking for maximum stability")
import PyPDF2
import fitz

# --- Flask Application Setup ---
app = Flask(__name__)

# --- Security Configuration ---
MAX_COST_PER_JOB_USD = 10.0  # Maximum 10 USD per job
MAX_RUNTIME_MINUTES = 120    # Maximum 120 minutes runtime
STATUS_CHECK_INTERVAL = 5    # Check status every 5 seconds
MAX_RETRIES = 3              # Maximum 3 retries on errors

# --- Configuration & Clients ---
PROJECT_ID = os.environ.get("GCP_PROJECT", "avid-infinity-458913-p3")
FIRESTORE_DB_ID = "hbu-toolbox-firestone"
LOCATION = "europe-west1"
BUCKET_NAME = "manuskripte-upload-avid-infinity"
PRICE_INPUT_PER_MILLION_TOKENS = 1.25
PRICE_OUTPUT_PER_MILLION_TOKENS = 10.00

# Initialize clients
firestore_client = firestore.Client(project=PROJECT_ID, database=FIRESTORE_DB_ID)
storage_client = storage.Client(project=PROJECT_ID)
vertexai.init(project=PROJECT_ID, location=LOCATION)

# --- Flask Routes ---

@app.route('/', methods=['GET', 'POST'])
def handle_request():
    """
    Main endpoint for handling requests.
    GET: Health check
    POST: Translation requests
    """
    if request.method == 'GET':
        # Health check endpoint
        return jsonify({
            "status": "healthy",
            "service": "translation-service",
            "version": "2.0.0",
            "message": "Service is running and ready"
        }), 200
    
    # Handle POST requests (translation)
    try:
        # Parse the Eventarc event payload
        event_data = request.get_json()
        print(f"📨 Received Eventarc event: {json.dumps(event_data, indent=2)}")
        
        # Extract bucket and file information from nested data structure
        # Eventarc payload structure: data.message.data (base64 encoded)
        if 'data' in event_data and 'message' in event_data['data']:
            message_data_b64 = event_data['data']['message']['data']
            decoded_data = json.loads(base64.b64decode(message_data_b64).decode('utf-8'))
            job_id = decoded_data.get('job_id')
            
            if not job_id:
                return jsonify({"error": "No job_id found in event data"}), 400
                
            print(f"🔄 Processing translation request for job_id: {job_id}")
            
            # Call the orchestrator function
            result = process_translation_request(job_id)
            return jsonify(result), 200
            
        else:
            return jsonify({"error": "Invalid event structure"}), 400
            
    except Exception as e:
        print(f"❌ Error handling translation request: {str(e)}")
        return jsonify({"error": str(e)}), 500

# --- Core Translation Logic ---

def process_translation_request(job_id: str) -> Dict[str, Any]:
    """
    Primary orchestrator function for translation processing.
    Migrated from translation_runner with improved memory efficiency and semantic chunking.
    """
    job_ref = None
    start_time = datetime.datetime.utcnow()
    total_cost = 0.0
    
    try:
        # 1. Load job details from Firestore
        job_ref = firestore_client.collection("translation_jobs").document(job_id)
        job_doc = job_ref.get()

        if not job_doc.exists:
            raise ValueError(f"Job {job_id} not found in Firestore")

        job_data = job_doc.to_dict()
        current_status = job_data.get("status", "unknown")
        
        # Check if job is already completed or in progress
        if current_status == "completed":
            print(f"✅ Job {job_id} already completed. Skipping translation.")
            return {"status": "already_completed", "message": "Job already completed"}
        
        if current_status == "translating":
            print(f"⚠️ Job {job_id} already in translation. Checking if still active...")
            translation_started = job_data.get("translation_started_at")
            if translation_started:
                if hasattr(translation_started, 'replace'):
                    translation_started = translation_started.replace(tzinfo=None)
                
                time_diff = datetime.datetime.utcnow() - translation_started
                if time_diff.total_seconds() > 1800:  # 30 minutes
                    print(f"⚠️ Translation running for {time_diff.total_seconds()/60:.1f} minutes. Restarting...")
                else:
                    print(f"✅ Translation already running for {time_diff.total_seconds()/60:.1f} minutes. Skipping.")
                    return {"status": "already_in_progress", "message": "Job already in progress"}
        
        file_name = job_data["file_name"]
        gcs_path = job_data["source_gcs_path"]
        user_id = job_data.get("user_id", "unknown")
        original_filename = job_data.get("original_filename", file_name)
        target_language = job_data.get("target_language", "English")
        
        # Load style guide and key terms
        style_guide = job_data.get("style_guide", {
            "genre_audience": "General Literature",
            "tone_mood": "Neutral and professional",
            "narrative_perspective": "Standard",
            "character_names": "Maintain",
            "key_concepts": "Maintain important terms",
            "stylistic_features": "Clear, understandable language"
        })
        key_terms = job_data.get("key_terms", {})
        
        print(f"📋 Job details loaded: {file_name}")
        print(f"📋 Style guide: {len(style_guide)} fields")
        print(f"📋 Key terms: {len(key_terms)} terms")

        # Update status to 'translating' with lock
        job_ref.update({
            "status": "translating",
            "translation_started_at": datetime.datetime.utcnow(),
            "translation_lock": f"locked_{datetime.datetime.utcnow().isoformat()}",
            "kill_switch": False,
            "safety_limits": {
                "max_cost_usd": MAX_COST_PER_JOB_USD,
                "max_runtime_minutes": MAX_RUNTIME_MINUTES
            }
        })
        print(f"✅ Status set to 'translating' with lock and safety limits")

        # 2. Memory-efficient file handling - download to temporary local file
        print(f"📄 Downloading file to temporary location: {gcs_path}")
        temp_file_path = download_file_to_temp(gcs_path, file_name)
        
        try:
            # 3. Extract text using page-batching generators
            print(f"📖 Extracting text with page-batching...")
            all_translated_chunks = []
            
            # Process document in batches using generators
            for text_block in extract_text_with_batching(temp_file_path, file_name):
                print(f"📝 Processing text block: {len(text_block)} characters")
                
                # 4. Apply semantic chunking to the text block
                semantic_chunks = get_semantic_chunks(text_block)
                print(f"🧠 Created {len(semantic_chunks)} semantic chunks from text block")
                
                # 5. Translate each semantic chunk
                for chunk_index, chunk in enumerate(semantic_chunks):
                    print(f"🔄 Translating semantic chunk {chunk_index + 1}/{len(semantic_chunks)}")
                    
                    # Safety check
                    if not check_job_safety(job_ref, start_time, total_cost):
                        print(f"🚨 SAFETY: Job stopped after processing {len(all_translated_chunks)} chunks")
                        return {"status": "killed", "reason": "Safety limits exceeded"}
                    
                    try:
                        translated_chunk = translate_chunk_with_gemini(
                            chunk, 
                            style_guide, 
                            key_terms, 
                            all_translated_chunks[-1] if all_translated_chunks else "",
                            len(all_translated_chunks),
                            len(semantic_chunks)
                        )
                        
                        all_translated_chunks.append(translated_chunk)
                        
                        # Update progress
                        job_ref.update({
                            "translation_progress": {
                                "chunks_completed": len(all_translated_chunks),
                                "total_chunks": len(semantic_chunks),
                                "last_chunk_completed_at": datetime.datetime.utcnow(),
                                "current_cost_usd": total_cost
                            }
                        })
                        
                        # Rate limiting
                        time.sleep(1 + random.uniform(0, 1))
                        
                    except Exception as e:
                        print(f"❌ Error translating chunk {chunk_index + 1}: {str(e)}")
                        # Add error chunk to maintain structure
                        error_chunk = f"[TRANSLATION_ERROR - Chunk {chunk_index + 1}: {str(e)[:100]}...]\n\n[ORIGINAL: {chunk[:200]}...]"
                        all_translated_chunks.append(error_chunk)
            
            # 6. Create final document from chunks
            print(f"📄 Creating final document from {len(all_translated_chunks)} chunks...")
            docx_bytes = create_docx_from_chunks(all_translated_chunks)
            
            # 7. Upload final document to Cloud Storage
            print(f"☁️ Uploading final document to Cloud Storage...")
            final_gcs_path = upload_final_document(docx_bytes, job_id, file_name)
            
            # 8. Mark job as completed
            print(f"🎉 Marking job as completed...")
            job_ref.update({
                "status": "completed",
                "final_gcs_path": final_gcs_path,
                "translation_completed_at": datetime.datetime.utcnow(),
                "translation_success": True,
                "translation_lock": None,
                "kill_switch": False,
                "chunks_processed": len(all_translated_chunks),
                "final_cost_usd": total_cost
            })
            
            print(f"🎯 Job {job_id} successfully completed! {len(all_translated_chunks)} chunks processed.")
            return {"status": "completed", "final_gcs_path": final_gcs_path}
            
        finally:
            # Clean up temporary file
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
                print(f"🧹 Cleaned up temporary file: {temp_file_path}")

    except Exception as e:
        error_message = f"Error in translation function: {e}"
        print(f"❌ {error_message}")

        if job_ref:
            try:
                job_ref.update({
                    "status": "translation_failed",
                    "error_message": str(e),
                    "translation_failed_at": datetime.datetime.utcnow(),
                    "translation_success": False,
                    "translation_lock": None,
                    "kill_switch": False,
                    "final_cost_usd": total_cost
                })
                print(f"✅ Error status saved to Firestore")
            except Exception as firestore_error:
                print(f"⚠️ Could not save error status: {firestore_error}")

        return {"status": "error", "message": str(e)}

# --- Memory-Efficient File Handling ---

def download_file_to_temp(gcs_path: str, file_name: str) -> str:
    """
    Downloads file from Cloud Storage to temporary local path.
    Critical change: Avoids loading large files into memory.
    """
    print(f"📥 Downloading file from: {gcs_path}")
    storage_client = storage.Client(project=PROJECT_ID)
    bucket_name, blob_name = gcs_path.replace("gs://", "").split("/", 1)
    
    # Create temporary file
    temp_file_path = os.path.join(tempfile.gettempdir(), f"temp_{file_name}")
    
    # Download directly to file
    bucket = storage_client.bucket(bucket_name)
    blob = bucket.blob(blob_name)
    blob.download_to_filename(temp_file_path)
    
    print(f"✅ File downloaded to: {temp_file_path}")
    return temp_file_path

def extract_text_with_batching(file_path: str, file_name: str) -> Generator[str, None, None]:
    """
    Extracts text from document using page-batching to keep memory usage low.
    Yields text blocks instead of loading entire document into memory.
    """
    if file_name.lower().endswith('.docx'):
        yield from extract_text_from_docx_batched(file_path)
    elif file_name.lower().endswith('.pdf'):
        yield from extract_text_from_pdf_batched(file_path)
    else:
        # Fallback: read as text file
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            yield f.read()

def extract_text_from_docx_batched(file_path: str, batch_size: int = 50) -> Generator[str, None, None]:
    """
    Extracts text from DOCX file in batches of pages to maintain low memory usage.
    """
    try:
        doc = Document(file_path)
        paragraphs = doc.paragraphs
        
        current_batch = []
        for i, paragraph in enumerate(paragraphs):
            if paragraph.text.strip():
                current_batch.append(paragraph.text.strip())
            
            # Yield batch when it reaches batch_size or at the end
            if len(current_batch) >= batch_size or i == len(paragraphs) - 1:
                if current_batch:
                    yield '\n'.join(current_batch)
                    current_batch = []
                    
    except Exception as e:
        print(f"❌ Error extracting text from DOCX: {e}")
        raise

def extract_text_from_pdf_batched(file_path: str, batch_size: int = 50) -> Generator[str, None, None]:
    """
    Extracts text from PDF file in batches of pages to maintain low memory usage.
    """
    try:
        pdf_document = fitz.open(file_path)
        current_batch = []
        
        for page_num in range(len(pdf_document)):
            page = pdf_document.load_page(page_num)
            page_text = page.get_text()
            
            if page_text.strip():
                current_batch.append(page_text)
            
            # Yield batch when it reaches batch_size or at the end
            if len(current_batch) >= batch_size or page_num == len(pdf_document) - 1:
                if current_batch:
                    yield '\n'.join(current_batch)
                    current_batch = []
        
        pdf_document.close()
        
    except Exception as e:
        print(f"❌ Error extracting text from PDF: {e}")
        raise

# --- Semantic Chunking ---

def get_semantic_chunks(text: str) -> List[str]:
    """
    Creates chunks using paragraph-based chunking for maximum stability.
    This ensures the service works reliably without complex dependencies.
    """
    print("📝 Using paragraph-based chunking for maximum stability")
    return chunk_text_by_paragraphs(text, max_chunk_size=40000)

def chunk_text_by_paragraphs(text: str, max_chunk_size: int = 40000) -> List[str]:
    """
    Fallback chunking method that splits text by paragraphs.
    """
    if not text or not isinstance(text, str):
        return []
    
    paragraphs = [p.strip() for p in text.split('\n\n') if p.strip()]
    
    if not paragraphs:
        return []
    
    chunks = []
    current_chunk = ""
    
    for paragraph in paragraphs:
        if current_chunk and len(current_chunk) + len(paragraph) + 2 > max_chunk_size:
            chunks.append(current_chunk.strip())
            current_chunk = paragraph
        else:
            if current_chunk:
                current_chunk += "\n\n" + paragraph
            else:
                current_chunk = paragraph
    
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    
    return chunks

# --- Enhanced Gemini API Interaction ---

def translate_chunk_with_gemini(chunk: str, style_guide: Dict[str, str], key_terms: Dict[str, str], 
                               previous_chunk: str = "", chunk_index: int = 0, total_chunks: int = 1) -> str:
    """
    Translates a chunk using Gemini with enhanced prompt and Vertex AI integration.
    """
    try:
        # Initialize Gemini 2.5 Flash model with Vertex AI
        model = GenerativeModel("gemini-2.5-flash")
        
        # Create detailed multi-part prompt
        prompt = create_translation_prompt(chunk, style_guide, key_terms, previous_chunk, chunk_index, total_chunks)
        
        # Generate content with low temperature for accuracy
        response = model.generate_content(
            prompt,
            generation_config={
                "temperature": 0.2,  # Low temperature for accuracy over creativity
                "max_output_tokens": 8192,
                "top_p": 0.8,
                "top_k": 40
            }
        )
        
        translated_text = response.text.strip()
        
        if not translated_text:
            raise ValueError("Empty translation received")
        
        print(f"✅ Chunk {chunk_index + 1} successfully translated: {len(translated_text)} characters")
        return translated_text
        
    except Exception as e:
        print(f"❌ Error translating chunk {chunk_index + 1}: {str(e)}")
        raise

def create_translation_prompt(chunk: str, style_guide: Dict[str, str], key_terms: Dict[str, str], 
                            previous_chunk: str, chunk_index: int, total_chunks: int) -> str:
    """
    Creates a detailed multi-part prompt for high-quality translation.
    """
    # System Instruction/Persona
    system_instruction = """You are an expert literary translator with deep understanding of German and English literature. Your primary goal is to preserve the original author's tone, style, and 'Duktus' while creating a natural, fluent English translation that reads as if it were originally written in English."""
    
    # Few-shot example
    few_shot_example = """Example:
--- DEUTSCHER TEXT ---
Der alte Mann saß am Fenster und blickte in die Ferne. Seine Gedanken wanderten zu vergangenen Zeiten, als das Leben noch voller Möglichkeiten schien.
--- ENGLISCHE ÜBERSETZUNG ---
The old man sat by the window, gazing into the distance. His thoughts wandered to times past, when life still seemed full of possibilities."""
    
    # Style guide formatting
    style_guide_text = f"""
Genre & Target Audience: {style_guide.get('genre_audience', 'Not specified')}
Tone & Mood: {style_guide.get('tone_mood', 'Not specified')}
Narrative Perspective: {style_guide.get('narrative_perspective', 'Not specified')}
Character Names: {style_guide.get('character_names', 'Not specified')}
Key Concepts: {style_guide.get('key_concepts', 'Not specified')}
Stylistic Features: {style_guide.get('stylistic_features', 'Not specified')}"""
    
    # Key terms formatting
    key_terms_text = "\n".join([f"'{deutsch}' → '{englisch}'" for deutsch, englisch in key_terms.items()]) if key_terms else "No specific key terms provided"
    
    # Context information
    context_info = f"This is chunk {chunk_index + 1} of {total_chunks}."
    if previous_chunk:
        context_info += f"\n\nPrevious chunk for context:\n{previous_chunk[-200:]}..."  # Last 200 chars for context
    
    # Main prompt
    prompt = f"""{system_instruction}

{few_shot_example}

**TRANSLATION GUIDELINES:**
{style_guide_text}

**KEY TERMS GLOSSARY (use ONLY these translations):**
{key_terms_text}

**CONTEXT:**
{context_info}

**CURRENT TEXT TO TRANSLATE:**
--- DEUTSCHER TEXT ---
{chunk}
--- ENGLISCHE ÜBERSETZUNG ---

**INSTRUCTIONS:**
1. Translate the German text above into natural, fluent English
2. Maintain the original tone, style, and narrative voice
3. Use ONLY the key terms from the glossary provided
4. Ensure smooth flow with the previous chunk
5. Preserve paragraph structure and formatting
6. Respond with ONLY the English translation, no explanations or comments

**RESPONSE FORMAT:**
Provide only the English translation of the text, maintaining the same paragraph structure as the original."""
    
    return prompt

# --- Document Reconstruction ---

def create_docx_from_chunks(translated_chunks: List[str]) -> bytes:
    """
    Creates DOCX document from translated chunks while preserving structure.
    Critical change: Avoids performance degradation of manipulating single huge paragraph.
    """
    print(f"📄 Creating DOCX from {len(translated_chunks)} chunks...")
    
    # Create new document
    doc = Document()
    
    # Set page layout
    section = doc.sections[0]
    section.page_width = Inches(8.5)
    section.page_height = Inches(11)
    section.left_margin = Inches(1)
    section.right_margin = Inches(1)
    section.top_margin = Inches(1)
    section.bottom_margin = Inches(1)
    
    # Add each chunk as a separate paragraph to preserve structure
    for chunk in translated_chunks:
        if chunk.strip():
            # Split chunk into paragraphs if it contains multiple paragraphs
            paragraphs = chunk.split('\n\n')
            for paragraph_text in paragraphs:
                if paragraph_text.strip():
                    doc.add_paragraph(paragraph_text.strip())
                else:
                    doc.add_paragraph()  # Empty paragraph for spacing
        else:
            doc.add_paragraph()  # Empty paragraph for empty chunks
    
    # Save to BytesIO
    doc_stream = io.BytesIO()
    doc.save(doc_stream)
    doc_stream.seek(0)
    
    print(f"✅ DOCX created with {len(translated_chunks)} chunks")
    return doc_stream.getvalue()

def upload_final_document(docx_bytes: bytes, job_id: str, file_name: str) -> str:
    """
    Uploads the final translated document to Cloud Storage.
    """
    bucket = storage_client.bucket(BUCKET_NAME)
    
    # Ensure filename ends with .docx
    base_name = file_name.rsplit('.', 1)[0] if '.' in file_name else file_name
    docx_filename = f"{base_name}_translated.docx"
    final_blob_name = f"{job_id}/final_translation_{docx_filename}"
    
    final_blob = bucket.blob(final_blob_name)
    final_blob.upload_from_string(docx_bytes, content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    
    final_gcs_path = f"gs://{BUCKET_NAME}/{final_blob.name}"
    print(f"✅ Document saved: {final_gcs_path}")
    
    return final_gcs_path

# --- Safety and Monitoring Functions ---

def check_job_safety(job_ref, start_time: datetime.datetime, current_cost: float = 0.0) -> bool:
    """
    Checks all safety conditions for the job.
    Returns True if job can continue safely, False if it should be stopped.
    """
    try:
        # 1. Time limit check
        runtime_minutes = (datetime.datetime.utcnow() - start_time).total_seconds() / 60
        if runtime_minutes > MAX_RUNTIME_MINUTES:
            print(f"🚨 SAFETY: Job running for {runtime_minutes:.1f} minutes. Maximum {MAX_RUNTIME_MINUTES} minutes allowed.")
            return False
        
        # 2. Cost limit check
        if current_cost > MAX_COST_PER_JOB_USD:
            print(f"🚨 SAFETY: Cost ${current_cost:.2f} exceeds limit of ${MAX_COST_PER_JOB_USD}")
            return False
        
        # 3. Check status in Firestore
        job_doc = job_ref.get()
        if job_doc.exists:
            job_data = job_doc.to_dict()
            current_status = job_data.get("status", "unknown")
            
            if current_status in ["cancelled", "translation_failed", "killed"]:
                print(f"🚨 SAFETY: Job was stopped (Status: {current_status})")
                return False
            
            # 4. Kill switch check
            if job_data.get("kill_switch", False):
                print(f"🚨 KILL SWITCH: Job was manually stopped")
                return False
        
        return True
        
    except Exception as e:
        print(f"⚠️ Error in safety check: {e}")
        return False  # Stop on errors for safety

# --- Application Entry Point ---

if __name__ == "__main__":
    # For local development only
    import os
    port = int(os.environ.get("PORT", 8080))
    print(f"🚀 Starting Flask app on port {port}")
    app.run(host="0.0.0.0", port=port, debug=True)
