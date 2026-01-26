# api/index.py
"""
Main API endpoint for Vercel serverless deployment
Handles voice-to-text transcription and LangChain Tool-Calling RAG answering
"""
import os
import sys
import tempfile
import base64
import numpy as np
from typing import Optional, Tuple

from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv
import soundfile as sf

# Load environment variables
load_dotenv()

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

from speech.stt_whisper import WhisperSTT
from speech.tts_edge import tts_mp3_bytes
from rag.agent import answer_question

# -----------------------------------------------------------------------------
# FastAPI app
# -----------------------------------------------------------------------------
app = FastAPI(title="Sunmarke Voice RAG API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: lock down in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files (for local development)
if os.path.exists(os.path.join(PROJECT_ROOT, "public")):
    app.mount("/static", StaticFiles(directory=os.path.join(PROJECT_ROOT, "public")), name="static")

# -----------------------------------------------------------------------------
# Serverless singletons (reused across warm invocations)
# -----------------------------------------------------------------------------
_stt: Optional[WhisperSTT] = None


def get_stt() -> WhisperSTT:
    global _stt
    if _stt is None:
        _stt = WhisperSTT()
    return _stt


# -----------------------------------------------------------------------------
# Response models
# -----------------------------------------------------------------------------
class TranscriptionResponse(BaseModel):
    text: str
    duration: float
    success: bool
    message: str


class AnswerResponse(BaseModel):
    answer: str
    audio_base64: Optional[str] = None
    success: bool
    message: str
    metas: Optional[list] = None
    context: Optional[str] = None


class AskRequest(BaseModel):
    query: str


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
def validate_audio_length(audio_data: np.ndarray, sr: int, max_seconds: int = 30) -> Tuple[bool, str, float, np.ndarray]:
    """
    Validates audio length and returns:
      (is_valid, message, duration_seconds, mono_audio)
    """
    if audio_data is None or len(audio_data) == 0:
        return False, "No audio data", 0.0, audio_data

    # Convert stereo -> mono
    if audio_data.ndim == 2:
        audio_data = audio_data[:, 0]

    duration = float(len(audio_data) / float(sr)) if sr else 0.0

    if duration > max_seconds:
        return False, f"Audio too long: {duration:.1f}s (max {max_seconds}s)", duration, audio_data

    return True, f"Audio duration: {duration:.1f}s", duration, audio_data


def float_to_int16(audio: np.ndarray) -> np.ndarray:
    """Convert float audio [-1,1] to int16."""
    if audio.dtype == np.int16:
        return audio
    audio = np.clip(audio, -1.0, 1.0)
    return (audio * 32767.0).astype(np.int16)


def build_tts_base64(text: str) -> Optional[str]:
    """Generate MP3 bytes and return base64 string (or None on failure)."""
    try:
        audio_bytes = tts_mp3_bytes(text)
        return base64.b64encode(audio_bytes).decode("utf-8")
    except Exception as e:
        print(f"TTS error: {e}")
        return None


def answer_for_query(query: str) -> AnswerResponse:
    """
    Runs the LangChain tool-calling RAG pipeline and returns AnswerResponse.
    """
    query = (query or "").strip()
    if not query:
        return AnswerResponse(
            answer="",
            audio_base64=None,
            success=False,
            message="Empty query",
            metas=None,
            context=None,
        )

    try:
        # Call the RAG agent
        result = answer_question(query)
        
        # Remove debug prints for production
        # print(f"DEBUG: result type = {type(result)}")
        # print(f"DEBUG: result = {result}")
        
        if not isinstance(result, dict):
            return AnswerResponse(
                answer="",
                audio_base64=None,
                success=False,
                message=f"Invalid response format",
                metas=None,
                context=None,
            )
        
        answer = result.get("answer", "")
        
        if not isinstance(answer, str):
            answer = str(answer)
        
        answer = answer.strip()
        metas = result.get("metas", [])
        context = result.get("context", "")

        if not answer:
            answer = "I'm sorry, but I don't have that information available in the provided Sunmarke website content."

        # Generate TTS audio
        audio_b64 = build_tts_base64(answer)

        return AnswerResponse(
            answer=answer,
            audio_base64=audio_b64,
            success=True,
            message="Answer generated successfully",
            metas=metas,
            context=context,
        )

    except Exception as e:
        import traceback
        print("Ask error:", traceback.format_exc())
        return AnswerResponse(
            answer="",
            audio_base64=None,
            success=False,
            message=f"Error: {str(e)}",
            metas=None,
            context=None,
        )


# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the main HTML interface"""
    html_path = os.path.join(PROJECT_ROOT, "public", "index.html")
    
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    else:
        return HTMLResponse(content="""
        <html>
            <body>
                <h1>Sunmarke Voice RAG API</h1>
                <p>HTML file not found. Please create public/index.html</p>
                <p>Available endpoints:</p>
                <ul>
                    <li>POST /transcribe - Transcribe audio to text</li>
                    <li>POST /ask - Ask a question (text)</li>
                    <li>POST /process - Full voice pipeline</li>
                    <li>GET /health - Health check</li>
                </ul>
            </body>
        </html>
        """)


@app.get("/health")
async def health_check():
    """Health check endpoint for monitoring"""
    return {
        "status": "healthy",
        "embeddings": "Cohere",
        "llm": "Gemini",
        "stt": "Groq Whisper",
        "tts": "gTTS"
    }


@app.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(audio_file: UploadFile = File(...)):
    """
    Transcribe audio using Groq Whisper API.
    Expects WAV (or any soundfile-readable format). Returns transcription text.
    """
    temp_path = None

    try:
        audio_bytes = await audio_file.read()
        if not audio_bytes:
            return TranscriptionResponse(
                text="",
                duration=0.0,
                success=False,
                message="Empty audio file",
            )

        # Save to temp file for soundfile
        temp_path = tempfile.mktemp(suffix=".wav")
        with open(temp_path, "wb") as f:
            f.write(audio_bytes)

        try:
            audio_data, sr = sf.read(temp_path)
        except Exception as e:
            return TranscriptionResponse(
                text="",
                duration=0.0,
                success=False,
                message=f"Could not read audio file: {str(e)}",
            )

        is_valid, msg, duration, mono = validate_audio_length(audio_data, sr, max_seconds=30)
        if not is_valid:
            return TranscriptionResponse(
                text="",
                duration=duration,
                success=False,
                message=msg,
            )

        audio_int16 = float_to_int16(mono)

        # Silence check
        rms = float(np.sqrt(np.mean(audio_int16.astype(np.float32) ** 2)))
        if rms < 100:
            return TranscriptionResponse(
                text="",
                duration=duration,
                success=False,
                message="Audio appears to be silent. Please try recording again.",
            )

        stt = get_stt()
        text = stt.transcribe(audio_int16, sr).strip()

        if not text:
            return TranscriptionResponse(
                text="",
                duration=duration,
                success=False,
                message="No speech detected in audio. Please speak clearly and try again.",
            )

        return TranscriptionResponse(
            text=text,
            duration=duration,
            success=True,
            message=f"Transcription successful! Duration: {duration:.1f}s",
        )

    except Exception as e:
        import traceback
        print("Transcription error:", traceback.format_exc())
        return TranscriptionResponse(
            text="",
            duration=0.0,
            success=False,
            message=f"Transcription error: {str(e)}",
        )
    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


@app.post("/ask", response_model=AnswerResponse)
async def ask_question_endpoint(request: AskRequest):
    """
    Text-only: Uses LangChain tool-calling RAG to answer.
    Returns answer with optional metadata and context.
    """
    return answer_for_query(request.query)


@app.post("/process", response_model=AnswerResponse)
async def process_voice(audio_file: UploadFile = File(...)):
    """
    Full pipeline: audio -> transcribe -> RAG answer -> TTS audio base64
    """
    transcription = await transcribe_audio(audio_file)

    if not transcription.success:
        return AnswerResponse(
            answer="",
            audio_base64=None,
            success=False,
            message=transcription.message,
            metas=None,
            context=None,
        )

    return answer_for_query(transcription.text)


# -----------------------------------------------------------------------------
# For local development with uvicorn
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    print("🚀 Starting Sunmarke Voice RAG API...")
    print("📂 Serving from:", PROJECT_ROOT)
    print("🌐 Open your browser at: http://localhost:8000")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)

# -----------------------------------------------------------------------------
# Vercel serverless handler
# -----------------------------------------------------------------------------
handler = app