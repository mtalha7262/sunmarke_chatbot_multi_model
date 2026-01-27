"""
Main API endpoint with Server-Sent Events streaming for real-time responses
"""

import os
import sys
import tempfile
import json
import asyncio
from typing import Optional, Tuple

import numpy as np
import soundfile as sf
from fastapi import FastAPI, File, UploadFile, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from dotenv import load_dotenv

try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except Exception:
    PYDUB_AVAILABLE = False

load_dotenv()

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(PROJECT_ROOT)

from speech.stt_whisper import WhisperSTT

app = FastAPI(title="Sunmarke Multi-Model Voice RAG API", version="3.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PUBLIC_DIR = os.path.join(PROJECT_ROOT, "public")
if os.path.exists(PUBLIC_DIR):
    app.mount("/static", StaticFiles(directory=PUBLIC_DIR), name="static")

_stt: Optional[WhisperSTT] = None


def get_stt() -> WhisperSTT:
    global _stt
    if _stt is None:
        _stt = WhisperSTT()
    return _stt


class TranscriptionResponse(BaseModel):
    text: str
    duration: float
    success: bool
    message: str


class AskRequest(BaseModel):
    query: str


def validate_audio_length(audio_data: np.ndarray, sr: int, max_seconds: int = 30) -> Tuple[bool, str, float, np.ndarray]:
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


def _guess_suffix(upload: UploadFile) -> str:
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
    return ".webm"


def _convert_to_wav_if_needed(input_path: str, input_suffix: str) -> Tuple[str, Optional[str]]:
    if input_suffix == ".wav":
        return input_path, None
    if not PYDUB_AVAILABLE:
        raise RuntimeError("Non-wav audio received but pydub is not installed")
    wav_path = tempfile.mktemp(suffix=".wav")
    audio = AudioSegment.from_file(input_path)
    audio = audio.set_frame_rate(16000).set_channels(1)
    audio.export(wav_path, format="wav")
    return wav_path, wav_path


async def generate_streaming_responses(question: str):
    """Stream responses as they complete"""
    from rag.multi_agent import answer_question_multi_model_streaming

    try:
        # Send question first
        yield f"data: {json.dumps({'type': 'question', 'question': question})}\n\n"

        # Stream all model responses as they arrive
        async for event in answer_question_multi_model_streaming(question):
            yield f"data: {json.dumps(event)}\n\n"
            # Small delay to ensure proper flushing
            await asyncio.sleep(0.01)

        # Send completion
        yield f"data: {json.dumps({'type': 'done'})}\n\n"

    except Exception as e:
        print(f"Streaming error: {e}")
        import traceback
        traceback.print_exc()
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"


@app.get("/", response_class=HTMLResponse)
async def root():
    html_path = os.path.join(PUBLIC_DIR, "index.html")
    if os.path.exists(html_path):
        with open(html_path, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse(content="<h1>Sunmarke Multi-Model Voice RAG API</h1>")


@app.get("/health")
async def health_check():
    return {
        "status": "healthy",
        "models": ["Gemini", "Groq Mixtral", "Groq Llama"],
        "streaming": True,
        "pydub_available": PYDUB_AVAILABLE,
        "note": "Using 2 Groq models (Mixtral + Llama) instead of paid DeepSeek"
    }


@app.post("/transcribe", response_model=TranscriptionResponse)
async def transcribe_audio(audio_file: UploadFile = File(...)):
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

        try:
            read_path, temp_converted = _convert_to_wav_if_needed(temp_original, suffix)
        except Exception as e:
            return TranscriptionResponse(text="", duration=0.0, success=False, message=f"Audio format error: {str(e)}")

        try:
            audio_data, sr = sf.read(read_path)
        except Exception as e:
            return TranscriptionResponse(text="", duration=0.0, success=False, message=f"Could not read audio: {str(e)}")

        is_valid, msg, duration, mono = validate_audio_length(audio_data, sr, max_seconds=30)
        if not is_valid:
            return TranscriptionResponse(text="", duration=duration, success=False, message=msg)

        audio_int16 = float_to_int16(mono)
        rms = float(np.sqrt(np.mean(audio_int16.astype(np.float32) ** 2)))
        if rms < 100:
            return TranscriptionResponse(text="", duration=duration, success=False, message="Audio appears silent")

        stt = get_stt()
        text = stt.transcribe(audio_int16, sr).strip()

        if not text:
            return TranscriptionResponse(text="", duration=duration, success=False, message="No speech detected")

        return TranscriptionResponse(text=text, duration=duration, success=True, message=f"Success! Duration: {duration:.1f}s")

    except Exception as e:
        import traceback
        print("Transcription error:", traceback.format_exc())
        return TranscriptionResponse(text="", duration=0.0, success=False, message=f"Error: {str(e)}")
    finally:
        for p in [temp_converted, temp_original]:
            if p and os.path.exists(p):
                try:
                    os.remove(p)
                except Exception:
                    pass


@app.post("/ask-stream")
async def ask_question_stream_post(request: AskRequest):
    """POST endpoint for streaming responses"""
    query = (request.query or "").strip()
    if not query:
        async def error_gen():
            yield f"data: {json.dumps({'type': 'error', 'message': 'Empty query'})}\n\n"
        
        return StreamingResponse(
            error_gen(),
            media_type="text/event-stream",
        )

    return StreamingResponse(
        generate_streaming_responses(query),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/ask-stream")
async def ask_question_stream_get(query: str = Query(...)):
    """GET endpoint for EventSource streaming"""
    q = (query or "").strip()
    if not q:
        async def error_gen():
            yield f"data: {json.dumps({'type': 'error', 'message': 'Empty query'})}\n\n"
        
        return StreamingResponse(
            error_gen(),
            media_type="text/event-stream",
        )

    return StreamingResponse(
        generate_streaming_responses(q),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/process-stream")
async def process_voice_stream(audio_file: UploadFile = File(...)):
    """Process voice and stream responses"""
    transcription = await transcribe_audio(audio_file)
    
    if not transcription.success:
        async def error_gen():
            yield f"data: {json.dumps({'type': 'error', 'message': transcription.message})}\n\n"
        
        return StreamingResponse(
            error_gen(),
            media_type="text/event-stream",
        )

    return StreamingResponse(
        generate_streaming_responses(transcription.text),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


if __name__ == "__main__":
    import uvicorn
    reload_flag = os.getenv("RELOAD", "true").lower() == "true"
    print("🚀 Starting Sunmarke Multi-Model Voice RAG API with Streaming...")
    print("🌐 Open: http://localhost:8000")
    print("📊 Models: Gemini | Groq Mixtral | Groq Llama")
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=reload_flag, timeout_graceful_shutdown=1)

handler = app

# """
# Vercel Serverless API - Main Entry Point
# This file is designed to work with Vercel's serverless function architecture
# """

# import os
# import sys
# import tempfile
# import json
# import asyncio
# from typing import Optional, Tuple

# import numpy as np
# import soundfile as sf
# from fastapi import FastAPI, File, UploadFile, Query
# from fastapi.middleware.cors import CORSMiddleware
# from fastapi.responses import HTMLResponse, StreamingResponse
# from pydantic import BaseModel

# # Add project root to Python path for imports
# PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# sys.path.insert(0, PROJECT_ROOT)

# # Initialize FastAPI app
# app = FastAPI(
#     title="Sunmarke Voice RAG API",
#     version="4.0.0",
#     docs_url="/api/docs",
#     redoc_url="/api/redoc"
# )

# # CORS configuration
# app.add_middleware(
#     CORSMiddleware,
#     allow_origins=["*"],
#     allow_credentials=True,
#     allow_methods=["*"],
#     allow_headers=["*"],
# )

# # Global cache for models (persists between warm invocations)
# _stt_cache = None


# def get_stt():
#     """Lazy load STT model to reduce cold starts"""
#     global _stt_cache
#     if _stt_cache is None:
#         from speech.stt_whisper import WhisperSTT
#         _stt_cache = WhisperSTT()
#     return _stt_cache


# class TranscriptionResponse(BaseModel):
#     text: str
#     duration: float
#     success: bool
#     message: str


# class AskRequest(BaseModel):
#     query: str


# def validate_audio_length(audio_data: np.ndarray, sr: int, max_seconds: int = 30) -> Tuple[bool, str, float, np.ndarray]:
#     if audio_data is None or len(audio_data) == 0:
#         return False, "No audio data", 0.0, audio_data
#     if audio_data.ndim == 2:
#         audio_data = audio_data[:, 0]
#     duration = float(len(audio_data) / float(sr)) if sr else 0.0
#     if duration > max_seconds:
#         return False, f"Audio too long: {duration:.1f}s (max {max_seconds}s)", duration, audio_data
#     return True, f"Audio duration: {duration:.1f}s", duration, audio_data


# def float_to_int16(audio: np.ndarray) -> np.ndarray:
#     if audio.dtype == np.int16:
#         return audio
#     audio = np.clip(audio, -1.0, 1.0)
#     return (audio * 32767.0).astype(np.int16)


# async def generate_streaming_responses(question: str):
#     """Stream responses as they complete - Vercel compatible"""
#     from rag.multi_agent import answer_question_multi_model_streaming

#     try:
#         # Send question first
#         yield f"data: {json.dumps({'type': 'question', 'question': question})}\n\n"

#         # Stream all model responses
#         async for event in answer_question_multi_model_streaming(question):
#             yield f"data: {json.dumps(event)}\n\n"
#             # Small delay for proper SSE flushing
#             await asyncio.sleep(0.01)

#         # Send completion
#         yield f"data: {json.dumps({'type': 'done'})}\n\n"

#     except Exception as e:
#         print(f"Streaming error: {e}")
#         import traceback
#         traceback.print_exc()
#         yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"


# @app.get("/")
# async def root():
#     """Serve the main HTML page"""
#     html_path = os.path.join(PROJECT_ROOT, "public", "index.html")
    
#     if os.path.exists(html_path):
#         with open(html_path, "r", encoding="utf-8") as f:
#             return HTMLResponse(content=f.read())
    
#     return HTMLResponse(content="""
#     <!DOCTYPE html>
#     <html>
#     <head>
#         <title>Sunmarke Voice RAG API</title>
#         <style>
#             body {
#                 font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
#                 background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
#                 color: white;
#                 display: flex;
#                 justify-content: center;
#                 align-items: center;
#                 height: 100vh;
#                 margin: 0;
#             }
#             .container {
#                 text-align: center;
#                 background: rgba(255, 255, 255, 0.1);
#                 padding: 40px;
#                 border-radius: 20px;
#                 backdrop-filter: blur(10px);
#             }
#             h1 { font-size: 3em; margin-bottom: 20px; }
#             p { font-size: 1.2em; margin: 10px 0; }
#             .badge {
#                 background: rgba(255, 255, 255, 0.2);
#                 padding: 10px 20px;
#                 border-radius: 20px;
#                 display: inline-block;
#                 margin: 10px 0;
#             }
#         </style>
#     </head>
#     <body>
#         <div class="container">
#             <h1>🎤 Sunmarke Voice RAG API</h1>
#             <p>API is running on Vercel!</p>
#             <div class="badge">⚡ Live Streaming Enabled</div>
#             <p style="margin-top: 20px;">Models: Gemini | Groq Mixtral | Groq Llama</p>
#             <p style="font-size: 0.9em; margin-top: 30px;">
#                 <a href="/api/health" style="color: white;">Health Check</a> | 
#                 <a href="/api/docs" style="color: white;">API Docs</a>
#             </p>
#         </div>
#     </body>
#     </html>
#     """)


# @app.get("/api")
# @app.get("/api/")
# async def api_root():
#     """API root endpoint"""
#     return {
#         "status": "healthy",
#         "platform": "Vercel Serverless",
#         "models": ["Gemini", "Groq Mixtral", "Groq Llama"],
#         "streaming": True,
#         "version": "4.0.0"
#     }


# @app.get("/api/health")
# async def health_check():
#     """Health check endpoint"""
#     return {
#         "status": "healthy",
#         "platform": "Vercel",
#         "models": ["Gemini", "Groq Mixtral", "Groq Llama"],
#         "streaming": True,
#         "python_version": f"{sys.version_info.major}.{sys.version_info.minor}"
#     }


# @app.post("/api/transcribe")
# async def transcribe_audio(audio_file: UploadFile = File(...)):
#     """Transcribe audio file - Vercel compatible"""
#     temp_path = None
    
#     try:
#         # Read audio file
#         audio_bytes = await audio_file.read()
#         if not audio_bytes:
#             return TranscriptionResponse(
#                 text="", duration=0.0, success=False, 
#                 message="Empty audio file"
#             )

#         # Save to temp file
#         temp_path = tempfile.mktemp(suffix=".wav")
#         with open(temp_path, "wb") as f:
#             f.write(audio_bytes)

#         # Read and validate audio
#         try:
#             audio_data, sr = sf.read(temp_path)
#         except Exception as e:
#             return TranscriptionResponse(
#                 text="", duration=0.0, success=False,
#                 message=f"Could not read audio: {str(e)}"
#             )

#         is_valid, msg, duration, mono = validate_audio_length(audio_data, sr, max_seconds=30)
#         if not is_valid:
#             return TranscriptionResponse(
#                 text="", duration=duration, success=False, message=msg
#             )

#         # Convert to int16
#         audio_int16 = float_to_int16(mono if mono.ndim == 1 else mono[:, 0])
        
#         # Check if silent
#         rms = float(np.sqrt(np.mean(audio_int16.astype(np.float32) ** 2)))
#         if rms < 100:
#             return TranscriptionResponse(
#                 text="", duration=duration, success=False,
#                 message="Audio appears silent"
#             )

#         # Transcribe
#         stt = get_stt()
#         text = stt.transcribe(audio_int16, sr).strip()

#         if not text:
#             return TranscriptionResponse(
#                 text="", duration=duration, success=False,
#                 message="No speech detected"
#             )

#         return TranscriptionResponse(
#             text=text, duration=duration, success=True,
#             message=f"Success! Duration: {duration:.1f}s"
#         )

#     except Exception as e:
#         import traceback
#         print("Transcription error:", traceback.format_exc())
#         return TranscriptionResponse(
#             text="", duration=0.0, success=False,
#             message=f"Error: {str(e)}"
#         )
    
#     finally:
#         if temp_path and os.path.exists(temp_path):
#             try:
#                 os.remove(temp_path)
#             except:
#                 pass


# @app.get("/api/ask-stream")
# async def ask_stream_get(query: str = Query(...)):
#     """GET endpoint for SSE streaming - Vercel compatible"""
#     q = (query or "").strip()
#     if not q:
#         async def error_gen():
#             yield f"data: {json.dumps({'type': 'error', 'message': 'Empty query'})}\n\n"
        
#         return StreamingResponse(
#             error_gen(),
#             media_type="text/event-stream",
#             headers={
#                 "Cache-Control": "no-cache, no-transform",
#                 "Connection": "keep-alive",
#                 "X-Accel-Buffering": "no",
#             }
#         )

#     return StreamingResponse(
#         generate_streaming_responses(q),
#         media_type="text/event-stream",
#         headers={
#             "Cache-Control": "no-cache, no-transform",
#             "Connection": "keep-alive",
#             "X-Accel-Buffering": "no",
#         }
#     )


# @app.post("/api/ask-stream")
# async def ask_stream_post(request: AskRequest):
#     """POST endpoint for SSE streaming - Vercel compatible"""
#     query = (request.query or "").strip()
#     if not query:
#         async def error_gen():
#             yield f"data: {json.dumps({'type': 'error', 'message': 'Empty query'})}\n\n"
        
#         return StreamingResponse(
#             error_gen(),
#             media_type="text/event-stream",
#             headers={
#                 "Cache-Control": "no-cache, no-transform",
#                 "Connection": "keep-alive",
#                 "X-Accel-Buffering": "no",
#             }
#         )

#     return StreamingResponse(
#         generate_streaming_responses(query),
#         media_type="text/event-stream",
#         headers={
#             "Cache-Control": "no-cache, no-transform",
#             "Connection": "keep-alive",
#             "X-Accel-Buffering": "no",
#         }
#     )


# @app.post("/api/process-stream")
# async def process_voice_stream(audio_file: UploadFile = File(...)):
#     """Process voice and stream responses - Vercel compatible"""
#     transcription = await transcribe_audio(audio_file)
    
#     if not transcription.success:
#         async def error_gen():
#             yield f"data: {json.dumps({'type': 'error', 'message': transcription.message})}\n\n"
        
#         return StreamingResponse(
#             error_gen(),
#             media_type="text/event-stream",
#             headers={
#                 "Cache-Control": "no-cache, no-transform",
#                 "Connection": "keep-alive",
#                 "X-Accel-Buffering": "no",
#             }
#         )

#     return StreamingResponse(
#         generate_streaming_responses(transcription.text),
#         media_type="text/event-stream",
#         headers={
#             "Cache-Control": "no-cache, no-transform",
#             "Connection": "keep-alive",
#             "X-Accel-Buffering": "no",
#         }
#     )


# # Vercel serverless handler
# handler = app