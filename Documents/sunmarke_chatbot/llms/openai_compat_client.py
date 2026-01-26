import os
from openai import OpenAI


class OpenAICompatClient:
    def __init__(self, base_url_env: str, api_key_env: str, model_env: str, default_model: str):
        base_url = os.getenv(base_url_env)
        api_key = os.getenv(api_key_env)
        model = os.getenv(model_env, default_model)

        if not base_url:
            raise RuntimeError(f"{base_url_env} is missing.")
        if not api_key:
            raise RuntimeError(f"{api_key_env} is missing.")

        self.client = OpenAI(base_url=base_url, api_key=api_key)
        self.model = model

    def generate(self, system: str, user: str) -> str:
        resp = self.client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            temperature=0.2,
        )
        return (resp.choices[0].message.content or "").strip()
