import os
from typing import Optional

try:
    from google import genai
except Exception as e:
    genai = None
    _genai_import_error = e


class GeminiClient:
    def __init__(self):
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("GEMINI_API_KEY is missing in environment variables.")

        if genai is None:
            raise RuntimeError(
                "google.genai failed to import. "
                "Install it using `pip install google-genai`. "
                f"Original error: {_genai_import_error}"
            )

        self.client = genai.Client(api_key=api_key)
        self.model = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

    def generate(self, system: str, user: str) -> str:
        prompt = f"{system}\n\n{user}"

        response = self.client.models.generate_content(
            model=self.model,
            contents=prompt,
        )

        return (response.text or "").strip()
