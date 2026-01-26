import numpy as np


def int16_to_float32(audio: np.ndarray) -> np.ndarray:
    if audio.dtype != np.int16:
        audio = audio.astype(np.int16)
    return audio.astype(np.float32) / 32768.0


def float32_to_int16(audio: np.ndarray) -> np.ndarray:
    audio = np.clip(audio, -1.0, 1.0)
    return (audio * 32767.0).astype(np.int16)