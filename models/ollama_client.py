import asyncio
import ollama
from tenacity import retry, stop_after_attempt, wait_fixed

from core.config import settings
from core.logger import logger
from models.model_registry import model_registry


class OllamaClient:
    def __init__(self):
        self.host = settings.OLLAMA_BASE_URL

        self.client = ollama.Client(host=self.host)
        self.async_client = ollama.AsyncClient(host=self.host)
        
        model_registry.register("ollama_client", self)

    @retry(
        stop=stop_after_attempt(settings.MODEL_MAX_RETRIES),
        wait=wait_fixed(2)
    )
    def generate(
        self,
        prompt: str,
        model: str = None,
        temperature: float = 0.2
    ):
        selected_model = model or settings.OLLAMA_DEFAULT_MODEL
        model_registry.register(selected_model, self.client)

        logger.info(f"Generating response using model: {selected_model}")

        response = self.client.chat(
            model=selected_model,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ],
            options={
                "temperature": temperature
            }
        )

        return response["message"]["content"]

    def health_check(self):
        try:
            self.client.list()
            return True
        except Exception as e:
            logger.error(f"Ollama health check failed: {e}")
            return False
        
    async def agenerate(
        self,
        prompt: str,
        model: str
    ):
        logger.info(f"Async generation using {model}")
        response = await self.async_client.generate(
            model=model,
            prompt=prompt
        )

        return response["response"]    
    
    async def astream_generate(
        self,
        prompt: str,
        model: str
    ):
        logger.info(f"Streaming generation using {model}")
        stream = await self.async_client.generate(
            model=model,
            prompt=prompt,
            stream=True
        )

        async for chunk in stream:
            yield chunk["response"]

ollama_client = OllamaClient()