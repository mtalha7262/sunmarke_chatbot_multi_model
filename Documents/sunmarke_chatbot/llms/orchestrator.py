import asyncio
from typing import Dict, Any

from llms.gemini_client import GeminiClient
from llms.openai_compat_client import OpenAICompatClient


class MultiModelOrchestrator:
    def __init__(self):
        self.clients = {}

        try:
            self.clients["Gemini"] = GeminiClient()
        except Exception as e:
            print(f"Failed to load Gemini: {e}")

        try:
            self.clients["Kimi"] = OpenAICompatClient(
                base_url_env="KIMI_BASE_URL",
                api_key_env="KIMI_API_KEY",
                model_env="KIMI_MODEL",
                default_model="moonshot-v1-8k",
            )
        except Exception as e:
            print(f"Failed to load Kimi: {e}")

        try:
            self.clients["DeepSeek"] = OpenAICompatClient(
                base_url_env="DEEPSEEK_BASE_URL",
                api_key_env="DEEPSEEK_API_KEY",
                model_env="DEEPSEEK_MODEL",
                default_model="deepseek-chat",
            )
        except Exception as e:
            print(f"Failed to load DeepSeek: {e}")

    async def _run_blocking(self, fn, *args):
        return await asyncio.to_thread(fn, *args)

    async def generate_all(self, system: str, user: str) -> Dict[str, Any]:
        async def wrap(name: str, client):
            try:
                text = await self._run_blocking(client.generate, system, user)
                return name, {"ok": True, "text": text}
            except Exception as e:
                return name, {"ok": False, "error": str(e)}

        tasks = []
        for name, client in self.clients.items():
            tasks.append(wrap(name, client))

        if not tasks:
            return {"Error": {"ok": False, "error": "No LLM clients initialized. Check your .env file."}}

        results = await asyncio.gather(*tasks)
        return {name: payload for name, payload in results}
