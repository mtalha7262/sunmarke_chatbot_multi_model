import io
from gtts import gTTS


def tts_mp3_bytes(text: str, voice: str = "en-US-JennyNeural") -> bytes:
    """
    Convert text to speech using Google Text-to-Speech (gTTS).
    
    Args:
        text: The text to convert to speech
        voice: Not used with gTTS (kept for API compatibility)
    
    Returns:
        MP3 audio bytes
    """
    if not text or not text.strip():
        raise ValueError("Text cannot be empty")
    
    try:
        # Create gTTS object
        tts = gTTS(text=text, lang='en', slow=False)
        
        # Save to bytes buffer
        mp3_buffer = io.BytesIO()
        tts.write_to_fp(mp3_buffer)
        mp3_buffer.seek(0)
        
        return mp3_buffer.getvalue()
    
    except Exception as e:
        raise RuntimeError(f"Failed to generate speech: {str(e)}")
