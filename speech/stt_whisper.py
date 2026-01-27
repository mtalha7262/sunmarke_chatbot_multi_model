import os
import numpy as np
from groq import Groq
import tempfile
import wave
import time

from speech.audio_utils import int16_to_float32


class WhisperSTT:
    def __init__(self):
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY is missing in environment variables.")
        
        self.client = Groq(api_key=api_key)
        print("Groq Whisper API client initialized successfully")

    def transcribe(self, audio_int16: np.ndarray, sample_rate: int) -> str:
        """Transcribe audio to text using Groq Whisper API with retry"""
        print(f"Transcribing audio: shape={audio_int16.shape}, sr={sample_rate}, dtype={audio_int16.dtype}")
        
        # Check if audio is silent
        rms = float(np.sqrt(np.mean(audio_int16.astype(np.float32) ** 2)))
        print(f"Audio RMS: {rms:.6f}")
        
        if rms < 100:  # Very low amplitude
            print("WARNING: Audio appears to be silent or very quiet")
            return ""
        
        # Create temporary WAV file
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
            tmp_path = tmp_file.name
            
            # Write WAV file
            with wave.open(tmp_path, "wb") as wav_file:
                wav_file.setnchannels(1)  # Mono
                wav_file.setsampwidth(2)  # 16-bit
                wav_file.setframerate(sample_rate)
                wav_file.writeframes(audio_int16.tobytes())
        
        max_retries = 3
        retry_delay = 2  # seconds
        
        try:
            for attempt in range(max_retries):
                try:
                    # Send to Groq Whisper API
                    print(f"Sending audio to Groq Whisper API (attempt {attempt + 1}/{max_retries})...")
                    with open(tmp_path, "rb") as audio_file:
                        transcription = self.client.audio.transcriptions.create(
                            file=(tmp_path, audio_file.read()),
                            model="whisper-large-v3",
                            temperature=0,
                            response_format="verbose_json",
                        )
                    
                    text = transcription.text.strip()
                    print(f"Final transcription: '{text}' (length: {len(text)})")
                    return text
                    
                except Exception as e:
                    error_str = str(e)
                    if "503" in error_str or "overloaded" in error_str.lower():
                        if attempt < max_retries - 1:
                            print(f"Groq API overloaded. Retrying in {retry_delay}s...")
                            time.sleep(retry_delay)
                            retry_delay *= 2  # Exponential backoff
                            continue
                    raise  # Re-raise if not a 503 or last attempt
        finally:
            # Clean up temporary file
            if os.path.exists(tmp_path):
                os.remove(tmp_path)