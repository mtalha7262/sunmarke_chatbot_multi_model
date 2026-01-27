# api/index.py
"""
Main API endpoint for Vercel serverless deployment
Handles voice-to-text transcription and Multi-Model RAG answering
"""

import os
import sys
import tempfile
import base64
import numpy as np
import json
import asyncio
from typing import Optional, Tuple, Dict

from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv
import soundfile as sf

# Optional (recommended) for webm/mp4 -> wav conversion
try:
    from pydub import AudioSegment  # requires ffmpeg installed
    PYDUB_AVAILABLE = True
except Exception:
    PYDUB_AVAILABLE = False

# Load environment variables
load_dotenv()

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

from speech.stt_whisper import WhisperSTT
from speech.tts_edge import tts_mp3_bytes


# -----------------------------------------------------------------------------
# FastAPI app
# -----------------------------------------------------------------------------
app = FastAPI(title="Sunmarke Multi-Model Voice RAG API", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
PUBLIC_DIR = os.path.join(PROJECT_ROOT, "public")
if os.path.exists(PUBLIC_DIR):
    app.mount("/static", StaticFiles(directory=PUBLIC_DIR), name="static")


# -----------------------------------------------------------------------------
# Serverless singletons
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


class ModelResponse(BaseModel):
    model: str               # Human readable label like "Gemini", "KIMI", "DeepSeek"
    answer: str
    audio_base64: Optional[str] = None
    success: bool
    error: Optional[str] = None


class MultiModelAnswerResponse(BaseModel):
    question: str
    success: bool
    message: str
    responses: Dict[str, ModelResponse]  # keys: gemini/kimi/deepseek
    context: Optional[str] = None
    metas: Optional[list] = None


class AskRequest(BaseModel):
    query: str


# -----------------------------------------------------------------------------
# Helpers
# -----------------------------------------------------------------------------
MODEL_LABELS = {
    "gemini": "Gemini",
    # "kimi": "KIMI",
    "groq": "Groq Llama",
    "deepseek": "DeepSeek",
}


def validate_audio_length(
    audio_data: np.ndarray,
    sr: int,
    max_seconds: int = 30
) -> Tuple[bool, str, float, np.ndarray]:
    if audio_data is None or len(audio_data) == 0:
        return False, "No audio data", 0.0, audio_data

    if audio_data.ndim == 2:
        audio_data = audio_data[:, 0]

    duration = float(len(audio_data) / float(sr)) if sr else 0.0

    if duration > max_seconds:
        return False, f"Audio too long: {duration:.1f}s (max {max_seconds}s)", duration, audio_data

    return True, f"Audio duration: {duration:.1f}s", duration, audio_data


def float_to_int16(audio: np.ndarray) -> np.ndarray:
    if audio.dtype == np.int16:
        return audio
    audio = np.clip(audio, -1.0, 1.0)
    return (audio * 32767.0).astype(np.int16)


def build_tts_base64(text: str) -> Optional[str]:
    try:
        audio_bytes = tts_mp3_bytes(text)
        return base64.b64encode(audio_bytes).decode("utf-8")
    except Exception as e:
        print(f"TTS error: {e}")
        return None


def _guess_suffix(upload: UploadFile) -> str:
    """
    Pick a suffix based on filename/content-type.
    """
    name = (upload.filename or "").lower()
    ctype = (upload.content_type or "").lower()

    if name.endswith(".wav") or "wav" in ctype:
        return ".wav"
    if name.endswith(".webm") or "webm" in ctype:
        return ".webm"
    if name.endswith(".mp4") or "mp4" in ctype:
        return ".mp4"
    if name.endswith(".m4a") or "m4a" in ctype:
        return ".m4a"
    if name.endswith(".ogg") or "ogg" in ctype:
        return ".ogg"

    # default (many browsers record webm)
    return ".webm"


def _convert_to_wav_if_needed(input_path: str, input_suffix: str) -> Tuple[str, Optional[str]]:
    """
    If input isn't wav, convert to wav 16k mono using pydub (ffmpeg).
    Returns: (path_to_use_for_sf_read, temp_wav_path_to_cleanup)
    """
    if input_suffix == ".wav":
        return input_path, None

    if not PYDUB_AVAILABLE:
        raise RuntimeError(
            "Non-wav audio received but pydub is not installed. "
            "Install: pip install pydub  AND install ffmpeg, "
            "or send WAV from frontend."
        )

    wav_path = tempfile.mktemp(suffix=".wav")
    audio = AudioSegment.from_file(input_path)
    audio = audio.set_frame_rate(16000).set_channels(1)
    audio.export(wav_path, format="wav")
    return wav_path, wav_path


def answer_for_query_multi(query: str) -> MultiModelAnswerResponse:
    """
    Query all 3 models and return their responses.
    Uses lazy import to avoid circular-import issues.
    """
    from rag.multi_agent import answer_question_multi_model  # lazy import

    query = (query or "").strip()
    if not query:
        return MultiModelAnswerResponse(
            question="",
            success=False,
            message="Empty query",
            responses={},
            context=None,
            metas=None,
        )

    try:
        result = answer_question_multi_model(query)

        model_responses: Dict[str, ModelResponse] = {}

        # result["responses"] expected keys: gemini/kimi/deepseek
        for model_key, model_result in (result.get("responses") or {}).items():
            answer_text = (model_result or {}).get("answer", "") or ""
            ok = bool((model_result or {}).get("success", False))

            # Generate TTS only if model succeeded
            audio_b64 = None
            if ok and answer_text.strip():
                audio_b64 = build_tts_base64(answer_text)

            model_responses[model_key] = ModelResponse(
                model=MODEL_LABELS.get(model_key, model_key),
                answer=answer_text,
                audio_base64=audio_b64,
                success=ok,
                error=(model_result or {}).get("error"),
            )

        # overall success: true if we got at least 1 response
        overall_ok = len(model_responses) > 0
        msg = "Answers generated from all models" if overall_ok else "No model responses returned"

        return MultiModelAnswerResponse(
            question=query,
            success=overall_ok,
            message=msg,
            responses=model_responses,
            context=result.get("context", ""),
            metas=result.get("metas", []),
        )

    except Exception as e:
        import traceback
        print("Multi-model error:", traceback.format_exc())
        return MultiModelAnswerResponse(
            question=query,
            success=False,
            message=f"Error: {str(e)}",
            responses={},
            context=None,
            metas=None,
        )


# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------
@app.get("/", response_class=HTMLResponse)
async def root():
    """
    Serve the main HTML interface
    """
    html_path = os.path.join(PUBLIC_DIR, "index.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())

    return HTMLResponse(content="""
    <html>
      <body>
        <h1>Sunmarke Multi-Model Voice RAG API</h1>
        <p>HTML file not found. Please create public/index.html</p>
        <ul>
          <li>POST /transcribe</li>
          <li>POST /ask-multi</li>
          <li>POST /process-multi</li>
          <li>GET /health</li>
        </ul>
      </body>
    </html>
    """)


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "models": ["Gemini", "KIMI", "DeepSeek"],
        "embeddings": "Cohere",
        "stt": "Groq Whisper",
        "tts": "Edge TTS",
        "pydub_available": PYDUB_AVAILABLE
    }


@app.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(audio_file: UploadFile = File(...)):
    """
    Transcribe audio using WhisperSTT (Groq Whisper in your implementation).
    Supports: wav/webm/mp4/m4a/ogg (web formats converted to wav if pydub+ffmpeg present).
    """
    temp_original = None
    temp_converted = None

    try:
        audio_bytes = await audio_file.read()
        if not audio_bytes:
            return TranscriptionResponse(text="", duration=0.0, success=False, message="Empty audio file")

        suffix = _guess_suffix(audio_file)

        temp_original = tempfile.mktemp(suffix=suffix)
        with open(temp_original, "wb") as f:
            f.write(audio_bytes)

        # Convert if needed
        try:
            read_path, temp_converted = _convert_to_wav_if_needed(temp_original, suffix)
        except Exception as e:
            return TranscriptionResponse(
                text="",
                duration=0.0,
                success=False,
                message=f"Audio format not supported: {str(e)}"
            )

        # Read WAV
        try:
            audio_data, sr = sf.read(read_path)
        except Exception as e:
            return TranscriptionResponse(
                text="",
                duration=0.0,
                success=False,
                message=f"Could not read audio file: {str(e)}"
            )

        is_valid, msg, duration, mono = validate_audio_length(audio_data, sr, max_seconds=30)
        if not is_valid:
            return TranscriptionResponse(text="", duration=duration, success=False, message=msg)

        audio_int16 = float_to_int16(mono)

        # Silence check (adjust threshold if needed)
        rms = float(np.sqrt(np.mean(audio_int16.astype(np.float32) ** 2)))
        if rms < 100:
            return TranscriptionResponse(
                text="",
                duration=duration,
                success=False,
                message="Audio appears to be silent. Please try recording again."
            )

        stt = get_stt()
        text = stt.transcribe(audio_int16, sr).strip()

        if not text:
            return TranscriptionResponse(
                text="",
                duration=duration,
                success=False,
                message="No speech detected in audio. Please speak clearly and try again."
            )

        return TranscriptionResponse(
            text=text,
            duration=duration,
            success=True,
            message=f"Transcription successful! Duration: {duration:.1f}s"
        )

    except Exception as e:
        import traceback
        print("Transcription error:", traceback.format_exc())
        return TranscriptionResponse(
            text="",
            duration=0.0,
            success=False,
            message=f"Transcription error: {str(e)}"
        )

    finally:
        # cleanup
        for p in [temp_converted, temp_original]:
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass


@app.post("/ask-multi", response_model=MultiModelAnswerResponse)
async def ask_question_multi_endpoint(request: AskRequest):
    """
    Text-only: Query all 3 models simultaneously
    """
    return answer_for_query_multi(request.query)


@app.post("/process-multi", response_model=MultiModelAnswerResponse)
async def process_voice_multi(audio_file: UploadFile = File(...)):
    """
    Full pipeline: audio -> transcribe -> 3 model answers -> 3 TTS outputs
    """
    transcription = await transcribe_audio(audio_file)

    if not transcription.success:
        return MultiModelAnswerResponse(
            question="",
            success=False,
            message=transcription.message,
            responses={},
            context=None,
            metas=None,
        )

    return answer_for_query_multi(transcription.text)


# -----------------------------------------------------------------------------
# For local development
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn

    reload_flag = os.getenv("RELOAD", "true").lower() == "true"

    print("🚀 Starting Sunmarke Multi-Model Voice RAG API...")
    print("📂 Serving from:", PROJECT_ROOT)
    print("🌐 Open your browser at: http://localhost:8000")

    # Timeout graceful shutdown helps with slow exit on Windows
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=reload_flag,
        timeout_graceful_shutdown=1
    )

# Vercel serverless handler
handler = app
